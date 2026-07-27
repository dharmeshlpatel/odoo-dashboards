# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Dynamic Dashboard Engine",
    "version": "19.0.1.0.77",
    "category": "Productivity",
    "summary": "Build kanban dashboards for any Odoo model via dynamic configuration",
    "description": """
Dynamic Dashboard Engine
========================

A single, dependency-free engine that generates kanban dashboards for **any**
Odoo model through UI / data configuration (blueprints).

Features:
- Blueprint-driven host kanban views, menus and window actions
- Config-driven KPI rows, footer smart buttons and View/New/Reporting links
- Soft module checks (CRM, Sales, Stock, …) — no hard depends on business apps
- Layman-friendly blueprint builder
- Runtime slot/graph rendering via OWL widgets (no host-model Python required)
- Built-in ordered many2many tags (Group By chains, header fields)

Technical dependencies are intentionally limited to ``base`` and ``web``.
    """,
    "author": "GritXi Technologies Pvt. Ltd.",
    "company": "GritXi Technologies Pvt. Ltd.",
    "maintainer": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": ["base", "web"],
    "data": [
        "security/dashboard_engine_security.xml",
        "security/ir.model.access.csv",
        "data/dashboard_graph_periods_data.xml",
        "views/dashboard_blueprint_views.xml",
        "views/dashboard_relation_path_views.xml",
        "views/dashboard_condition_views.xml",
        "views/dashboard_blueprint_template_views.xml",
        "views/dashboard_engine_menus.xml",
        "data/seed_conditions.xml",
        "data/seed_blueprints.xml",
        "data/seed_blueprint_headers.xml",
        "data/seed_blueprint_warehouse.xml",
        "data/seed_crm_parity.xml",
        "data/seed_sales_parity.xml",
        "data/seed_pos_parity.xml",
        "data/seed_website_parity.xml",
        "data/seed_crm_salesperson.xml",
        "data/seed_share_links.xml",
    ],
    "demo": [],
    "assets": {
        "web.assets_backend": [
            "dashboard_engine/static/src/scss/**/*",
            "dashboard_engine/static/src/js/**/*",
            "dashboard_engine/static/src/xml/**/*",
        ]
    },
    "images": ["static/description/main_screenshot.png"],
    "price": 99,
    "currency": "EUR",
    "installable": True,
    "auto_install": False,
    "application": True,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
