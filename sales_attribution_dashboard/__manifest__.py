# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Sales Attribution Dashboards",
    "version": "19.0.1.0.1",
    "category": "Sales/Sales",
    "summary": "Sales kanban dashboards by Campaign, Medium, and Source",
    "description": """
Sales Attribution (Campaign / Medium / Source) for dashboard_engine.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "sale",
        "utm",
    ],
    "data": [
        "data/seed_blueprints.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
