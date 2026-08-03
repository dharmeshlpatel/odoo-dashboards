# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_user_pref AS p
           SET company_id = u.company_id
          FROM res_users AS u
         WHERE p.user_id = u.id
           AND u.company_id IS NOT NULL
        """
    )
    _logger.info(
        "dashboard_user_pref: backfilled company_id on %s rows", cr.rowcount
    )
