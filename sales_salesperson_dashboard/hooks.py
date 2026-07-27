# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    bp = env.ref("sales_salesperson_dashboard.blueprint_sales_salespersons", raise_if_not_found=False)
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
