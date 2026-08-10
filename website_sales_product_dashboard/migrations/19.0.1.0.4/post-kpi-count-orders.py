# -*- coding: utf-8 -*-
"""Count distinct sale.order so website product KPIs match opened lists."""

SLOTS = {
    "website_sales_product_dashboard.slot_website_prod_lines": {
        "name": "Online Orders",
        "label": "Online Order",
        "label_plural": "Online Orders",
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": "[('order_id.website_id', '!=', False)]",
        "compute_aggregator": "order_id:count_distinct",
    },
    "website_sales_product_dashboard.slot_website_prod_kpi_quotations": {
        "label": "Quotation",
        "label_plural": "Quotations",
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": (
            "[('order_id.website_id', '!=', False), "
            "('state', 'in', ('draft', 'sent'))]"
        ),
        "compute_aggregator": "order_id:count_distinct",
    },
    "website_sales_product_dashboard.slot_website_prod_kpi_to_invoice": {
        "label": "Order to Invoice",
        "label_plural": "Orders to Invoice",
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": (
            "[('order_id.website_id', '!=', False), "
            "('invoice_status', '=', 'to invoice')]"
        ),
        "compute_aggregator": "order_id:count_distinct",
    },
    "website_sales_product_dashboard.slot_website_prod_bottom": {
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": "[('order_id.website_id', '!=', False)]",
        "compute_aggregator": "order_id:count_distinct",
    },
    "website_sales_product_dashboard.slot_website_prod_bottom_orders": {
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": (
            "[('order_id.website_id', '!=', False), "
            "('state', 'in', ('sale', 'done'))]"
        ),
        "compute_aggregator": "order_id:count_distinct",
        "action_domain": (
            "[('order_line.product_id', '=', '{{id}}'), ('website_id', '!=', False), "
            "('state', 'in', ('sale', 'done'))]"
        ),
    },
}


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, vals in SLOTS.items():
        slot = env.ref(xmlid, raise_if_not_found=False)
        if slot:
            slot.write(vals)
