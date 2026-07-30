# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

"""CRM Salespersons pack install hooks."""

USERS_SALESPERSON_BLUEPRINT_XMLIDS = (
    "crm_salesperson_dashboard.blueprint_crm_salespersons",
    "sales_salesperson_dashboard.blueprint_sales_salespersons",
    "salesperson_360_dashboard.blueprint_salesperson_360",
)


def link_salesperson_share_pool(env):
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
    slot = env.ref(
        "crm_salesperson_dashboard.slot_crm_sp_overdue",
        raise_if_not_found=False,
    )
    if slot and not slot.is_attention_signal:
        slot.sudo().write({"is_attention_signal": True})
    link_salesperson_share_pool(env)
    bp = env.ref(
        "crm_salesperson_dashboard.blueprint_crm_salespersons",
        raise_if_not_found=False,
    )
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
