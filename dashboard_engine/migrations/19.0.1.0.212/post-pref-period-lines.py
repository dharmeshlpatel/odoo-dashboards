# -*- coding: utf-8 -*-
"""Lift legacy Open/Closed pref date slots into period_line_ids rows."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Pref = env["dashboard.user.pref"].sudo()
    prefs = Pref.search([])
    lifted = 0
    synced = 0
    for pref in prefs:
        if not pref.period_line_ids and (
            pref.period_field_id or pref.period_closed_field_id
        ):
            pref._lift_legacy_period_to_lines()
            lifted += 1
        # Align labels/order to the active Chart Model Option when present.
        before = pref.period_line_ids.ids
        pref._sync_pref_period_lines()
        if pref.period_line_ids.ids != before:
            synced += 1
    _logger.info(
        "pref period lines: lifted=%s synced=%s of %s pref(s)",
        lifted,
        synced,
        len(prefs),
    )
