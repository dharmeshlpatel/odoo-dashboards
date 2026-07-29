# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Dynamic Dashboard Engine",
    "version": "19.0.1.0.107",
    "category": "Productivity",
    "summary": "Build kanban dashboards for any Odoo model via dynamic configuration",
    "description": """
Dynamic Dashboard Engine
========================

A single, dependency-free engine that generates kanban dashboards for **any**
Odoo model through UI / data configuration (blueprints).

Business presets ship as separate Apps modules (CRM/Sales/POS/Website/…).
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
        "views/dashboard_studio_views.xml",
        "views/dashboard_blueprint_create_wizard_views.xml",
        "views/dashboard_relation_path_views.xml",
        "views/dashboard_condition_views.xml",
        "views/dashboard_blueprint_template_views.xml",
        "views/dashboard_engine_menus.xml",
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
