# -*- coding: utf-8 -*-
"""Force website product primary onto sale.report graph."""


def migrate(cr, version):
    domain = "[('website_id', '!=', False)]"
    cr.execute(
        """
        UPDATE dashboard_blueprint SET
            primary_button_label = jsonb_build_object('en_US', %s),
            primary_action_xmlid = %s,
            primary_action_domain = %s,
            graph_model = %s,
            graph_data_field = %s,
            graph_measure = %s,
            graph_groupby = %s,
            graph_domain = %s,
            graph_caption = jsonb_build_object('en_US', %s)
        WHERE key = 'website_products'
        """,
        (
            "Online Sales Analysis",
            "sale.action_order_report_all",
            domain,
            "sale.report",
            "product_id",
            "price_subtotal:sum",
            "date:month",
            domain,
            "Online Sales",
        ),
    )
