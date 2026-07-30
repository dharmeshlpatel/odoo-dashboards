# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

COMPANY_SHARE = (
    "company_dashboard.blueprint_company_crm",
    "company_dashboard.blueprint_company_sales",
    "company_dashboard.blueprint_company_invoice",
    "company_360_dashboard.blueprint_company_360",
)


def link_share_pool(env):
    bps = [env.ref(x, raise_if_not_found=False) for x in COMPANY_SHARE]
    bps = [b for b in bps if b]
    if len(bps) < 2:
        return
    for bp in bps:
        others = [o.id for o in bps if o.id != bp.id]
        bp.sudo().write({"share_link_ids": [(6, 0, others)]})


def post_init_hook(env):
    bp = env.ref("company_360_dashboard.blueprint_company_360", raise_if_not_found=False)
    if bp and bp.state != "published":
        bp.sudo().action_publish()
    elif bp:
        bp.sudo()._sync_generated_artifacts()
    link_share_pool(env)
