# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class DashboardBlueprintGroup(models.Model):
    _name = "dashboard.blueprint.group"
    _description = "Dashboard Group"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    hub_menu_id = fields.Many2one(
        "dashboard.blueprint.hub",
        string="Hub Menu",
        required=True,
        ondelete="restrict",
        index=True,
        help="Shared menu where this group appears. Several groups can share "
        "the same hub menu; opening it shows all of them together.",
    )
    dashboard_ids = fields.One2many(
        "dashboard.blueprint",
        "group_id",
        string="Dashboards",
    )

    @api.model
    def _default_hub_menu_id(self):
        return self.env.ref(
            "dashboard_engine.dashboard_hub_default", raise_if_not_found=False
        )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "hub_menu_id" in fields_list and not res.get("hub_menu_id"):
            hub = self._default_hub_menu_id()
            if hub:
                res["hub_menu_id"] = hub.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        default_hub = self._default_hub_menu_id()
        for vals in vals_list:
            if not vals.get("hub_menu_id") and default_hub:
                vals["hub_menu_id"] = default_hub.id
        groups = super().create(vals_list)
        groups.mapped("hub_menu_id")._sync_generated_artifacts()
        return groups

    def write(self, vals):
        old_hubs = self.mapped("hub_menu_id")
        res = super().write(vals)
        hubs = old_hubs | self.mapped("hub_menu_id")
        if "hub_menu_id" in vals or "sequence" in vals or "name" in vals:
            hubs._sync_generated_artifacts()
        return res

    def unlink(self):
        hubs = self.mapped("hub_menu_id")
        res = super().unlink()
        hubs._sync_generated_artifacts()
        return res
