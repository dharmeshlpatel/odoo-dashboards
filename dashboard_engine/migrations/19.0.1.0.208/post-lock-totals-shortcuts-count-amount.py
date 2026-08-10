# -*- coding: utf-8 -*-
"""Totals and Shortcuts always use Count + Amount (Shows is KPI-only)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_blueprint_slot
           SET value_mode = 'count_amount'
         WHERE section IN ('button_box', 'bottom')
           AND COALESCE(value_mode, '') != 'count_amount'
        """
    )
    _logger.info(
        "locked totals/shortcuts to count_amount: %s row(s)", cr.rowcount
    )
