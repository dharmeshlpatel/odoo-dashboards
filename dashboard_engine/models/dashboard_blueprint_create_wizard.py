# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Blank dashboard wizard (Wave E)."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DashboardBlueprintCreateWizard(models.TransientModel):
    _name = "dashboard.blueprint.create.wizard"
    _description = "Create Dashboard Blueprint"

    name = fields.Char(required=True, default="My Dashboard", string="Name")
    host_model_id = fields.Many2one(
        "ir.model",
        string="Host Model",
        required=True,
        domain="[('transient', '=', False)]",
        help="Model of each card (e.g. Contact, User).",
    )
    key = fields.Char(
        string="Technical Key",
        help="Leave empty to generate from the name.",
    )
    open_studio = fields.Boolean(
        string="Open Studio After Create",
        default=True,
    )

    @api.onchange("name")
    def _onchange_name_key(self):
        if self.name and not self.key:
            # Mirror blueprint create suggestion lightly for UX.
            suggestion = "".join(
                ch if ch.isalnum() else "_" for ch in (self.name or "").lower()
            )
            self.key = "_".join(part for part in suggestion.split("_") if part)[:64]

    def action_create(self):
        self.ensure_one()
        if not self.host_model_id:
            raise UserError(_("Choose a host model."))
        vals = {
            "name": self.name,
            "host_model_id": self.host_model_id.id,
            "state": "draft",
            "primary_button_label": _("Open"),
            "graph_caption": self.name,
            "header_title_field": "display_name",
        }
        if self.key:
            vals["key"] = self.key
        blueprint = self.env["dashboard.blueprint"].create(vals)
        # Seed a starter KPI so Studio is not empty.
        host = self.host_model_id.model
        self.env["dashboard.blueprint.slot"].create(
            {
                "blueprint_id": blueprint.id,
                "section": "kpi",
                "sequence": 10,
                "key": "starter_kpi",
                "name": _("Items"),
                "label": _("Item"),
                "label_plural": _("Items"),
                "compute_model": host,
                "compute_domain": "[]",
                "action_model": host,
                "show_if_zero": True,
                "value_mode": "count",
            }
        )
        if self.open_studio:
            return blueprint.action_open_studio()
        return {
            "type": "ir.actions.act_window",
            "res_model": "dashboard.blueprint",
            "res_id": blueprint.id,
            "views": [(False, "form")],
            "target": "current",
        }
