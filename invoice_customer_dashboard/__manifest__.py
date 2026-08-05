# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Invoice Customers Dashboard",
    "version": "19.0.1.0.3",
    "category": "Accounting/Accounting",
    "summary": "Invoice Customers kanban dashboard preset for Dynamic Dashboard Engine",
    "description": """
Invoice Customers Dashboard
===========================

Ships the Invoice Customers blueprint preset for ``dashboard_engine``.
Joins the CRM / Sales / Invoice partner-customer share pool when peers
are installed.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "account",
    ],
    "data": [
        "data/seed_conditions.xml",
        "data/seed_blueprints.xml",
        "data/seed_blueprint_headers.xml",
        "data/seed_invoice_parity.xml",
        "data/seed_graph_variants.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
