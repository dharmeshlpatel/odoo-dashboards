# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

OWN = (
    "crm_attribution_dashboard.blueprint_crm_campaigns",
    "crm_attribution_dashboard.blueprint_crm_mediums",
    "crm_attribution_dashboard.blueprint_crm_sources",
)
SHARE_GROUPS = (
    ("crm_attribution_dashboard.blueprint_crm_campaigns", "sales_attribution_dashboard.blueprint_sales_campaigns"),
    ("crm_attribution_dashboard.blueprint_crm_mediums", "sales_attribution_dashboard.blueprint_sales_mediums"),
    ("crm_attribution_dashboard.blueprint_crm_sources", "sales_attribution_dashboard.blueprint_sales_sources"),
)


def link_share_pool(env):
    for group in SHARE_GROUPS:
        bps = [env.ref(x, raise_if_not_found=False) for x in group]
        bps = [b for b in bps if b]
        if len(bps) < 2:
            continue
        for bp in bps:
            others = [o.id for o in bps if o.id != bp.id]
            bp.sudo().write({"share_link_ids": [(6, 0, others)]})


def post_init_hook(env):
    for xid in OWN:
        bp = env.ref(xid, raise_if_not_found=False)
        if bp and bp.state != "published":
            bp.sudo().action_publish()
        elif bp:
            bp.sudo()._sync_generated_artifacts()
    link_share_pool(env)
