# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Cross-model My / panel-filter maps (Product B′ linked 360).

Viewer blueprint prefs drive My + period + custom filter. Include scopes stay
chart-only. Maps translate those prefs onto peer models (e.g. sale.order)
without ``sudo()`` shortcuts — target record rules always apply.
"""
import logging

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

from ..tools.date_utils import _get_period_dates
from ..tools.domain_utils import _date_range_to_domain
from .dashboard_graph_periods import get_period_year

_logger = logging.getLogger(__name__)

# Commercial surfaces that can inherit My / panel filters.
PANEL_MY_SECTIONS = frozenset(
    {"kpi", "bottom", "button_box", "menu_views", "menu_reports"}
)
SECTION_APPLY_FLAG = {
    "kpi": "apply_kpi",
    "bottom": "apply_bottom",
    "button_box": "apply_bottom",
    "menu_views": "apply_views",
    "menu_reports": "apply_reports",
    "menu_new": "apply_menu_new",
}

ASSIGNEE_FIELD_CANDIDATES = ("user_id", "user_ids", "salesperson_id")


class DashboardBlueprintScopeTarget(models.Model):
    """Map a restrict/panel filter from the graph model onto another model."""

    _name = "dashboard.blueprint.scope.target"
    _description = "Dashboard Scope Target Map"
    _order = "sequence, id"

    scope_id = fields.Many2one(
        "dashboard.blueprint.scope",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    target_model = fields.Char(
        required=True,
        index=True,
        help="Technical model that receives this map, e.g. sale.order.",
    )
    target_model_id = fields.Many2one(
        "ir.model",
        string="Target Model",
        compute="_compute_target_model_id",
        inverse="_inverse_target_model_id",
        store=True,
        readonly=False,
        ondelete="cascade",
    )
    domain = fields.Char(
        default="[('user_id', '=', uid)]",
        required=True,
        string="Domain",
        help="Domain evaluated with uid/user. Must use fields that exist on "
        "the target model.",
    )
    module_depends = fields.Char(
        string="Required Apps",
        help="Comma-separated modules. Map is ignored until all are installed.",
    )
    period_field = fields.Char(
        string="Create / open period field",
        help="Target field for gear Creation Date filter, e.g. date_order.",
    )
    period_closed_field = fields.Char(
        string="Closed period field",
        help="Target field for gear Closed Date filter, if any.",
    )
    period_field_id = fields.Many2one(
        "ir.model.fields",
        string="Create / open period field",
        compute="_compute_period_field_ids",
        inverse="_inverse_period_field_id",
        store=True,
        readonly=False,
        ondelete="set null",
        domain=(
            "[('model_id', '=', target_model_id), "
            "('ttype', 'in', ['date', 'datetime'])]"
        ),
    )
    period_closed_field_id = fields.Many2one(
        "ir.model.fields",
        string="Closed period field",
        compute="_compute_period_field_ids",
        inverse="_inverse_period_closed_field_id",
        store=True,
        readonly=False,
        ondelete="set null",
        domain=(
            "[('model_id', '=', target_model_id), "
            "('ttype', 'in', ['date', 'datetime'])]"
        ),
    )
    apply_kpi = fields.Boolean(default=True, string="Apply to KPIs")
    apply_bottom = fields.Boolean(default=True, string="Apply to bottoms")
    apply_views = fields.Boolean(default=True, string="Apply to views")
    apply_reports = fields.Boolean(default=True, string="Apply to reports")
    apply_menu_new = fields.Boolean(
        default=False,
        string="Apply to New (defaults only)",
        help="When on, New menus get assignee defaults only — never a domain "
        "that blocks create.",
    )

    @api.depends("target_model")
    def _compute_target_model_id(self):
        Model = self.env["ir.model"].sudo()
        for rec in self:
            rec.target_model_id = (
                Model.search([("model", "=", rec.target_model)], limit=1)
                if rec.target_model
                else False
            )

    def _inverse_target_model_id(self):
        for rec in self:
            rec.target_model = rec.target_model_id.model or False

    @api.depends("period_field", "period_closed_field", "target_model")
    def _compute_period_field_ids(self):
        Fields = self.env["ir.model.fields"].sudo()
        for rec in self:
            rec.period_field_id = (
                Fields.search(
                    [
                        ("model", "=", rec.target_model),
                        ("name", "=", rec.period_field),
                    ],
                    limit=1,
                )
                if rec.target_model and rec.period_field
                else False
            )
            rec.period_closed_field_id = (
                Fields.search(
                    [
                        ("model", "=", rec.target_model),
                        ("name", "=", rec.period_closed_field),
                    ],
                    limit=1,
                )
                if rec.target_model and rec.period_closed_field
                else False
            )

    def _inverse_period_field_id(self):
        for rec in self:
            rec.period_field = rec.period_field_id.name or False

    def _inverse_period_closed_field_id(self):
        for rec in self:
            rec.period_closed_field = rec.period_closed_field_id.name or False

    def _modules_ok(self):
        self.ensure_one()
        return self.env["dashboard.blueprint"]._modules_installed_static(
            self.module_depends
        )

    def _target_domain(self):
        """Domain for this map, with uid resolved. Empty if unsafe."""
        self.ensure_one()
        if not self._modules_ok():
            return []
        if not self.target_model or self.target_model not in self.env:
            return []
        try:
            domain = list(
                safe_eval(
                    self.domain or "[]",
                    {"uid": self.env.uid, "user": self.env.user},
                )
            )
        except Exception:
            _logger.warning(
                "Dashboard engine: unreadable scope target domain on %s → %s",
                self.scope_id.name,
                self.target_model,
                exc_info=True,
            )
            return []
        if not self._domain_applies_to_target(domain):
            _logger.info(
                "dashboard_engine skip map scope=%s model=%s reason=field_missing",
                self.scope_id.name,
                self.target_model,
            )
            return []
        return domain

    def _domain_applies_to_target(self, domain):
        self.ensure_one()
        Model = self.env[self.target_model]
        for leaf in domain:
            if not isinstance(leaf, (list, tuple)) or len(leaf) < 3:
                continue
            field_expr = leaf[0]
            if not isinstance(field_expr, str):
                continue
            name = field_expr.split(".", 1)[0].split(":", 1)[0]
            if name and name not in Model._fields:
                return False
        return True

    def _applies_to_section(self, section):
        self.ensure_one()
        flag = SECTION_APPLY_FLAG.get(section)
        return bool(flag and getattr(self, flag, False))


class DashboardBlueprintPanel(models.Model):
    _inherit = "dashboard.blueprint"

    def _panel_viewer(self):
        """Blueprint whose gear prefs drive My / panel filters for this card."""
        self.ensure_one()
        key = self.env.context.get("dashboard_blueprint_key")
        if key and key != self.key:
            other = self._get_blueprint(key)
            if other:
                return other
        return self

    def _domain_leaves_apply_to_model(self, domain, model_name):
        if not domain:
            return True
        if not model_name or model_name not in self.env:
            return False
        Model = self.env[model_name]
        for leaf in domain:
            if not isinstance(leaf, (list, tuple)) or len(leaf) < 3:
                continue
            field_expr = leaf[0]
            if not isinstance(field_expr, str):
                continue
            name = field_expr.split(".", 1)[0].split(":", 1)[0]
            if name and name not in Model._fields:
                return False
        return True

    def _chosen_restrict_scopes(self):
        self.ensure_one()
        available = self.scope_ids.filtered(lambda s: s.mode == "restrict")
        if not available:
            return available
        pref = self._current_pref()
        if pref:
            return pref.scope_ids & available
        return available.filtered("default_on")

    def _resolved_scope_targets(self):
        """Active target maps for ticked restrict scopes (cached per request)."""
        self.ensure_one()
        cache = self.env.cr.cache.setdefault("dashboard_scope_targets", {})
        key = (self.id, self.env.uid, self.env.company.id)
        if key in cache:
            return cache[key]
        Target = self.env["dashboard.blueprint.scope.target"]
        rows = Target.browse()
        for scope in self._chosen_restrict_scopes():
            rows |= scope.target_ids.filtered(lambda t: t._modules_ok())
        cache[key] = rows
        return rows

    def _all_scope_targets(self):
        self.ensure_one()
        cache = self.env.cr.cache.setdefault("dashboard_scope_targets_all", {})
        if self.id in cache:
            return cache[self.id]
        rows = self.scope_ids.filtered(lambda s: s.mode == "restrict").mapped(
            "target_ids"
        )
        cache[self.id] = rows
        return rows

    def _scope_target_for(self, model_name, section=None, active_my_only=False):
        """Best map row for ``model_name``.

        ``active_my_only=True`` limits to maps under currently ticked My
        scopes (for My domain). Period/custom remap uses all configured maps
        so gear months still work when My is off.
        """
        self.ensure_one()
        rows = (
            self._resolved_scope_targets()
            if active_my_only
            else self._all_scope_targets().filtered(lambda t: t._modules_ok())
        )
        for target in rows:
            if target.target_model != model_name:
                continue
            if section and not target._applies_to_section(section):
                continue
            return target
        return self.env["dashboard.blueprint.scope.target"]

    def _has_active_commercial_map(self, model_name=None):
        """True when a map exists and (for cross-app) a share peer is present."""
        self.ensure_one()
        # Bust stale request cache after share-link / seed writes in same txn.
        self.env.cr.cache.pop("dashboard_scope_targets_all", None)
        self.env.cr.cache.pop("dashboard_scope_targets", None)
        targets = self._all_scope_targets().filtered(lambda t: t._modules_ok())
        if model_name:
            targets = targets.filtered(lambda t: t.target_model == model_name)
        if not targets:
            return False
        if model_name and model_name == self.graph_model:
            return True
        peers = self._share_component() - self
        if not peers:
            return False
        if model_name == "sale.order":
            return bool(
                peers.filtered(
                    lambda b: b.graph_model == "sale.order"
                    or "sale" in (b.module_depends or "")
                    or "sale" in (b.key or "")
                )
            )
        return True

    def _restrict_scope_domain_for_model(self, model_name, section=None):
        self.ensure_one()
        if not model_name:
            return []
        if model_name == self.graph_model:
            return self._restrict_scope_domain()
        # My domain only when a restrict scope is actually ticked.
        target = self._scope_target_for(
            model_name, section=section, active_my_only=True
        )
        if target:
            return target._target_domain()
        domain = self._restrict_scope_domain()
        if (
            domain
            and self._domain_leaves_apply_to_model(domain, model_name)
            and any(
                peer.graph_model == model_name
                for peer in (self._share_component() - self)
            )
        ):
            return list(domain)
        if domain and model_name != self.graph_model:
            _logger.info(
                "dashboard_engine skip restrict model=%s blueprint=%s "
                "reason=no_map_or_fields",
                model_name,
                self.key,
            )
        return []

    def _panel_domain_for_model(self, model_name, section=None):
        """Period + custom + My for commercial surfaces (include scopes out)."""
        self.ensure_one()
        parts = []
        my = self._restrict_scope_domain_for_model(model_name, section=section)
        if my:
            parts.append(my)
        # Period/custom need a configured map (or same graph model) even if My off.
        has_map = model_name == self.graph_model or bool(
            self._scope_target_for(model_name, section=section, active_my_only=False)
        )
        pref = self._current_pref()
        if pref and has_map:
            period = pref._panel_period_domain_for_model(model_name)
            if period:
                parts.append(period)
            custom = pref._panel_custom_domain_for_model(model_name)
            if custom:
                parts.append(custom)
        parts = [p for p in parts if p]
        if not parts:
            return []
        if len(parts) == 1:
            return list(parts[0])
        return list(fields.Domain.AND(parts))

    def _slot_panel_domain(self, slot):
        self.ensure_one()
        if slot._slot_follows_panel_filters():
            model = slot._panel_target_model()
            return self._panel_domain_for_model(model, section=slot.section)
        if slot._slot_follows_my():
            model = slot._panel_target_model()
            return self._restrict_scope_domain_for_model(model, section=slot.section)
        return []

    def _auto_accept_scope_targets_for_share(self):
        """On share-link write: seed high-confidence CRM↔Sales maps."""
        for rec in self:
            component = rec._share_component()
            sale_peers = component.filtered(lambda b: b.graph_model == "sale.order")
            crm_peers = component.filtered(lambda b: b.graph_model == "crm.lead")
            if not (sale_peers and crm_peers):
                continue
            for bp in crm_peers:
                for scope in bp.scope_ids.filtered(lambda s: s.mode == "restrict"):
                    if not scope._domain_applies_to_model("crm.lead"):
                        continue
                    self._ensure_scope_target(
                        scope,
                        "crm.lead",
                        domain=scope.domain or "[('user_id', '=', uid)]",
                        period_field="create_date",
                        period_closed_field="date_closed",
                    )
                    if self._modules_installed_static("sale"):
                        self._ensure_scope_target(
                            scope,
                            "sale.order",
                            domain="[('user_id', '=', uid)]",
                            module_depends="sale",
                            period_field="date_order",
                        )

    @api.model
    def _ensure_scope_target(
        self,
        scope,
        target_model,
        domain,
        module_depends=False,
        period_field=False,
        period_closed_field=False,
    ):
        Target = self.env["dashboard.blueprint.scope.target"].sudo()
        existing = scope.target_ids.filtered(
            lambda t: t.target_model == target_model
        )[:1]
        if existing:
            vals = {}
            if period_field and not existing.period_field:
                vals["period_field"] = period_field
            if period_closed_field and not existing.period_closed_field:
                vals["period_closed_field"] = period_closed_field
            if vals:
                existing.write(vals)
            return existing
        return Target.create(
            {
                "scope_id": scope.id,
                "target_model": target_model,
                "domain": domain,
                "module_depends": module_depends or False,
                "period_field": period_field or False,
                "period_closed_field": period_closed_field or False,
                "apply_kpi": True,
                "apply_bottom": True,
                "apply_views": True,
                "apply_reports": True,
                "apply_menu_new": False,
            }
        )

    def studio_suggest_scope_targets(self, scope_id):
        """Ranked map suggestions for Studio (Phase 3)."""
        self.ensure_one()
        scope = self.env["dashboard.blueprint.scope"].browse(scope_id).exists()
        if not scope or scope.blueprint_id != self:
            return []
        host = self.host_model_name
        suggestions = []
        for model_name in self.env:
            Model = self.env[model_name]
            if not hasattr(Model, "_fields"):
                continue
            link_fields = [
                name
                for name, field in Model._fields.items()
                if getattr(field, "type", None) == "many2one"
                and getattr(field, "comodel_name", None) == host
            ]
            if not link_fields:
                continue
            assignee = next(
                (f for f in ASSIGNEE_FIELD_CANDIDATES if f in Model._fields),
                False,
            )
            if not assignee:
                continue
            score = 100 if model_name in ("crm.lead", "sale.order") else 50
            create_field = next(
                (
                    f
                    for f in ("create_date", "date_order", "date")
                    if f in Model._fields
                ),
                False,
            )
            suggestions.append(
                {
                    "target_model": model_name,
                    "domain": "[('%s', '=', uid)]" % assignee,
                    "period_field": create_field or False,
                    "link_fields": link_fields,
                    "score": score,
                    "already_mapped": bool(
                        scope.target_ids.filtered(
                            lambda t, m=model_name: t.target_model == m
                        )
                    ),
                }
            )
        suggestions.sort(key=lambda row: (-row["score"], row["target_model"]))
        return suggestions[:40]

    def _seed_crm_scope_target_defaults(self):
        """Ensure CRM / 360 My scopes have commercial (+ optional) maps."""
        mine_refs = (
            "crm_customer_dashboard.scope_crm_mine",
            "customer_360_dashboard.scope_c360_mine",
            "crm_salesperson_dashboard.scope_crm_sp_mine",
        )
        for xmlid in mine_refs:
            mine = self.env.ref(xmlid, raise_if_not_found=False)
            if not mine:
                continue
            self._ensure_scope_target(
                mine,
                "crm.lead",
                domain=mine.domain or "[('user_id', '=', uid)]",
                period_field="create_date",
                period_closed_field="date_closed",
            )
            if self._modules_installed_static("sale"):
                self._ensure_scope_target(
                    mine,
                    "sale.order",
                    domain="[('user_id', '=', uid)]",
                    module_depends="sale",
                    period_field="date_order",
                )
            # Website orders share sale.order; invoice map when accounting present.
            if (
                self._modules_installed_static("account")
                and "account.move" in self.env
            ):
                Move = self.env["account.move"]
                assignee = (
                    "invoice_user_id"
                    if "invoice_user_id" in Move._fields
                    else ("user_id" if "user_id" in Move._fields else False)
                )
                if assignee:
                    self._ensure_scope_target(
                        mine,
                        "account.move",
                        domain=(
                            "[('%s', '=', uid), ('move_type', 'in', "
                            "('out_invoice', 'out_refund'))]" % assignee
                        ),
                        module_depends="account",
                        period_field=(
                            "invoice_date"
                            if "invoice_date" in Move._fields
                            else "date"
                        ),
                    )
            if (
                self._modules_installed_static("calendar")
                and "calendar.event" in self.env
                and "user_id" in self.env["calendar.event"]._fields
            ):
                self._ensure_scope_target(
                    mine,
                    "calendar.event",
                    domain="[('user_id', '=', uid)]",
                    module_depends="calendar",
                    period_field="start",
                )
        self._seed_meetings_follow_my_defaults()

    def _seed_meetings_follow_my_defaults(self):
        """Opt Meetings bottoms into My (Studio when-My without Studio click)."""
        for xmlid in (
            "crm_salesperson_dashboard.slot_crm_sp_bottom_meetings",
            "crm_customer_dashboard.slot_crm_bottom_meetings",
        ):
            slot = self.env.ref(xmlid, raise_if_not_found=False)
            if not slot:
                continue
            vals = {}
            if not slot.panel_follow_my:
                vals["panel_follow_my"] = True
            # Customer meetings use host meeting_count; set action model so
            # clicks can honour mapped My on calendar.event.
            if (
                not slot.compute_model
                and not slot.action_model
                and "calendar.event" in self.env
            ):
                vals["action_model"] = "calendar.event"
            if vals:
                slot.write(vals)


class DashboardBlueprintScopePanel(models.Model):
    _inherit = "dashboard.blueprint.scope"

    target_ids = fields.One2many(
        "dashboard.blueprint.scope.target",
        "scope_id",
        string="Target Maps",
        help="Cross-model My / panel filter maps for linked commercial surfaces.",
    )

    @api.depends(
        "name",
        "description",
        "label_ids.sequence",
        "label_ids.name",
        "label_ids.description",
        "label_ids.module_depends",
        "target_ids.target_model",
        "target_ids.module_depends",
        "blueprint_id.share_link_ids",
        "blueprint_id.graph_model",
    )
    def _compute_presentation(self):
        for rec in self:
            presented = rec._presentation()
            rec.display_label = presented["name"]
            rec.display_description = presented["description"]

    def _presentation(self):
        """Resolve label / help; Sales wording only when linked + mapped."""
        self.ensure_one()
        best = self.env["dashboard.blueprint.scope.label"]
        best_score = -1
        bp = self.blueprint_id
        sales_linked = bool(bp and bp._has_active_commercial_map("sale.order"))
        for label in self.label_ids:
            depends = label.module_depends or ""
            if not self.env["dashboard.blueprint"]._modules_installed_static(depends):
                continue
            deps = {n.strip() for n in depends.split(",") if n.strip()}
            if "sale" in deps and not sales_linked:
                continue
            module_count = len(deps)
            score = (module_count * 1000) + (label.sequence or 0)
            if score >= best_score:
                best = label
                best_score = score
        return {
            "name": (best.name if best else None) or self.name,
            "description": (
                (best.description if best else None) or self.description or ""
            ),
        }


class DashboardBlueprintSlotPanel(models.Model):
    _inherit = "dashboard.blueprint.slot"

    panel_follow_my = fields.Boolean(
        string="Follow My when active",
        default=False,
        help="Odd surfaces (Meetings, Deliveries, …): when on, apply the "
        "viewer's My domain if a map or same-leaf apply is available.",
    )
    panel_follow_filters = fields.Boolean(
        string="Follow panel filters when active",
        default=False,
        help="Odd surfaces: when on, also apply gear period + custom filter "
        "(mapped fields only).",
    )

    def _panel_viewer(self):
        self.ensure_one()
        key = self.env.context.get("dashboard_blueprint_key")
        if key:
            bp = self.env["dashboard.blueprint"]._get_blueprint(key)
            if bp:
                return bp
        return self.blueprint_id

    def _panel_target_model(self):
        self.ensure_one()
        return self.compute_model or self.action_model or False

    def _slot_follows_my(self):
        self.ensure_one()
        if self.section == "menu_new":
            return False
        model = self._panel_target_model()
        if not model:
            return False
        viewer = self._panel_viewer()
        if self.section not in PANEL_MY_SECTIONS and not self.panel_follow_my:
            return False
        if model == viewer.graph_model:
            return self.section in PANEL_MY_SECTIONS or self.panel_follow_my
        target = viewer._scope_target_for(model, section=self.section)
        if target:
            return True
        if self.panel_follow_my:
            return bool(
                viewer._restrict_scope_domain_for_model(model, section=self.section)
            )
        if self.section == "kpi" and self.blueprint_id in viewer._share_component():
            return bool(
                viewer._restrict_scope_domain_for_model(model, section=self.section)
            )
        return False

    def _slot_follows_panel_filters(self):
        self.ensure_one()
        if self.section == "menu_new":
            return False
        model = self._panel_target_model()
        if not model:
            return False
        viewer = self._panel_viewer()
        if model == viewer.graph_model and self.section in PANEL_MY_SECTIONS:
            return True
        if viewer._scope_target_for(model, section=self.section):
            return True
        return bool(self.panel_follow_filters)

    def _honours_restrict_scope(self):
        """Product B′: My applies to commercial surfaces (mapped / same model)."""
        return self._slot_follows_my()

    def _aggregate_fingerprint(self, records):
        """Stable key for page-level read_group reuse (Phase 5).

        Slots that share model + link + compute domain + panel domain +
        aggregators can reuse one batch result. Host-field-only slots
        (no compute_model) return falsy so they stay independent.
        """
        self.ensure_one()
        if not self.compute_model or self.compute_model not in self.env:
            return False
        path_str, _source = self._resolve_slot_path_string()
        relate = path_str or self.relate_field or self.blueprint_id.graph_data_field
        viewer = self._panel_viewer()
        panel = tuple(
            (leaf if isinstance(leaf, str) else tuple(leaf))
            for leaf in (viewer._slot_panel_domain(self) or [])
        )
        aggregates = []
        if self._wants_count() or not self._wants_amount():
            aggregates.append(self.compute_aggregator or "__count")
        if self._wants_amount() and self.amount_aggregator:
            aggregates.append(self.amount_aggregator)
        return (
            self.compute_model,
            relate or False,
            (self.compute_domain or "").strip(),
            panel,
            tuple(aggregates),
            self.value_mode or "count",
            bool(self.blueprint_id._hierarchy_enabled()),
            tuple(records.ids),
        )


class DashboardUserPrefPanel(models.Model):
    _inherit = "dashboard.user.pref"

    def _panel_period_domain_for_model(self, model_name):
        self.ensure_one()
        bp = self.blueprint_id
        if model_name == (self.graph_model or bp.graph_model):
            return self._period_domain()
        target = bp._scope_target_for(model_name)
        if not target:
            return []
        lines = self.period_line_ids.sorted("sequence")
        ranges = []
        if lines:
            # Scope targets still map only two peer fields (index 0 / 1).
            open_line = lines[0] if len(lines) > 0 else False
            closed_line = lines[1] if len(lines) > 1 else False
            if (
                target.period_field
                and open_line
                and (open_line.period_mq_ids or open_line.period_year_ids)
            ):
                ranges += self._period_ranges_for_name(
                    target.period_field,
                    open_line.period_mq_ids,
                    open_line.period_year_ids,
                )
            if (
                target.period_closed_field
                and closed_line
                and (closed_line.period_mq_ids or closed_line.period_year_ids)
            ):
                ranges += self._period_ranges_for_name(
                    target.period_closed_field,
                    closed_line.period_mq_ids,
                    closed_line.period_year_ids,
                )
        else:
            if target.period_field and (self.period_mq_ids or self.period_year_ids):
                ranges += self._period_ranges_for_name(
                    target.period_field,
                    self.period_mq_ids,
                    self.period_year_ids,
                )
            if target.period_closed_field and (
                self.period_closed_mq_ids or self.period_closed_year_ids
            ):
                ranges += self._period_ranges_for_name(
                    target.period_closed_field,
                    self.period_closed_mq_ids,
                    self.period_closed_year_ids,
                )
        if not ranges:
            return []
        combine = (
            fields.Domain.AND if self.period_operator == "all" else fields.Domain.OR
        )
        return list(combine(ranges))

    def _period_ranges_for_name(self, field_name, mq_ids, year_ids):
        self.ensure_one()
        if not field_name or not year_ids:
            return []
        tz_offset = self.env.context.get("webclient_tz_offset", 0)
        ranges = []
        months = mq_ids.mapped("name")
        for year_key in year_ids.mapped("name"):
            year = get_period_year().get(year_key)
            if year is None:
                continue
            for start, end in _get_period_dates(year, months):
                leaves = _date_range_to_domain(field_name, start, end, tz_offset)
                ranges.append(list(fields.Domain.AND(leaves)))
        return ranges

    def _panel_custom_domain_for_model(self, model_name):
        self.ensure_one()
        try:
            domain = list(safe_eval(self.custom_filter or "[]"))
        except Exception:
            _logger.warning(
                "Dashboard engine: unreadable custom filter on preference %s",
                self.id,
                exc_info=True,
            )
            return []
        if not domain:
            return []
        if model_name == self.blueprint_id.graph_model:
            return domain
        if model_name not in self.env:
            return []
        graph_model = self.blueprint_id.graph_model
        Src = self.env[graph_model] if graph_model in self.env else None
        Dst = self.env[model_name]
        out = []
        for leaf in domain:
            if isinstance(leaf, str):
                out.append(leaf)
                continue
            if not isinstance(leaf, (list, tuple)) or len(leaf) < 3:
                out.append(leaf)
                continue
            field_expr = leaf[0]
            if not isinstance(field_expr, str):
                continue
            name = field_expr.split(".", 1)[0].split(":", 1)[0]
            if name not in Dst._fields:
                _logger.info(
                    "dashboard_engine skip custom leaf field=%s model=%s "
                    "reason=missing",
                    name,
                    model_name,
                )
                continue
            if (
                Src is not None
                and name in Src._fields
                and Dst._fields[name].type != Src._fields[name].type
            ):
                _logger.info(
                    "dashboard_engine skip custom leaf field=%s model=%s "
                    "reason=ttype_mismatch",
                    name,
                    model_name,
                )
                continue
            out.append(leaf)
        if out and not self.blueprint_id._domain_leaves_apply_to_model(out, model_name):
            return []
        return out
