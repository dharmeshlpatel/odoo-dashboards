# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

"""Vendor Bills pack — standalone (no customer share pool)."""


def post_init_hook(env):
    bp = env.ref(
        "vendor_bills_dashboard.blueprint_vendor_bills",
        raise_if_not_found=False,
    )
    if bp and bp.state != "published":
        bp.sudo().action_publish()
    elif bp:
        bp.sudo()._sync_generated_artifacts()
