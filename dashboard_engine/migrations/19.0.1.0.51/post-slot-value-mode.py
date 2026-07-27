# -*- coding: utf-8 -*-
"""Backfill slot value_mode (Shows) from existing amount/count sources."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Count + Amount: remote aggregate or both host fields.
    cr.execute(
        """
        UPDATE dashboard_blueprint_slot
           SET value_mode = 'count_amount'
         WHERE COALESCE(amount_aggregator, '') != ''
            OR (
                COALESCE(count_field, '') != ''
                AND COALESCE(amount_field, '') != ''
            )
        """
    )
    both_n = cr.rowcount
    # Amount only: host amount without count / compute.
    cr.execute(
        """
        UPDATE dashboard_blueprint_slot
           SET value_mode = 'amount'
         WHERE COALESCE(amount_field, '') != ''
           AND COALESCE(count_field, '') = ''
           AND COALESCE(compute_model, '') = ''
           AND COALESCE(amount_aggregator, '') = ''
        """
    )
    amount_n = cr.rowcount
    # Everything else keeps DB default 'count'.
    _logger.info(
        "slot-value-mode: count_amount=%s, amount=%s", both_n, amount_n
    )
