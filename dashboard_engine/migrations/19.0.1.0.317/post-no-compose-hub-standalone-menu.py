# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    hub = env.ref(
        "dashboard_engine.dashboard_hub_default", raise_if_not_found=False
    )
    if hub:
        hub.write({"is_root_app": False, "menu_parent_id": False})
        hub._sync_generated_artifacts()
    env["dashboard.blueprint"]._attach_compose_hubs_to_360_app()
    hubs = env["dashboard.blueprint"].search([("is_compose_hub", "=", True)])
    for bp in hubs:
        bp._purge_generated_menu()
        if bp.menu_parent_id or bp.menu_parent_xmlid:
            bp.with_context(skip_hub_menu_parent_sync=True).write(
                {"menu_parent_id": False, "menu_parent_xmlid": False}
            )
        if bp.state == "published":
            bp._sync_generated_artifacts()
