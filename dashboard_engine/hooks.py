# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

"""Engine install / uninstall helpers.

Generated kanban menus are created in Python, so they are not pack XML.
Uninstall hooks must delete them while the pack is still marked ``to remove``.
At that moment the blueprint record still exists, so orphan-GC would keep them.
"""


def purge_generated_dashboard_artifacts(env, keys=None):
    """Delete generated dashboard views, window actions, and menus.

    ``keys``: blueprint keys such as ``crm_customers``. ``None`` deletes every
    ``dashboard.engine.*`` artifact and hub client actions (engine uninstall).
    """
    View = env["ir.ui.view"].sudo()
    Action = env["ir.actions.act_window"].sudo()
    Menu = env["ir.ui.menu"].sudo()
    actions = Action.browse()
    if keys:
        names = []
        for key in keys:
            names.extend(
                [
                    "dashboard.engine.kanban.%s" % key,
                    "dashboard.engine.search.%s" % key,
                ]
            )
        views = View.search([("name", "in", names)]) if names else View.browse()
        if views:
            actions |= Action.search([("view_id", "in", views.ids)])
        for key in keys:
            needle = '"dashboard_blueprint_key": "%s"' % key
            actions |= Action.search([("context", "ilike", needle)])
    else:
        views = View.search([("name", "=like", "dashboard.engine.%")])
        actions = Action.search(
            [
                "|",
                ("view_id", "in", views.ids or [0]),
                ("context", "ilike", "dashboard_blueprint_key"),
            ]
        )
    action_refs = [
        "ir.actions.act_window,%s" % action_id for action_id in actions.ids
    ]
    menus = Menu.search([("action", "in", action_refs)]) if action_refs else Menu
    hub_menus = Menu.browse()
    clients = env["ir.actions.client"].sudo().browse()
    if not keys:
        clients = env["ir.actions.client"].sudo().search(
            [("tag", "=", "dashboard_engine.hub")]
        )
        client_refs = [
            "ir.actions.client,%s" % client_id for client_id in clients.ids
        ]
        if client_refs:
            hub_menus = Menu.search([("action", "in", client_refs)])
    menus.unlink()
    hub_menus.unlink()
    actions.unlink()
    if clients:
        clients.unlink()
    views.unlink()
    return True


def uninstall_hook(env):
    """Drop leftover generated menus when the engine itself is uninstalled."""
    purge_generated_dashboard_artifacts(env)
