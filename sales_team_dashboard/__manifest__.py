# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Sales Team Dashboards",
    "version": "19.0.1.0.1",
    "category": "Sales/CRM",
    "summary": "CRM and Sales Team daily kanban dashboards (crm.team host)",
    "description": """
Sales Team Dashboards
=====================

Daily boards on ``crm.team`` for CRM pipeline and Sales orders.
Share pool links both blueprints so slots compose across apps.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "crm",
        "sale",
        "sales_team",
    ],
    "data": [
        "data/seed_blueprints.xml",
        "data/seed_blueprint_headers.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
