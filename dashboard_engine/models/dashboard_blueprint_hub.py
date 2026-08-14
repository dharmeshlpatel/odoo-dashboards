# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class DashboardBlueprintHub(models.Model):
    """Shared menu anchor for one or more hub groups.

    Several ``dashboard.blueprint.group`` records can point at the same hub.
    Opening the generated menu shows all of those groups together in one hub
    screen (left sidebar sections + embedded dashboards).
    """

    _name = "dashboard.blueprint.hub"
    _description = "Dashboard Hub Menu"
    _order = "menu_sequence, name, id"

    name = fields.Char(required=True, translate=True)
    is_root_app = fields.Boolean(
        string="Main App Menu",
        help="Create a top-level item on the Odoo apps screen (no parent). "
        "Used for Dashboards 360.",
    )
    menu_parent_id = fields.Many2one(
        "ir.ui.menu",
        string="Parent Menu",
        ondelete="restrict",
        help="Where this hub menu sits in the Odoo menu tree. "
        "Ignored when Main App Menu is on. "
        "Empty + Main App Menu off = no hub menu is generated.",
    )
    menu_sequence = fields.Integer(default=10, string="Menu Sequence")
    menu_group_ids = fields.Many2many(
        "res.groups",
        "dashboard_blueprint_hub_menu_group_rel",
        "hub_id",
        "group_id",
        string="Menu Visibility",
        help="If set, the generated menu is only visible to these groups. "
        "Empty → Odoo uses action access.",
    )
    menu_web_icon = fields.Char(
        string="Web Icon File",
        help="Optional icon path, e.g. module_name,static/description/icon.png",
    )
    menu_web_icon_data = fields.Binary(
        string="Web Icon Image",
        attachment=True,
    )
    group_ids = fields.One2many(
        "dashboard.blueprint.group",
        "hub_menu_id",
        string="Groups",
    )
    generated_action_id = fields.Many2one(
        "ir.actions.client",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    generated_menu_id = fields.Many2one(
        "ir.ui.menu",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    @api.model_create_multi
    def create(self, vals_list):
        hubs = super().create(vals_list)
        hubs._sync_generated_artifacts()
        return hubs

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_hub_menu_sync"):
            return res
        sync_fields = {
            "name",
            "is_root_app",
            "menu_parent_id",
            "menu_sequence",
            "menu_group_ids",
            "menu_web_icon",
            "menu_web_icon_data",
        }
        if sync_fields.intersection(vals):
            self._sync_generated_artifacts()
        return res

    def unlink(self):
        menus = self.mapped("generated_menu_id")
        actions = self.mapped("generated_action_id")
        res = super().unlink()
        menus.unlink()
        actions.unlink()
        return res

    def _record_has_xmlid(self, record):
        if not record:
            return False
        return bool(
            self.env["ir.model.data"].sudo().search(
                [("model", "=", record._name), ("res_id", "=", record.id)],
                limit=1,
            )
        )

    def _sync_generated_artifacts(self):
        """Update the client action + menu. Do not create XML-owned menus."""
        for hub in self:
            action = hub._upsert_client_action()
            menu = hub._upsert_menu(action)
            hub.with_context(skip_hub_menu_sync=True).write(
                {
                    "generated_action_id": action.id if action else False,
                    "generated_menu_id": menu.id if menu else False,
                }
            )

    def _upsert_client_action(self):
        self.ensure_one()
        Action = self.env["ir.actions.client"].sudo()
        vals = {
            "name": self.name,
            "tag": "dashboard_engine.hub",
            "context": "{'hub_menu_id': %d}" % self.id,
        }
        if self.generated_action_id:
            self.generated_action_id.write(vals)
            return self.generated_action_id
        return Action.create(vals)

    def _upsert_menu(self, action):
        self.ensure_one()
        Menu = self.env["ir.ui.menu"].sudo()
        xml_owned = self._record_has_xmlid(self.generated_menu_id)
        want_menu = self.is_root_app or bool(self.menu_parent_id) or xml_owned
        if not want_menu:
            if self.generated_menu_id and not xml_owned:
                self.generated_menu_id.unlink()
            return Menu.browse()
        if xml_owned:
            self.generated_menu_id.write(
                {
                    "name": self.name,
                    "action": "ir.actions.client,%s" % action.id,
                    "active": True,
                }
            )
            return self.generated_menu_id
        vals = {
            "name": self.name,
            "action": "ir.actions.client,%s" % action.id,
            "parent_id": False if self.is_root_app else self.menu_parent_id.id,
            "sequence": self.menu_sequence,
            "active": True,
            "group_ids": [(6, 0, self.menu_group_ids.ids)],
            "web_icon": self.menu_web_icon or False,
            "web_icon_data": self.menu_web_icon_data or False,
        }
        if self.generated_menu_id:
            self.generated_menu_id.write(vals)
            return self.generated_menu_id
        return Menu.create(vals)

    @api.model
    def _resync_all_menus(self):
        """Refresh every hub menu (visibility + labels). Used after group/bp changes."""
        self.search([])._sync_generated_artifacts()
