# -*- coding: utf-8 -*-
"""Copy blueprint Group By / Measure / Include defaults onto Chart Model Options."""


def migrate(cr, version):
    env = None
    try:
        from odoo import api, SUPERUSER_ID

        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        return
    Blueprint = env["dashboard.blueprint"].sudo()
    for bp in Blueprint.search([]):
        bp._ensure_default_graph_variant_row()
        bp._ensure_option_graph_defaults()
        if bp.graph_variant_ids.filtered("is_default"):
            bp._sync_blueprint_from_default_variant()
