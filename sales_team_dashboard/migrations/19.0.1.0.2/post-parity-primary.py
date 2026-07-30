# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.
"""Point Sales Team primary button at sale.report graph analysis."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_blueprint
           SET primary_action_xmlid = %s,
               primary_action_domain = %s
         WHERE key = 'sales_team'
        """,
        (
            "sale.action_order_report_all",
            "[]",
        ),
    )
