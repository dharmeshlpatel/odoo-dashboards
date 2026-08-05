# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "POS Session Dashboard",
    "version": "19.0.1.0.1",
    "category": "Sales/Point of Sale",
    "summary": "POS Session daily board for shop managers",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "point_of_sale",
    ],
    "data": [
        "data/seed_blueprints.xml",
        "data/seed_graph_variants.xml",
        "data/seed_headers.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
