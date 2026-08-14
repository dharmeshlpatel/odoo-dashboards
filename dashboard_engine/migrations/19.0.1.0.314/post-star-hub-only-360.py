# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.dashboard_engine.share_pools import (
        link_partner_customer_share_pool,
    )

    env["dashboard.blueprint"]._attach_compose_hubs_to_360_app()
    link_partner_customer_share_pool(env)
    for xmlid in (
        "crm_customer_dashboard.blueprint_crm_customers",
        "sales_customer_dashboard.blueprint_sales_customers",
        "customer_360_dashboard.blueprint_customer_360",
    ):
        bp = env.ref(xmlid, raise_if_not_found=False)
        if bp and bp.state == "published":
            bp._sync_generated_artifacts()
