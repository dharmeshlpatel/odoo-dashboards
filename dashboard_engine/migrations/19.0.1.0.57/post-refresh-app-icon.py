# -*- coding: utf-8 -*-
"""Refresh Dashboard Engine app switcher icon after redesign."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    menu = env.ref(
        "dashboard_engine.menu_dashboard_engine_root",
        raise_if_not_found=False,
    )
    if not menu:
        return
    # Re-write web_icon so Odoo reloads static/description/icon.png into web_icon_data.
    menu.write({"web_icon": "dashboard_engine,static/description/icon.png"})
    _logger.info("refreshed Dashboard Engine web_icon (%s bytes)", len(menu.web_icon_data or b""))
