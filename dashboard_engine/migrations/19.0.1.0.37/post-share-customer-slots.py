# -*- coding: utf-8 -*-
"""Wire CRM↔Sales customer share pool; drop CRM copies of Sales-owned keys."""
import logging

_logger = logging.getLogger(__name__)

# (section, key) owned by sales_customers after share — unlink CRM duplicates.
SALES_OWNED_KEYS = {
    ("button_box", "box_total_due"),
    ("button_box", "box_total_overdue"),
    ("bottom", "bottom_deliveries"),
    ("bottom", "bottom_invoiced"),
    ("menu_views", "view_quotations"),
    ("menu_views", "view_orders"),
    ("menu_views", "view_transfers"),
    ("menu_views", "view_invoices"),
    ("menu_new", "new_quotation"),
    ("menu_reports", "report_sales"),
}


def migrate(cr, version):
    env = None
    try:
        from odoo import api, SUPERUSER_ID

        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.exception("share-customer-slots: cannot build environment")
        return

    Blueprint = env["dashboard.blueprint"].sudo()
    crm = Blueprint.search([("key", "=", "crm_customers")], limit=1)
    sales = Blueprint.search([("key", "=", "sales_customers")], limit=1)
    if not crm or not sales:
        _logger.info("share-customer-slots: blueprints missing, skip")
        return

    crm.write({"share_link_ids": [(4, sales.id)]})
    # Symmetric sync runs on write; ensure both sides anyway.
    if crm not in sales.share_link_ids:
        sales.with_context(skip_share_sync=True).write(
            {"share_link_ids": [(4, crm.id)]}
        )

    dupes = crm.slot_ids.filtered(
        lambda s: (s.section, s.key) in SALES_OWNED_KEYS
    )
    if dupes:
        _logger.info(
            "share-customer-slots: unlink %s CRM duplicate slot(s)", len(dupes)
        )
        dupes.unlink()
