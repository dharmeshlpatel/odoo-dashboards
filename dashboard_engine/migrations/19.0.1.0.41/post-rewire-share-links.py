# -*- coding: utf-8 -*-
"""Re-apply customer share pool after share_blueprint_ids → share_link_ids."""
import logging

_logger = logging.getLogger(__name__)

CUSTOMER_KEYS = (
    "crm_customers",
    "sales_customers",
    "website_customers",
    "pos_customers",
)


def migrate(cr, version):
    try:
        from odoo import api, SUPERUSER_ID

        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.exception("rewire-share-links: no env")
        return

    Blueprint = env["dashboard.blueprint"].sudo()
    present = [
        bp
        for key in CUSTOMER_KEYS
        for bp in [Blueprint.search([("key", "=", key)], limit=1)]
        if bp
    ]
    if len(present) < 2:
        _logger.info("rewire-share-links: fewer than 2 customer BPs, skip")
        return

    ids = [bp.id for bp in present]
    for bp in present:
        others = [i for i in ids if i != bp.id]
        bp.with_context(skip_share_sync=True).write(
            {"share_link_ids": [(6, 0, others)]}
        )
    _logger.info(
        "rewire-share-links: pooled %s blueprints",
        ", ".join(bp.key for bp in present),
    )
