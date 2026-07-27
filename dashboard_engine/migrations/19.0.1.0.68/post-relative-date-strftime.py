# -*- coding: utf-8 -*-
"""Recompute domain Char: use context_today().strftime(...) not \"today\".

DomainSelector's date editor cannot parse the CRM magic string \"today\"
and shows \"Invalid DateTime\". Expression form is DomainSelector-safe.
"""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    for rec in env["dashboard.condition"].search([]):
        rec._compute_domain()
