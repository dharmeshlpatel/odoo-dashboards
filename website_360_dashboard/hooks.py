# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    bp = env.ref("website_360_dashboard.blueprint_website_360", raise_if_not_found=False)
    if bp and bp.state != "published":
        bp.sudo().action_publish()
    elif bp:
        bp.sudo()._sync_generated_artifacts()
