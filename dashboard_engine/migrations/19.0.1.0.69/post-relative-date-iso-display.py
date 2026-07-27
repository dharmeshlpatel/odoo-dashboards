# -*- coding: utf-8 -*-
"""Show relative dates as ISO strings in domain Char (DomainSelector-safe)."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    for rec in env["dashboard.condition"].search([]):
        rec._compute_domain()
