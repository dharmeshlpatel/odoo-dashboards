# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Give the shipped partner blueprints the picture their card header expects.

The header lines are new records, so the seed data creates them on any
database. The picture and title live on the blueprint itself, which is
noupdate, so an existing row would keep an empty header image forever.

Only blueprints still without a picture are touched: that is the marker of a
header nobody has configured yet, which keeps this safe to re-run.
"""
from odoo import api, SUPERUSER_ID

SEEDED_PARTNER_BLUEPRINTS = ("crm_customers", "sales_customers", "pos_customers")


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    blueprints = env["dashboard.blueprint"].search(
        [
            ("key", "in", SEEDED_PARTNER_BLUEPRINTS),
            ("host_model_name", "=", "res.partner"),
            ("header_image_field", "=", False),
        ]
    )
    blueprints.write(
        {
            "header_title_field": "display_name",
            "header_image_field": "image_128",
            "header_image_style": "avatar",
        }
    )
