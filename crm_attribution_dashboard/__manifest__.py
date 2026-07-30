# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "CRM Attribution Dashboards",
    "version": "19.0.1.0.1",
    "category": "Sales/CRM",
    "summary": "CRM kanban dashboards by Campaign, Medium, and Source",
    "description": """
CRM Attribution (Campaign / Medium / Source) for dashboard_engine.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "crm",
        "utm",
    ],
    "data": [
        "data/seed_conditions.xml",
        "data/seed_blueprints.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
