# -*- coding: utf-8 -*-
"""Heal option Include defaults + set Default Chart Model on existing prefs."""


def migrate(cr, version):
    try:
        from odoo import SUPERUSER_ID, api
    except Exception:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Blueprint = env["dashboard.blueprint"].sudo()
    Pref = env["dashboard.user.pref"].sudo()
    for bp in Blueprint.search([]):
        if hasattr(bp, "_ensure_option_graph_defaults"):
            bp._ensure_option_graph_defaults()
        default = (
            bp._default_graph_variant()
            if hasattr(bp, "_default_graph_variant")
            else bp.graph_variant_ids.filtered("is_default")[:1]
        )
        if not default:
            continue
        prefs = Pref.search(
            [
                ("blueprint_id", "=", bp.id),
                ("preferred_graph_variant_id", "=", False),
            ]
        )
        if prefs:
            prefs.with_context(skip_variant_graph_defaults=True).write(
                {
                    "preferred_graph_variant_id": default.id,
                    "preferred_graph_model": default.graph_model,
                }
            )
