# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Website 360 Dashboard",
    "version": "19.0.1.0.1",
    "category": "Website",
    "summary": "Website 360 hub on website.website (multi-site host)",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "website",
        "website_sale",
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
