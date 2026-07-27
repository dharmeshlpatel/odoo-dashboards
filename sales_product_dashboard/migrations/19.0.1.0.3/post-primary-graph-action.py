# -*- coding: utf-8 -*-
"""Point Sales Analysis at sale.report graph (parity with V1 / CRM)."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_blueprint
           SET primary_action_xmlid = %s,
               primary_action_domain = %s
         WHERE key = 'sales_products'
        """,
        (
            "sale.action_order_report_all",
            "[]",
        ),
    )
