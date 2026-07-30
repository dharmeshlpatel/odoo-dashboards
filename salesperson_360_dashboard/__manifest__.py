# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Salesperson 360 Dashboard",
    "version": "19.0.1.0.1",
    "category": "Sales/CRM",
    "summary": "Salesperson 360 hub kanban dashboard for Dynamic Dashboard Engine",
    "description": """
Salesperson 360 Dashboard
=========================

Manager hub on ``res.users`` that composes shared CRM / Sales salesperson
slots and enables the Needs attention lens.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "crm",
        "sale",
        "crm_salesperson_dashboard",
        "sales_salesperson_dashboard",
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
