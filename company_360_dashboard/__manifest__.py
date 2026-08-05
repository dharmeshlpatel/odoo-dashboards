# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
{
    "name": "Company 360 Dashboard",
    "version": "19.0.1.0.1",
    "category": "Sales/CRM",
    "summary": "Company 360 hub on res.company composing CRM / Sales / Invoice company packs",
    "author": "GritXi Technologies Pvt. Ltd.",
    "website": "https://www.gritxi.com/",
    "depends": [
        "dashboard_engine",
        "crm",
        "sale",
        "account",
        "company_dashboard",
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
