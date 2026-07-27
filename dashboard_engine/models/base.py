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
