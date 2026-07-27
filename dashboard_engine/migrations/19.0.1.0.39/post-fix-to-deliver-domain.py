# -*- coding: utf-8 -*-
"""Replace non-searchable qty_to_deliver domains with delivery_status."""
import logging

_logger = logging.getLogger(__name__)

NEW_COMPUTE = "[('state', '=', 'sale'), ('delivery_status', '!=', 'full')]"
NEW_ACTION = (
    "[('state', '=', 'sale'), ('delivery_status', '!=', 'full'),"
    " ('partner_id', '=', '{{id}}')]"
)


def migrate(cr, version):
    try:
        from odoo import api, SUPERUSER_ID

        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.exception("fix-to-deliver-domain: no env")
        return

    slot = env.ref("dashboard_engine.slot_sale_to_deliver", raise_if_not_found=False)
    if not slot:
        slot = env["dashboard.blueprint.slot"].sudo().search(
            [("key", "=", "to_deliver"), ("section", "=", "kpi")], limit=1
        )
    if not slot:
        _logger.info("fix-to-deliver-domain: slot missing, skip")
        return

    vals = {}
    if "qty_to_deliver" in (slot.compute_domain or ""):
        vals["compute_domain"] = NEW_COMPUTE
    if "qty_to_deliver" in (slot.action_domain or ""):
        vals["action_domain"] = NEW_ACTION
    # Also rewrite any legacy order_line.qty_to_deliver copies.
    if "order_line.qty_to_deliver" in (slot.compute_domain or ""):
        vals["compute_domain"] = NEW_COMPUTE
    if "order_line.qty_to_deliver" in (slot.action_domain or ""):
        vals["action_domain"] = NEW_ACTION
    if vals:
        slot.write(vals)
        _logger.info("fix-to-deliver-domain: updated slot %s", slot.key)
