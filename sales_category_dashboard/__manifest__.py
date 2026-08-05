# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Sales Categories Dashboard",
    "version": "19.0.1.0.1",
    "category": "Sales/Sales",
    "summary": "Sales by product category kanban dashboard",
    "description": """
Sales by Product Category for dashboard_engine.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "sale",
        "product",
    ],
    "data": [
        "data/seed_blueprints.xml",
        "data/seed_graph_variants.xml",
        "data/seed_headers.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
