# -*- coding: utf-8 -*-
"""Recompute stored domain Char so group_value tokens use group_value(...)."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'dashboard_condition' AND column_name = 'domain'
        """
    )
    if not cr.fetchone():
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    conditions = env["dashboard.condition"].search([("domain_tree", "!=", False)])
    for condition in conditions:
        condition._compute_domain()
