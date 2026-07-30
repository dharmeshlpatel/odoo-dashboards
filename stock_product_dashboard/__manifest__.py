# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Stock Products Dashboard",
    "version": "19.0.1.0.1",
    "category": "Inventory/Inventory",
    "summary": "Stock Products daily board (on-hand / reserved) for dashboard_engine",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "stock",
        "product",
    ],
    "data": [
        "data/seed_blueprints.xml",
        "data/seed_headers.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
