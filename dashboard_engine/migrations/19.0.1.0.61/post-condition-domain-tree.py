# -*- coding: utf-8 -*-
"""Backfill domain_tree from existing condition rules."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    conditions = env["dashboard.condition"].search([])
    conditions._rebuild_domain_tree_from_rules()
    _logger.info(
        "condition-domain-tree: rebuilt domain_tree for %s conditions",
        len(conditions),
    )
