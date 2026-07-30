# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.customer_360_dashboard.hooks import (
        link_partner_customer_share_pool,
    )

    link_partner_customer_share_pool(env)
    bp = env.ref(
        "customer_360_dashboard.blueprint_customer_360",
        raise_if_not_found=False,
    )
    if not bp:
        return
    if bp.menu_parent_xmlid != "crm.crm_menu_report":
        bp.sudo().write({"menu_parent_xmlid": "crm.crm_menu_report"})
    if bp.state == "published":
        bp._sync_generated_artifacts()
