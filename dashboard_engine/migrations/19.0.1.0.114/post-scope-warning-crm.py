# -*- coding: utf-8 -*-
"""Seed scope_warning on CRM Customers when empty (noupdate seed skip)."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

WARNING = (
    "You cannot disable both 'Pipeline' and 'Leads' because at least one must stay on."
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    bp = env["dashboard.blueprint"].search([("key", "=", "crm_customers")], limit=1)
    if bp and not (bp.scope_warning or "").strip():
        bp.scope_warning = WARNING
        _logger.info("scope-warning-crm: set warning on blueprint id=%s", bp.id)
    else:
        _logger.info("scope-warning-crm: nothing to update")
