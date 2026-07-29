# -*- coding: utf-8 -*-
"""Re-publish kanban arch so header flex alignment classes go live."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Blueprint = env["dashboard.blueprint"].sudo()
    n = 0
    for bp in Blueprint.search([("state", "=", "published")]):
        bp._sync_generated_artifacts()
        n += 1
    _logger.info("header-align-flex: synced %s published blueprint(s)", n)
