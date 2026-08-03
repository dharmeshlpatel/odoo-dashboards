# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class BaseModelDashboardEngine(models.AbstractModel):
    """
    Lightweight hooks and payload fields available on every model.

    Generated kanban cards call these object methods and read these fields;
    both delegate to ``dashboard.blueprint`` so host models need no custom
    Python and the engine stays free of business-app dependencies.

    Host models are chosen at runtime by configuration, so the fields cannot
    be attached through a static ``_inherit`` on each model. They live on
    ``base`` instead, and every compute short-circuits unless a dashboard is
    actually rendering, so the cost on unrelated models is nil.
    """

    _inherit = "base"

    dashboard_graph_data = fields.Text(
        compute="_compute_dashboard_engine_graph",
        help="Chart payload consumed by the analytic_dashboard_graph widget.",
    )
    dashboard_graph_type = fields.Selection(
        [("bar", "Bar"), ("line", "Line")],
        compute="_compute_dashboard_engine_graph",
    )
    dashboard_slots = fields.Json(
        compute="_compute_dashboard_engine_slots",
        help="KPI / button / menu payload rendered by the dashboard_slots widget.",
    )
    dashboard_primary_label = fields.Char(
        compute="_compute_dashboard_engine_primary_label",
        help="Text on the card's main button. Same for every card on the "
        "page — it depends on the viewer's saved preferences, not the "
        "record — so it is computed once per batch, not per card.",
    )
    # Kanban search-view toggles: never stored; rewritten in search_fetch.
    # search= stubs make the fields searchable for ir.ui.view validation;
    # the real domain rewrite stays in search_fetch (two-pass My ∩ KPIs).
    dashboard_my_data = fields.Boolean(
        store=False, search="_search_dashboard_my_data"
    )
    dashboard_with_kpis = fields.Boolean(
        store=False, search="_search_dashboard_with_kpis"
    )
    dashboard_needs_attention = fields.Boolean(
        store=False, search="_search_dashboard_needs_attention"
    )

    def _search_dashboard_my_data(self, operator, value):
        """Fallback only; dashboard search_fetch rewrites this leaf first."""
        return [("id", "=", False)]

    def _search_dashboard_with_kpis(self, operator, value):
        """Fallback only; dashboard search_fetch rewrites this leaf first."""
        return [("id", "=", False)]

    def _search_dashboard_needs_attention(self, operator, value):
        """Fallback only; dashboard search_fetch rewrites this leaf first."""
        return [("id", "=", False)]

    def _dashboard_engine_blueprint(self):
        """Published blueprint for the current card page, read as sudo.

        Configuration is not a business document: every internal user who can
        open the generated kanban must be able to render it, without needing
        the engine ACL. Actions still execute as the viewer so record rules
        on CRM/Sales/… keep applying.
        """
        return self.env["dashboard.blueprint"].sudo()._get_rendering_blueprint(
            self._name
        )

    @api.depends_context("dashboard_blueprint_key")
    def _compute_dashboard_engine_primary_label(self):
        blueprint = self._dashboard_engine_blueprint()
        label = blueprint._resolved_primary_label() if blueprint else False
        for record in self:
            record.dashboard_primary_label = label

    @api.depends_context("dashboard_blueprint_key")
    def _compute_dashboard_engine_slots(self):
        blueprint = self._dashboard_engine_blueprint()
        if not blueprint:
            self.dashboard_slots = False
            return
        # Re-bind env.user for group/pref checks inside the sudo blueprint.
        blueprint = blueprint.with_user(self.env.user)
        payloads = blueprint._build_slots_payloads(self)
        empty = blueprint._empty_slots_payload()
        for record in self:
            record.dashboard_slots = payloads.get(record.id) or empty

    @api.depends_context("dashboard_blueprint_key")
    def _compute_dashboard_engine_graph(self):
        blueprint = self._dashboard_engine_blueprint()
        if not blueprint or not blueprint._has_graph():
            self.dashboard_graph_data = False
            self.dashboard_graph_type = False
            return
        blueprint = blueprint.with_user(self.env.user)
        payloads = blueprint._build_graph_payloads(self)
        for record in self:
            payload = payloads.get(record.id) or {}
            record.dashboard_graph_data = payload.get("json", False)
            record.dashboard_graph_type = payload.get("type", False)

    def action_dashboard_engine_primary(self):
        self.ensure_one()
        key = self.env.context.get("dashboard_blueprint_key")
        if not key:
            return False
        return self.env["dashboard.blueprint"].execute_primary_action(
            key, self._name, self.id
        )

    def action_dashboard_engine_slot(self):
        self.ensure_one()
        key = self.env.context.get("dashboard_blueprint_key")
        slot_key = self.env.context.get("dashboard_slot_key")
        if not key or not slot_key:
            return False
        return self.env["dashboard.blueprint"].execute_slot_action(
            key, slot_key, self._name, self.id
        )

    @api.model
    def _search(
        self,
        domain,
        offset=0,
        limit=None,
        order=None,
        *,
        active_test=True,
        bypass_access=False,
    ):
        # Rewrite here (not only search_fetch) so Group By / _read_group also
        # resolve virtual lens flags. Ungrouped kanban uses search_fetch →
        # _search; grouped kanban uses _read_group → _search.
        domain = self._dashboard_lens_rewrite_domain(domain)
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            active_test=active_test,
            bypass_access=bypass_access,
        )

    @api.model
    def _dashboard_lens_rewrite_domain(self, domain):
        """Replace virtual lens flags with real domains when rendering.

        Multi-pass rewrite of virtual flags. When My and With KPIs are both on,
        My becomes a host domain and KPIs use the full KPI host-id set;
        intersection is ``my_domain AND id in kpi_ids``. Needs attention is
        ``id in attention_ids`` and AND-intersects with My / KPIs the same way.
        Do not also narrow KPI graph rows by ``user_id`` — that over-filters
        hosts that already scope My via host ``user_id`` (e.g. ``res.partner``).

        Gate: ``dashboard_blueprint_key`` present, not
        ``_dashboard_fetching_data``, and blueprint host matches ``self._name``.

        Applied from ``_search`` so both flat search and Group By paths work.
        Without this, Group By hits the ``search=`` stubs that return
        ``[('id', '=', False)]`` and the kanban goes blank.
        """
        key = self.env.context.get("dashboard_blueprint_key")
        if not key or self.env.context.get("_dashboard_fetching_data"):
            return domain
        # Lookup must not re-enter rewrite (context still carries the key).
        bp = (
            self.env["dashboard.blueprint"]
            .sudo()
            .with_context(_dashboard_fetching_data=True)
            ._get_blueprint(key)
        )
        if not bp or bp.host_model_name != self._name:
            return domain
        bp = bp.with_user(self.env.user)
        # Domain objects and plain lists both iterate to leaf/operator tokens.
        domain = list(domain or [])

        def _is_flag(leaf, name):
            return (
                isinstance(leaf, (list, tuple))
                and len(leaf) >= 3
                and leaf[0] == name
            )

        def _flag_on(leaf):
            return leaf[2] in (True, 1, [True], [1])

        out = []
        for leaf in domain:
            if _is_flag(leaf, "dashboard_my_data"):
                if _flag_on(leaf):
                    out.extend(bp._lens_my_domain())
                continue
            if _is_flag(leaf, "dashboard_with_kpis"):
                if _flag_on(leaf):
                    out.append(("id", "in", bp._lens_kpis_host_ids()))
                continue
            if _is_flag(leaf, "dashboard_needs_attention"):
                if _flag_on(leaf):
                    out.append(("id", "in", bp._lens_attention_host_ids()))
                continue
            out.append(leaf)
        return out
