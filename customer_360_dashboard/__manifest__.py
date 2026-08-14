# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Customer 360 Dashboard",
    "version": "19.0.1.0.13",
    "category": "Productivity",
    "summary": "Customer 360 hub kanban dashboard for Dynamic Dashboard Engine",
    "description": """
Customer 360 Dashboard
======================

Manager hub on ``res.partner`` that composes shared customer packs
(CRM / Sales / Invoice / Website / POS when installed) and enables
the Needs attention lens. CRM is optional — install the CRM Customers
pack to add pipeline charts, Pipeline / Leads / My Pipeline boxes, and slots.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
    ],
    "data": [
        "data/seed_blueprints.xml",
        "data/seed_hub_membership.xml",
        "data/seed_dashboard_ui.xml",
        "data/seed_graph_variants.xml",
        "data/seed_blueprint_headers.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
}
