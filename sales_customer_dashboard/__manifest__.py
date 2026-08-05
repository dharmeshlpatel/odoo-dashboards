# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Sales Customers Dashboard",
    "version": "19.0.1.0.1",
    "category": "Sales",
    "summary": "Sales Customers kanban dashboard preset for Dynamic Dashboard Engine",
    "description": """
Sales Customers Dashboard
=========================

Ships the Sales Customers blueprint preset for ``dashboard_engine``.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "sale",
    ],
    "data": [
        "data/seed_blueprints.xml",
        "data/seed_blueprint_headers.xml",
        "data/seed_sales_parity.xml",
        "data/seed_graph_variants.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
