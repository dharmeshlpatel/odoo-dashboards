# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
"""Drop Customer 360 local chart options so packs own Pipeline / Sales Orders."""


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    bp = env.ref(
        "customer_360_dashboard.blueprint_customer_360",
        raise_if_not_found=False,
    )
    if not bp:
        return
    # Remove seeded / duplicated local options; Share Links supply them.
    bp.graph_variant_ids.unlink()
    for xmlid in (
        "customer_360_dashboard.graph_variant_c360_lead",
        "customer_360_dashboard.graph_variant_c360_sale",
    ):
        data = env["ir.model.data"].search(
            [
                ("module", "=", xmlid.split(".", 1)[0]),
                ("name", "=", xmlid.split(".", 1)[1]),
            ],
            limit=1,
        )
        if data:
            data.unlink()
