# -*- coding: utf-8 -*-
"""Seed empty Chart Model Option Custom Filters from matching blueprint domain."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    seeded = 0
    for bp in env["dashboard.blueprint"].sudo().search([]):
        bp_domain = (bp.graph_domain or "").strip()
        if not bp_domain or bp_domain == "[]":
            continue
        for variant in bp.graph_variant_ids:
            if variant.graph_model != (bp.graph_model or ""):
                continue
            current = (variant.graph_domain or "").strip() or "[]"
            if current != "[]":
                continue
            variant.with_context(skip_graph_variant_default=True).write(
                {"graph_domain": bp_domain}
            )
            seeded += 1
    _logger.info("seeded variant graph_domain from blueprint: %s row(s)", seeded)
