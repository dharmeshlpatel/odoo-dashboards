# -*- coding: utf-8 -*-
"""Move Advanced button rules onto the Default Chart Model Option."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ActionVariant = env["dashboard.blueprint.action.variant"].sudo()
    copied_fields = 0
    moved_alts = 0
    for bp in env["dashboard.blueprint"].sudo().search([]):
        default = bp.graph_variant_ids.filtered("is_default")[:1]
        if not default:
            default = bp.graph_variant_ids.sorted("sequence")[:1]
        if not default:
            continue
        vals = {}
        v_domain = (default.primary_action_domain or "").strip() or "[]"
        bp_domain = (bp.primary_action_domain or "").strip() or "[]"
        if v_domain == "[]" and bp_domain != "[]":
            vals["primary_action_domain"] = bp.primary_action_domain
        if (
            not default.primary_label_alt_scope_id
            and bp.primary_label_alt_scope_id
        ):
            vals["primary_label_alt_scope_id"] = bp.primary_label_alt_scope_id.id
            vals["primary_label_alt"] = bp.primary_label_alt or False
        if vals:
            default.with_context(skip_graph_variant_default=True).write(vals)
            copied_fields += 1
        legacy = ActionVariant.search(
            [
                ("blueprint_id", "=", bp.id),
                ("graph_variant_id", "=", False),
            ]
        )
        if legacy and not default.alternate_action_ids:
            legacy.write({"graph_variant_id": default.id})
            moved_alts += len(legacy)
    _logger.info(
        "option button rules: copied fields on %s blueprint(s), "
        "moved %s alternate action(s)",
        copied_fields,
        moved_alts,
    )
