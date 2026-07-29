# -*- coding: utf-8 -*-
"""Backfill kanban lens fields on preset blueprints (noupdate seeds skip upgrades)."""
import logging

_logger = logging.getLogger(__name__)

# key → lens field values (matches preset seed_blueprints / seed_website_parity)
LENS_BY_KEY = {
    "crm_customers": {
        "lens_my_enabled": True,
        "lens_my_default": True,
        "lens_my_label": "My Partners",
        "lens_kpis_enabled": True,
        "lens_kpis_default": True,
        "lens_kpis_label": "With KPIs",
    },
    "sales_customers": {
        "lens_my_enabled": True,
        "lens_my_default": True,
        "lens_my_label": "My Partners",
        "lens_kpis_enabled": True,
        "lens_kpis_default": True,
        "lens_kpis_label": "With KPIs",
    },
    "pos_customers": {
        "lens_my_enabled": True,
        "lens_my_default": True,
        "lens_my_label": "My Partners",
        "lens_kpis_enabled": True,
        "lens_kpis_default": True,
        "lens_kpis_label": "With KPIs",
    },
    "website_customers": {
        "lens_my_enabled": True,
        "lens_my_default": True,
        "lens_my_label": "My Partners",
        "lens_kpis_enabled": True,
        "lens_kpis_default": True,
        "lens_kpis_label": "With KPIs",
    },
    "sales_products": {
        "lens_my_enabled": True,
        "lens_my_default": True,
        "lens_my_label": "My Products",
        "lens_kpis_enabled": True,
        "lens_kpis_default": True,
        "lens_kpis_label": "With KPIs",
    },
    "pos_products": {
        "lens_my_enabled": True,
        "lens_my_default": True,
        "lens_my_label": "My Products",
        "lens_kpis_enabled": True,
        "lens_kpis_default": True,
        "lens_kpis_label": "With KPIs",
    },
    "website_products": {
        "lens_my_enabled": True,
        "lens_my_default": True,
        "lens_my_label": "My Products",
        "lens_kpis_enabled": True,
        "lens_kpis_default": True,
        "lens_kpis_label": "With KPIs",
    },
    "crm_salespersons": {
        "lens_my_enabled": False,
        "lens_kpis_enabled": True,
        "lens_kpis_default": True,
        "lens_kpis_label": "With KPIs",
    },
    "sales_salespersons": {
        "lens_my_enabled": False,
        "lens_kpis_enabled": True,
        "lens_kpis_default": True,
        "lens_kpis_label": "With KPIs",
    },
    "warehouse_overview": {
        "lens_my_enabled": False,
        "lens_kpis_enabled": True,
        "lens_kpis_default": True,
        "lens_kpis_label": "With KPIs",
    },
}


def _lens_unset(blueprint):
    """True when lens was never configured (fresh DB before Task 5)."""
    if (blueprint.lens_my_label or "").strip() or (blueprint.lens_kpis_label or "").strip():
        return False
    if blueprint.lens_my_enabled or blueprint.lens_kpis_enabled:
        return False
    return True


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    Blueprint = env["dashboard.blueprint"]
    for key, vals in LENS_BY_KEY.items():
        bp = Blueprint.search([("key", "=", key)], limit=1)
        if not bp or not _lens_unset(bp):
            continue
        bp.write(vals)
        if bp.state == "published":
            bp._sync_generated_artifacts()
        _logger.info("kanban lens seeds: updated blueprint key=%s", key)
