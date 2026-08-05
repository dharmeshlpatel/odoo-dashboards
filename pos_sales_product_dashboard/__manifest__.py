# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "POS Sales Products Dashboard",
    "version": "19.0.1.0.3",
    "category": "Sales/Point Of Sale",
    "summary": "POS Products kanban dashboard preset for Dynamic Dashboard Engine",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": ["dashboard_engine", "point_of_sale", "product"],
    "data": [
        "data/seed_blueprints.xml",
        "data/seed_blueprint_headers.xml",
        "data/seed_pos_product_parity.xml",
        "data/seed_graph_variants.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
}
