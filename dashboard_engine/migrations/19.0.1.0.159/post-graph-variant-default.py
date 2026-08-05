# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Mark one Default chart-model option per blueprint and sync blueprint fields."""
    cr.execute(
        """
        SELECT DISTINCT blueprint_id
          FROM dashboard_blueprint_graph_variant
        """
    )
    bp_ids = [row[0] for row in cr.fetchall()]
    if not bp_ids:
        _logger.info("graph variant default: no variants to heal")
        return

    env = None
    try:
        from odoo import api, SUPERUSER_ID

        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.exception("graph variant default: cannot build environment")
        return

    Blueprint = env["dashboard.blueprint"]
    healed = 0
    for bp in Blueprint.browse(bp_ids):
        if not bp.graph_variant_ids:
            continue
        if bp.graph_variant_ids.filtered("is_default"):
            bp._sync_blueprint_from_default_variant()
            continue
        match = bp.graph_variant_ids.filtered(
            lambda v: v.graph_model == bp.graph_model
        )[:1]
        target = match or bp.graph_variant_ids.sorted("sequence")[:1]
        if target:
            bp._studio_mark_default_graph_variant(target)
            healed += 1
    _logger.info("graph variant default: marked default on %s blueprint(s)", healed)
