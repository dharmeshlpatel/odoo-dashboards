# -*- coding: utf-8 -*-
"""noupdate seeds: primary opens sale.order, not sale.order.line."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_blueprint
           SET primary_action_domain = %s
         WHERE key = 'website_products'
           AND (primary_action_domain IS NULL OR primary_action_domain IN ('', '[]'))
        """,
        (
            "[('order_line.product_id', '=', '{{id}}'), ('website_id', '!=', False)]",
        ),
    )
