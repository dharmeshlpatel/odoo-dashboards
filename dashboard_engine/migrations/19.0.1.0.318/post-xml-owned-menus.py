# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    from odoo.addons.dashboard_engine.share_pools import (
        PARTNER_CUSTOMER_HUB_XMLID,
        PARTNER_CUSTOMER_SPOKE_XMLIDS,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    hub = env.ref(
        "dashboard_engine.dashboard_hub_default", raise_if_not_found=False
    )
    menu = env.ref(
        "dashboard_engine.menu_dashboards_360", raise_if_not_found=False
    )
    action = env.ref(
        "dashboard_engine.action_dashboard_hub", raise_if_not_found=False
    )
    if hub and menu and action:
        hub.with_context(skip_hub_menu_sync=True).write(
            {
                "is_root_app": False,
                "generated_menu_id": menu.id,
                "generated_action_id": action.id,
            }
        )
        action.write(
            {
                "name": "Dashboards 360",
                "context": "{'hub_menu_id': %d}" % hub.id,
            }
        )
    env["dashboard.blueprint"]._attach_compose_hubs_to_360_app()
    hub_bp = env.ref(PARTNER_CUSTOMER_HUB_XMLID, raise_if_not_found=False)
    if hub_bp:
        commands = []
        for xmlid in PARTNER_CUSTOMER_SPOKE_XMLIDS:
            spoke = env.ref(xmlid, raise_if_not_found=False)
            if not spoke:
                continue
            commands.append((4, spoke.id))
            if hub_bp not in spoke.share_link_ids:
                spoke.with_context(skip_share_sync=True).write(
                    {"share_link_ids": [(4, hub_bp.id)]}
                )
        if commands:
            hub_bp.with_context(skip_share_sync=True).write(
                {"share_link_ids": commands}
            )
    for bp in env["dashboard.blueprint"].search([("state", "=", "published")]):
        bp._sync_generated_artifacts()
    env["dashboard.blueprint"]._gc_orphan_generated_artifacts()
