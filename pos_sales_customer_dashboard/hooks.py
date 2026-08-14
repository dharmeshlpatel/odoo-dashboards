# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    bp = env.ref(
        "pos_sales_customer_dashboard.blueprint_pos_customers",
        raise_if_not_found=False,
    )
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()


def uninstall_hook(env):
    return
