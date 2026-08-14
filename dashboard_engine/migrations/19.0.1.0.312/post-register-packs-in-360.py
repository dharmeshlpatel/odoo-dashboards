# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.dashboard_engine.share_pools import (
        link_partner_customer_share_pool,
    )

    link_partner_customer_share_pool(env)
    crm = env.ref(
        "crm_customer_dashboard.blueprint_crm_customers",
        raise_if_not_found=False,
    )
    if crm and crm.state == "published":
        crm._sync_generated_artifacts()
