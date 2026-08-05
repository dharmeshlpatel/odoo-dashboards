# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Warehouse Dashboard",
    "version": "19.0.1.0.2",
    "category": "Inventory/Inventory",
    "summary": "Warehouse kanban dashboard preset for Dynamic Dashboard Engine",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": ["dashboard_engine", "stock"],
    "data": [
        "data/seed_blueprints.xml",
        "data/seed_blueprint_headers.xml",
        "data/seed_warehouse_parity.xml",
        "data/seed_graph_variants.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
}
