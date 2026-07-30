# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.invoice_customer_dashboard.hooks import (
        _dedupe_overdue_amount_display,
        link_partner_customer_share_pool,
    )

    _dedupe_overdue_amount_display(env)
    link_partner_customer_share_pool(env)
    bp = env.ref(
        "invoice_customer_dashboard.blueprint_invoice_customers",
        raise_if_not_found=False,
    )
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
