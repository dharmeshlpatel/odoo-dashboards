# -*- coding: utf-8 -*-
"""noupdate seeds: primary opens pos.order, not pos.order.line."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_blueprint
           SET primary_action_domain = %s
         WHERE key = 'pos_products'
           AND (primary_action_domain IS NULL OR primary_action_domain IN ('', '[]'))
        """,
        ("[('lines.product_id', '=', '{{id}}')]",),
    )
