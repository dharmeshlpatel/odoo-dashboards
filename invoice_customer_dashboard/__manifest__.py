# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Invoice Customers Dashboard",
    "version": "19.0.1.0.6",
    "category": "Accounting/Accounting",
    "summary": "Invoice Customers kanban dashboard preset for Dynamic Dashboard Engine",
    "description": """
Invoice Customers Dashboard
===========================

Ships the Invoice Customers blueprint preset for ``dashboard_engine``.
Joins Customer 360 when that hub is installed. Packs stay standalone.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "customer_360_dashboard",
        "account",
    ],
    "data": [
        "data/seed_conditions.xml",
        "data/seed_blueprints.xml",
        "data/seed_dashboard_ui.xml",
        "data/seed_blueprint_headers.xml",
        "data/seed_invoice_parity.xml",
        "data/seed_graph_variants.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
}
