# -*- coding: utf-8 -*-
"""Count distinct parent orders/moves so KPI numbers match opened lists."""

SLOTS = {
    "sales_product_dashboard.slot_sales_prod_quotations": {
        "label": "Quotation",
        "label_plural": "Quotations",
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": "[('state', 'in', ('draft', 'sent'))]",
        "compute_aggregator": "order_id:count_distinct",
        "module_depends": "sale,product",
    },
    "sales_product_dashboard.slot_sales_prod_to_deliver": {
        "label": "Order to Deliver",
        "label_plural": "Orders to Deliver",
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": (
            "[('state', '=', 'sale'), ('order_id.delivery_status', '!=', 'full')]"
        ),
        "compute_aggregator": "order_id:count_distinct",
        "action_domain": (
            "[('order_line.product_id', '=', '{{id}}'), ('state', '=', 'sale'), "
            "('delivery_status', '!=', 'full')]"
        ),
        "module_depends": "sale,product,sale_stock",
    },
    "sales_product_dashboard.slot_sales_prod_to_invoice": {
        "label": "Order to Invoice",
        "label_plural": "Orders to Invoice",
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": "[('invoice_status', '=', 'to invoice')]",
        "compute_aggregator": "order_id:count_distinct",
        "module_depends": "sale,product",
    },
    "sales_product_dashboard.slot_sales_prod_to_upsell": {
        "label": "Order to Upsell",
        "label_plural": "Orders to Upsell",
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": "[('invoice_status', '=', 'upselling')]",
        "compute_aggregator": "order_id:count_distinct",
        "module_depends": "sale,product",
    },
    "sales_product_dashboard.slot_sales_prod_bottom": {
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": "[('state', '!=', 'cancel')]",
        "compute_aggregator": "order_id:count_distinct",
        "module_depends": "sale,product",
    },
    "sales_product_dashboard.slot_sales_prod_bottom_orders": {
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": "[('state', 'in', ('sale', 'done'))]",
        "compute_aggregator": "order_id:count_distinct",
        "module_depends": "sale,product",
    },
    "sales_product_dashboard.slot_sales_prod_bottom_invoices": {
        "compute_model": "account.move.line",
        "relate_field": "product_id",
        "compute_domain": (
            "[('move_id.move_type', 'in', ('out_invoice', 'out_refund')), "
            "('move_id.state', '!=', 'cancel')]"
        ),
        "compute_aggregator": "move_id:count_distinct",
        "module_depends": "sale,account",
    },
}


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, vals in SLOTS.items():
        slot = env.ref(xmlid, raise_if_not_found=False)
        if slot:
            slot.write(vals)
