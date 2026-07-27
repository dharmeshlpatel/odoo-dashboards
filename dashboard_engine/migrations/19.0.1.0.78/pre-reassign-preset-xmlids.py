# -*- coding: utf-8 -*-
"""Reassign CRM/Sales/salesperson preset xmlids from dashboard_engine to packs."""
import logging

_logger = logging.getLogger(__name__)

# From docs/superpowers/plans/2026-07-27-preset-xmlid-inventory.md
CRM_CUSTOMER_XMLID_NAMES = (
    "blueprint_crm_customers",
    "scope_crm_mine",
    "scope_crm_pipeline",
    "scope_crm_leads",
    "scope_crm_mine_label_sale",
    "scope_crm_mine_label_website",
    "slot_crm_open_opportunities",
    "slot_crm_overdue_opportunities",
    "slot_crm_menu_opportunities",
    "slot_crm_bottom_opportunities",
    "header_crm_job",
    "header_crm_location",
    "header_crm_email",
    "header_crm_tags",
    "condition_crm_overdue_opportunity",
    "rule_crm_overdue_type",
    "rule_crm_overdue_open",
    "rule_crm_overdue_deadline",
    "condition_crm_default_type",
    "rule_crm_default_type",
    "group_value_crm_use_lead",
    "condition_crm_unassigned",
    "rule_crm_unassigned_user",
    "slot_crm_unassigned",
    "slot_crm_menu_view_leads",
    "slot_crm_menu_new_lead",
    "slot_crm_menu_new_opportunity",
    "slot_crm_menu_report_leads",
    "slot_crm_menu_report_opportunities",
    "variant_crm_report_opportunities_enterprise",
    "slot_crm_menu_report_activities",
    "slot_crm_bottom_meetings",
    "variant_crm_primary_enterprise",
)

SALES_CUSTOMER_XMLID_NAMES = (
    "blueprint_sales_customers",
    "scope_sale_orders",
    "scope_sale_quotations",
    "scope_sale_mine",
    "slot_sale_quotations",
    "slot_sale_bottom_orders",
    "header_sales_job",
    "header_sales_location",
    "header_sales_email",
    "header_sales_tags",
    "slot_sale_to_deliver",
    "slot_sale_to_invoice",
    "slot_sale_to_upsell",
    "slot_sale_bottom_deliveries",
    "slot_sale_box_total_due",
    "slot_sale_box_total_overdue",
    "slot_sale_bottom_invoiced",
    "slot_sale_menu_quotations",
    "slot_sale_menu_orders",
    "slot_sale_menu_transfers",
    "slot_sale_menu_invoices",
    "slot_sale_menu_new_quotation",
    "slot_sale_menu_report_sales",
    "slot_sale_menu_report_quotation",
    "slot_sale_menu_report_transfers",
    "slot_sale_menu_report_invoices",
)

CRM_SALESPERSON_XMLID_NAMES = (
    "blueprint_crm_salespersons",
    "scope_crm_sp_pipeline",
    "scope_crm_sp_leads",
    "slot_crm_sp_open",
    "slot_crm_sp_bottom",
    "slot_crm_sp_menu_opportunities",
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
        "reassign-preset-xmlids: moved %s rows to %s",
        cr.rowcount,
        new_module,
    )


def migrate(cr, version):
    _reassign(cr, CRM_CUSTOMER_XMLID_NAMES, "crm_customer_dashboard")
    _reassign(cr, SALES_CUSTOMER_XMLID_NAMES, "sales_customer_dashboard")
    _reassign(cr, CRM_SALESPERSON_XMLID_NAMES, "crm_salesperson_dashboard")
