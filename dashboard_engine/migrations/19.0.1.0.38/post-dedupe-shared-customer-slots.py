# -*- coding: utf-8 -*-
"""Expand customer share pool; drop remaining CRM copies of Sales-owned keys."""
import logging

_logger = logging.getLogger(__name__)

CUSTOMER_KEYS = (
    "crm_customers",
    "sales_customers",
    "website_customers",
    "pos_customers",
)

# Commercial keys owned by sales_customers — remove from other customer BPs.
SALES_OWNED_KEYS = {
    ("button_box", "box_total_due"),
    ("button_box", "box_total_overdue"),
    ("bottom", "bottom_sales"),
    ("bottom", "bottom_deliveries"),
    ("bottom", "bottom_invoiced"),
    ("menu_views", "view_quotations"),
    ("menu_views", "view_orders"),
    ("menu_views", "view_transfers"),
    ("menu_views", "view_invoices"),
    ("menu_new", "new_quotation"),
    ("menu_reports", "report_sales"),
    ("menu_reports", "report_quotation"),
    ("menu_reports", "report_transfers"),
    ("menu_reports", "report_invoices"),
    ("kpi", "quotations"),
    ("kpi", "to_deliver"),
    ("kpi", "to_invoice"),
    ("kpi", "to_upsell"),
}


def migrate(cr, version):
    try:
        from odoo import api, SUPERUSER_ID

        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.exception("dedupe-shared-customer-slots: no env")
        return

    Blueprint = env["dashboard.blueprint"].sudo()
    by_key = {
        key: Blueprint.search([("key", "=", key)], limit=1) for key in CUSTOMER_KEYS
    }
    present = [bp for bp in by_key.values() if bp]
    if len(present) < 2:
        _logger.info("dedupe-shared-customer-slots: fewer than 2 customer BPs, skip")
        return

    ids = [bp.id for bp in present]
    for bp in present:
        others = [i for i in ids if i != bp.id]
        bp.with_context(skip_share_sync=True).write(
            {"share_link_ids": [(6, 0, others)]}
        )

    sales = by_key.get("sales_customers")
    if not sales:
        return
    for bp in present:
        if bp == sales:
            continue
        dupes = bp.slot_ids.filtered(lambda s: (s.section, s.key) in SALES_OWNED_KEYS)
        if dupes:
            _logger.info(
                "dedupe-shared-customer-slots: unlink %s slot(s) from %s",
                len(dupes),
                bp.key,
            )
            dupes.unlink()
