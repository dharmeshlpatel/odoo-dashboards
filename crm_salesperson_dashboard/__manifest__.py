# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "CRM Salespersons Dashboard",
    "version": "19.0.1.0.2",
    "category": "Sales/CRM",
    "summary": "CRM Salespersons kanban dashboard preset for Dynamic Dashboard Engine",
    "description": """
CRM Salespersons Dashboard
==========================

Ships the CRM Salespersons blueprint preset (``res.users`` host) for
``dashboard_engine`` — customer-parity slots with ``user_id`` as the card
link. Independent of ``crm_customer_dashboard``.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "crm",
        "report_sale_crm",
    ],
    "data": [
        "data/seed_crm_salesperson.xml",
        "data/seed_blueprint_headers.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
