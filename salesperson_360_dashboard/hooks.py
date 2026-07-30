# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

"""Salesperson 360 pack install hooks."""

USERS_SALESPERSON_BLUEPRINT_XMLIDS = (
    "crm_salesperson_dashboard.blueprint_crm_salespersons",
    "sales_salesperson_dashboard.blueprint_sales_salespersons",
    "salesperson_360_dashboard.blueprint_salesperson_360",
)


def link_salesperson_share_pool(env):
    """Link CRM / Sales salesperson + 360 hub into one share pool."""
    bps = []
    for xid in USERS_SALESPERSON_BLUEPRINT_XMLIDS:
        bp = env.ref(xid, raise_if_not_found=False)
        if bp:
            bps.append(bp)
    if len(bps) < 2:
        return
    for bp in bps:
        others = [other.id for other in bps if other.id != bp.id]
        bp.sudo().write({"share_link_ids": [(6, 0, others)]})


def post_init_hook(env):
    bp = env.ref(
        "salesperson_360_dashboard.blueprint_salesperson_360",
        raise_if_not_found=False,
    )
    if bp and bp.state != "published":
        bp.sudo().action_publish()
    elif bp:
        bp.sudo()._sync_generated_artifacts()
    link_salesperson_share_pool(env)
