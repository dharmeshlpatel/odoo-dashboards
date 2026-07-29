# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Customer 360 Dashboard",
    "version": "19.0.1.0.1",
    "category": "Sales/CRM",
    "summary": "Customer 360 hub kanban dashboard for Dynamic Dashboard Engine",
    "description": """
Customer 360 Dashboard
======================

Manager hub on ``res.partner`` that composes shared CRM / Sales / Invoice
customer slots and enables the Needs attention lens.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "crm",
        "contacts",
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
