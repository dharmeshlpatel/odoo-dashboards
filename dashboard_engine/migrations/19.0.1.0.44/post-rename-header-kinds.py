# -*- coding: utf-8 -*-
"""Map legacy header line kinds detail→left and tags→right."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_blueprint_header_item
           SET kind = 'left'
         WHERE kind = 'detail'
        """
    )
    left_n = cr.rowcount
    cr.execute(
        """
        UPDATE dashboard_blueprint_header_item
           SET kind = 'right'
         WHERE kind = 'tags'
        """
    )
    right_n = cr.rowcount
    _logger.info(
        "rename-header-kinds: detail→left=%s, tags→right=%s", left_n, right_n
    )
