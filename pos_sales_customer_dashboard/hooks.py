# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def _link_pos_website_share(env):
    pos = env.ref(
        "pos_sales_customer_dashboard.blueprint_pos_customers",
        raise_if_not_found=False,
    )
    web = env.ref(
        "website_sales_customer_dashboard.blueprint_website_customers",
        raise_if_not_found=False,
    )
    if not pos or not web:
        return
    pos.sudo().write({"share_link_ids": [(6, 0, [web.id])]})
    web.sudo().write({"share_link_ids": [(6, 0, [pos.id])]})


def post_init_hook(env):
    _link_pos_website_share(env)
    bp = env.ref("pos_sales_customer_dashboard.blueprint_pos_customers", raise_if_not_found=False)
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
