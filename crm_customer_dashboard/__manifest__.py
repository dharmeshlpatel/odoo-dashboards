# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "CRM Customers Dashboard",
    "version": "19.0.1.0.3",
    "category": "Sales/CRM",
    "summary": "CRM Customers kanban dashboard preset for Dynamic Dashboard Engine",
    "description": """
CRM Customers Dashboard
=======================

Ships the CRM Customers blueprint preset for ``dashboard_engine``.
Requires CRM. Salesperson dashboards ship in ``crm_salesperson_dashboard``.
""",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "crm",
        "report_sale_crm",
    ],
    "data": [
        "data/seed_conditions.xml",
        "data/seed_blueprints.xml",
        "data/seed_scope_targets.xml",
        "data/seed_blueprint_headers.xml",
        "data/seed_crm_parity.xml",
        "data/seed_graph_variants.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
