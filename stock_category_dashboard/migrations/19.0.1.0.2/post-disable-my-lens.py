# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """product.category / stock.move have no user_id — My filter cannot resolve."""
    cr.execute(
        """
        UPDATE dashboard_blueprint
           SET lens_my_enabled = FALSE,
               lens_my_default = FALSE
         WHERE key = 'stock_categories'
           AND lens_my_enabled IS TRUE
        """
    )
    _logger.info(
        "stock_categories: disabled unresolved My lens on %s row(s)", cr.rowcount
    )
