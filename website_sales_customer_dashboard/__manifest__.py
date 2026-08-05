# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Website Sales Customers Dashboard",
    "version": "19.0.1.0.2",
    "category": "Website/Website",
    "summary": "Website Customers kanban dashboard preset for Dynamic Dashboard Engine",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": ["dashboard_engine", "website_sale"],
    "data": [
        "data/seed_website_parity.xml",
        "data/seed_blueprint_headers.xml",
        "data/seed_website_customer_parity.xml",
        "data/seed_graph_variants.xml",
    ],
    "installable": True,
    "application": False,
    "license": "Other proprietary",
    "post_init_hook": "post_init_hook",
}
