# -*- coding: utf-8 -*-
"""Count distinct pos.order so POS product KPIs match opened lists."""

SLOTS = {
    "pos_sales_product_dashboard.slot_pos_prod_lines": {
        "name": "POS Orders",
        "label": "POS Order",
        "label_plural": "POS Orders",
        "compute_model": "pos.order.line",
        "relate_field": "product_id",
        "compute_domain": "[]",
        "compute_aggregator": "order_id:count_distinct",
        "action_xmlid": "point_of_sale.action_pos_pos_form",
        "action_domain": "[('lines.product_id', '=', '{{id}}')]",
    },
    "pos_sales_product_dashboard.slot_pos_prod_kpi_refunds": {
        "name": "Refunds",
        "label": "Refund",
        "label_plural": "Refunds",
        "compute_model": "pos.order.line",
        "relate_field": "product_id",
        "compute_domain": "[('order_id.amount_total', '<', 0)]",
        "compute_aggregator": "order_id:count_distinct",
        "action_domain": (
            "[('lines.product_id', '=', '{{id}}'), ('amount_total', '<', 0)]"
        ),
    },
    "pos_sales_product_dashboard.slot_pos_prod_bottom": {
        "compute_model": "pos.order.line",
        "relate_field": "product_id",
        "compute_domain": "[]",
        "compute_aggregator": "order_id:count_distinct",
        "action_xmlid": "point_of_sale.action_pos_pos_form",
        "action_domain": "[('lines.product_id', '=', '{{id}}')]",
    },
}


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, vals in SLOTS.items():
        slot = env.ref(xmlid, raise_if_not_found=False)
        if slot:
            slot.write(vals)
