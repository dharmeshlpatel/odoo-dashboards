# -*- coding: utf-8 -*-
"""Force POS product primary onto report.pos.order graph."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE dashboard_blueprint SET
            primary_button_label = jsonb_build_object('en_US', 'POS Analysis'),
            primary_action_xmlid = 'point_of_sale.action_report_pos_order_all',
            primary_action_domain = '[]',
            graph_model = 'report.pos.order',
            graph_data_field = 'product_id',
            graph_measure = 'price_total:sum',
            graph_groupby = 'date:month',
            graph_caption = jsonb_build_object('en_US', 'POS Sales')
        WHERE key = 'pos_products'
        """
    )
