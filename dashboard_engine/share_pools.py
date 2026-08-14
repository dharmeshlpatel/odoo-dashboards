# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Named share pools for compose hubs (star topology, not a mesh)."""

PARTNER_CUSTOMER_HUB_XMLID = "customer_360_dashboard.blueprint_customer_360"

PARTNER_CUSTOMER_SPOKE_XMLIDS = (
    "crm_customer_dashboard.blueprint_crm_customers",
    "sales_customer_dashboard.blueprint_sales_customers",
    "invoice_customer_dashboard.blueprint_invoice_customers",
    "website_sales_customer_dashboard.blueprint_website_customers",
    "pos_sales_customer_dashboard.blueprint_pos_customers",
)

COMPOSE_360_BLUEPRINT_XMLIDS = (
    "customer_360_dashboard.blueprint_customer_360",
    "product_360_dashboard.blueprint_product_360",
    "product_category_360_dashboard.blueprint_product_category_360",
    "pos_product_360_dashboard.blueprint_pos_product_360",
    "website_360_dashboard.blueprint_website_360",
    "warehouse_360_dashboard.blueprint_warehouse_360",
    "company_360_dashboard.blueprint_company_360",
    "salesperson_360_dashboard.blueprint_salesperson_360",
)


def link_partner_customer_share_pool(env):
    """No-op: Share Links ship as pack XML. Kept for old callers/tests."""
    return


def uninstall_partner_customer_pack(env, keys=()):
    """Pack XML uninstall drops menus. Do not unlink XML-owned records here."""
    return
