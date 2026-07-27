# -*- coding: utf-8 -*-
"""Force primary/graph fields (translated Char fields are jsonb)."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_blueprint SET
            primary_action_xmlid = 'sale.action_order_report_salesperson',
            primary_action_domain = '[]',
            graph_model = 'sale.report',
            graph_data_field = 'user_id',
            graph_measure = 'price_subtotal:sum',
            graph_groupby = 'date:month',
            graph_caption = jsonb_build_object('en_US', 'Sales')
        WHERE key = 'sales_salespersons'
        """
    )
