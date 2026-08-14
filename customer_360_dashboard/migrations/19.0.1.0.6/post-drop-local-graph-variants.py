# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
"""Drop Customer 360 local chart options reseeded by registry heal."""


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    bp = env.ref(
        "customer_360_dashboard.blueprint_customer_360",
        raise_if_not_found=False,
    )
    if not bp:
        return
    bp.graph_variant_ids.unlink()
