# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    from odoo.addons.dashboard_engine.hooks import (
        purge_generated_dashboard_artifacts,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    env["dashboard.blueprint"]._gc_orphan_generated_artifacts()
    installed = env["ir.module.module"].search(
        [
            ("name", "=", "crm_customer_dashboard"),
            ("state", "=", "installed"),
        ]
    )
    if not installed:
        purge_generated_dashboard_artifacts(env, keys=("crm_customers",))
