# -*- coding: utf-8 -*-
"""Reassign POS/Website preset xmlids from dashboard_engine to preset apps."""
import logging

_logger = logging.getLogger(__name__)

POS_CUSTOMER_XMLID_NAMES = (
    "blueprint_pos_customers",
    "slot_pos_orders_kpi",
    "slot_pos_bottom",
    "header_pos_job",
    "header_pos_location",
    "header_pos_email",
    "header_pos_tags",
    "scope_pos_orders",
    "scope_pos_mine",
    "slot_pos_to_invoice",
    "slot_pos_menu_orders",
)

WEBSITE_CUSTOMER_XMLID_NAMES = (
    "blueprint_website_customers",
    "scope_website_orders",
    "scope_website_abandoned",
    "slot_website_unpaid",
    "slot_website_abandoned",
    "slot_website_bottom_orders",
    "slot_website_menu_orders",
)


def _reassign(cr, names, new_module):
    if not names:
        return
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = %s
         WHERE module = 'dashboard_engine'
           AND name = ANY(%s)
        """,
        (new_module, list(names)),
    )
    _logger.info(
        "reassign-preset-xmlids-79: moved %s rows to %s",
        cr.rowcount,
        new_module,
    )


def migrate(cr, version):
    _reassign(cr, POS_CUSTOMER_XMLID_NAMES, "pos_sales_customer_dashboard")
    _reassign(cr, WEBSITE_CUSTOMER_XMLID_NAMES, "website_sales_customer_dashboard")
