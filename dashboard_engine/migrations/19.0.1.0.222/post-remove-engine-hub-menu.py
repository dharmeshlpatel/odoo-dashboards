# -*- coding: utf-8 -*-
"""Detach default hub from Dashboard Engine app and hide its menu."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    hub = env.ref("dashboard_engine.dashboard_hub_default", raise_if_not_found=False)
    if not hub:
        return
    engine_root = env.ref(
        "dashboard_engine.menu_dashboard_engine_root", raise_if_not_found=False
    )
    vals = {}
    if engine_root and hub.menu_parent_id == engine_root:
        vals["menu_parent_id"] = False
    if vals:
        hub.write(vals)
    else:
        hub._sync_generated_artifacts()
    if hub.generated_menu_id and hub.generated_menu_id.active:
        hub.generated_menu_id.write({"active": False})
    _logger.info(
        "default hub detached from Dashboard Engine (menu_parent=%s, generated=%s)",
        hub.menu_parent_id.id or False,
        hub.generated_menu_id.id if hub.generated_menu_id else False,
    )
