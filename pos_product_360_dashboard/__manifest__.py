# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "POS Product 360 Dashboard",
    "version": "19.0.1.0.1",
    "category": "Sales/Point of Sale",
    "summary": "POS-facing Product 360 hub (shares Sales / Stock / POS / Website packs)",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "point_of_sale",
        "product",
        "pos_sales_product_dashboard",
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
