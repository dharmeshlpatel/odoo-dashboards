# -*- coding: utf-8 -*-
"""Map header line kind left/right → inline + alignment; default alignment."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_blueprint_header_item
           SET alignment = COALESCE(alignment, 'left')
         WHERE alignment IS NULL OR alignment = ''
        """
    )
    cr.execute(
        """
        UPDATE dashboard_blueprint_header_item
           SET kind = 'inline', alignment = 'left'
         WHERE kind = 'left'
        """
    )
    left_n = cr.rowcount
    cr.execute(
        """
        UPDATE dashboard_blueprint_header_item
           SET kind = 'inline', alignment = 'right'
         WHERE kind = 'right'
        """
    )
    right_n = cr.rowcount
    cr.execute(
        """
        UPDATE dashboard_blueprint_header_item
           SET kind = 'subtitle', alignment = COALESCE(NULLIF(alignment, ''), 'left')
         WHERE kind = 'subtitle'
        """
    )
    subtitle_n = cr.rowcount
    _logger.info(
        "header-kind-alignment: left→inline=%s, right→inline=%s, subtitle=%s",
        left_n,
        right_n,
        subtitle_n,
    )
