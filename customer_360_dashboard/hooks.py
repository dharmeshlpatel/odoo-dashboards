# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

"""Customer 360 pack install hooks."""

PARTNER_CUSTOMER_BLUEPRINT_XMLIDS = (
    "crm_customer_dashboard.blueprint_crm_customers",
    "sales_customer_dashboard.blueprint_sales_customers",
    "invoice_customer_dashboard.blueprint_invoice_customers",
    "customer_360_dashboard.blueprint_customer_360",
)


def link_partner_customer_share_pool(env):
    """Link all installed partner-customer blueprints into one share pool."""
    bps = []
    for xid in PARTNER_CUSTOMER_BLUEPRINT_XMLIDS:
        bp = env.ref(xid, raise_if_not_found=False)
        if bp:
            bps.append(bp)
    if len(bps) < 2:
        return
    for bp in bps:
        others = [other.id for other in bps if other.id != bp.id]
        bp.sudo().write({"share_link_ids": [(6, 0, others)]})


def post_init_hook(env):
    link_partner_customer_share_pool(env)
    bp = env.ref(
        "customer_360_dashboard.blueprint_customer_360",
        raise_if_not_found=False,
    )
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
