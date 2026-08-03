# -*- coding: utf-8 -*-
"""Assign existing hub groups to the default hub and resync menus."""


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    default_hub = env.ref(
        "dashboard_engine.dashboard_hub_default", raise_if_not_found=False
    )
    if default_hub:
        env["dashboard.blueprint.group"].sudo().search(
            [("hub_menu_id", "=", False)]
        ).write({"hub_menu_id": default_hub.id})
    for hub in env["dashboard.blueprint.hub"].sudo().search([]):
        hub._sync_generated_artifacts()
    for bp in env["dashboard.blueprint"].sudo().search([("state", "=", "published")]):
        bp._sync_generated_artifacts()
    for hub in env["dashboard.blueprint.hub"].sudo().search([]):
        hub._sync_generated_artifacts()
