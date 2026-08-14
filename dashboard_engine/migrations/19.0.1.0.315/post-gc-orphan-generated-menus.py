# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    env["dashboard.blueprint"]._gc_orphan_generated_artifacts()
    from odoo.addons.dashboard_engine.share_pools import (
        link_partner_customer_share_pool,
    )

    link_partner_customer_share_pool(env)
