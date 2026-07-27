# -*- coding: utf-8 -*-
"""Refresh domain Char: relative dates as smart strings (today, today -7d).

Conditions domain widget uses before/after presets; ISO stand-ins are obsolete.
"""


def migrate(cr, version):
    cr.execute(
        """
        SELECT id FROM ir_model_data
        WHERE module = 'dashboard_engine' AND model = 'ir.model'
          AND name = 'model_dashboard_condition'
        """
    )
    if not cr.fetchone():
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Condition = env["dashboard.condition"].sudo()
    for condition in Condition.search([]):
        if not condition.domain_tree:
            continue
        # Recompute Char from tokens (triggers _compute_domain).
        condition.domain_tree = condition.domain_tree
