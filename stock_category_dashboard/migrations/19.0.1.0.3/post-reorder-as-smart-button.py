# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Move Reordering Rules from Right · KPIs (kpi) to Footer · Totals (button_box).

    Applies to every orderpoint slot still seeded as a right-side KPI link
    (stock Categories and any share-pool copy that kept section=kpi).
    name/label are translated jsonb columns.
    """
    cr.execute(
        """
        UPDATE dashboard_blueprint_slot
           SET section = 'button_box',
               sequence = CASE WHEN sequence < 30 THEN 30 ELSE sequence END,
               name = jsonb_build_object('en_US', 'Reordering Rules'),
               label = jsonb_build_object('en_US', 'Reordering Rules'),
               icon = COALESCE(NULLIF(icon, ''), 'fa-refresh'),
               show_if_zero = TRUE
         WHERE compute_model = 'stock.warehouse.orderpoint'
           AND section = 'kpi'
        """
    )
    _logger.info(
        "reordering rules → button_box smart button on %s slot(s)", cr.rowcount
    )
