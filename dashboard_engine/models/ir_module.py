# -*- coding: utf-8 -*-

from odoo import models, api


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    def _installed_module_domain(self, module_name):
        return [("name", "=", module_name), ("state", "=", "installed")]

    @api.model
    def _is_module_installed(self, module_name):
        domain = self._installed_module_domain(module_name)
        return bool(self.sudo().search_count(domain))

    def write(self, vals):
        removing = self.filtered(
            lambda m: vals.get("state") in ("to remove", "uninstalled")
        )
        removed_names = removing.mapped("name")
        res = super().write(vals)
        if removed_names and "dashboard.blueprint" in self.env:
            Blueprint = self.env["dashboard.blueprint"].sudo()
            Blueprint._gc_orphan_generated_artifacts()
        if (
            self.env.context.get("install_mode")
            or self.env.context.get("module")
            or not self.env.registry.ready
        ):
            return res
        if vals.get("state") in ("installed", "uninstalled", "to remove"):
            if "dashboard.blueprint" in self.env:
                Blueprint = self.env["dashboard.blueprint"].sudo()
                for bp in Blueprint.search([]):
                    bp._sync_generated_artifacts()
                from odoo.addons.dashboard_engine import _ensure_warehouse_blueprint

                _ensure_warehouse_blueprint(self.env)
        return res
