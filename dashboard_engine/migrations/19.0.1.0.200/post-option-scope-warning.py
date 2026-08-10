# -*- coding: utf-8 -*-
"""Copy blueprint scope_warning onto Chart Model Options that lack one."""


def migrate(cr, version):
    try:
        from odoo import SUPERUSER_ID, api
    except Exception:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Blueprint = env["dashboard.blueprint"].sudo()
    for bp in Blueprint.search([("scope_warning", "!=", False)]):
        warn = (bp.scope_warning or "").strip()
        if not warn:
            continue
        for variant in bp.graph_variant_ids:
            if not (variant.scope_warning or "").strip():
                variant.with_context(skip_graph_variant_default=True).write(
                    {"scope_warning": warn}
                )
        if bp.graph_variant_ids.filtered("is_default"):
            bp._sync_blueprint_from_default_variant()
