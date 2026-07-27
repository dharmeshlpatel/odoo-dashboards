# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

"""CRM Salespersons pack install hooks."""


def post_init_hook(env):
    bp = env.ref(
        "crm_salesperson_dashboard.blueprint_crm_salespersons",
        raise_if_not_found=False,
    )
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
