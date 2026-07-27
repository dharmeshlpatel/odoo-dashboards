# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

"""CRM Customers pack install hooks."""


def _link_crm_sales_share(env):
    """Phase A: CRM Customers <-> Sales Customers share pool (optional peer)."""
    crm = env.ref(
        "crm_customer_dashboard.blueprint_crm_customers",
        raise_if_not_found=False,
    )
    sale = env.ref(
        "sales_customer_dashboard.blueprint_sales_customers",
        raise_if_not_found=False,
    )
    if not crm or not sale:
        return
    crm.sudo().write({"share_link_ids": [(6, 0, [sale.id])]})
    sale.sudo().write({"share_link_ids": [(6, 0, [crm.id])]})


def post_init_hook(env):
    _link_crm_sales_share(env)
    bp = env.ref(
        "crm_customer_dashboard.blueprint_crm_customers",
        raise_if_not_found=False,
    )
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
