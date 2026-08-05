# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Vendor Bills Dashboard",
    "version": "19.0.1.0.1",
    "category": "Accounting/Accounting",
    "summary": "Vendor bills kanban dashboard on supplier partners",
    "description": """
Vendor Bills dashboard for dashboard_engine (AP).
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
        "data/seed_graph_variants.xml",
        "data/seed_headers.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
