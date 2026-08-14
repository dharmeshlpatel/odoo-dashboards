# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    env["dashboard.blueprint"]._attach_compose_hubs_to_360_app()
    from odoo.addons.dashboard_engine.share_pools import (
        link_partner_customer_share_pool,
    )

    link_partner_customer_share_pool(env)
    bp = env.ref(
        "customer_360_dashboard.blueprint_customer_360",
        raise_if_not_found=False,
    )
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
    hub = env.ref(
        "dashboard_engine.dashboard_hub_default", raise_if_not_found=False
    )
    if hub:
        hub._sync_generated_artifacts()
