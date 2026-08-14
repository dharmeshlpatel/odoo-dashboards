# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

"""Customer 360 pack install hooks."""


def drop_local_crm_scopes(env):
    """Remove CRM copies that used to live on Customer 360."""
    leftover = env["dashboard.blueprint.scope"]
    for xmlid in (
        "customer_360_dashboard.scope_c360_pipeline",
        "customer_360_dashboard.scope_c360_leads",
        "customer_360_dashboard.scope_c360_mine",
    ):
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            leftover |= rec
    if leftover:
        leftover.sudo().unlink()
    bp = env.ref(
        "customer_360_dashboard.blueprint_customer_360",
        raise_if_not_found=False,
    )
    if not bp:
        return
    bp.sudo().write(
        {
            "module_depends": False,
            "module_ids": [(5, 0, 0)],
            "primary_action_xmlid": False,
            "primary_action_context": False,
            "primary_button_label": False,
            "graph_model": False,
            "graph_measure": False,
            "graph_groupby": False,
            "graph_caption": False,
        }
    )
    if bp.state == "published":
        bp._sync_generated_artifacts()


def post_init_hook(env):
    drop_local_crm_scopes(env)
    bp = env.ref(
        "customer_360_dashboard.blueprint_customer_360",
        raise_if_not_found=False,
    )
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()


def uninstall_hook(env):
    return
