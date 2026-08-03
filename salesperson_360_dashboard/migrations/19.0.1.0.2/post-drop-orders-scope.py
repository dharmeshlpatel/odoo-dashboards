# -*- coding: utf-8 -*-
"""Drop sale.order include scope from crm.lead Salesperson 360 graph."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    scope = env.ref(
        "salesperson_360_dashboard.scope_sp360_orders",
        raise_if_not_found=False,
    )
    if not scope:
        # noupdate seed may lack xmlid; match by blueprint + domain shape.
        bp = env.ref(
            "salesperson_360_dashboard.blueprint_salesperson_360",
            raise_if_not_found=False,
        )
        if not bp:
            _logger.info("sp360-drop-orders-scope: blueprint missing, skip")
            return
        scope = bp.scope_ids.filtered(
            lambda s: s.mode == "include"
            and "state" in (s.domain or "")
            and "sale" in (s.domain or "")
        )[:1]
    if scope:
        scope.unlink()
        _logger.info("sp360-drop-orders-scope: removed incompatible Sales Orders scope")
    else:
        _logger.info("sp360-drop-orders-scope: nothing to remove")
