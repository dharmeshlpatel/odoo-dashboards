# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    bp = env.ref("pos_session_dashboard.blueprint_pos_sessions", raise_if_not_found=False)
    if bp and bp.state != "published":
        bp.sudo().action_publish()
    elif bp:
        bp.sudo()._sync_generated_artifacts()
