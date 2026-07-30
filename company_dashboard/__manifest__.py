# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Company Dashboards",
    "version": "19.0.1.0.1",
    "category": "Productivity",
    "summary": "Company rollup CRM / Sales / Invoice kanban dashboards",
    "description": """
Company CRM / Sales / Invoice dashboards for dashboard_engine.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "crm",
        "sale",
        "account",
    ],
    "data": [
        "data/seed_blueprints.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
