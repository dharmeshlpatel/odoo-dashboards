# -*- coding: utf-8 -*-
"""Fill empty Chart Model Option Group By / Measure (e.g. Sales Orders)."""


def migrate(cr, version):
    try:
        from odoo import SUPERUSER_ID, api
    except Exception:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Blueprint = env["dashboard.blueprint"].sudo()
    for bp in Blueprint.search([]):
        if hasattr(bp, "_ensure_option_graph_defaults"):
            bp._ensure_option_graph_defaults()
