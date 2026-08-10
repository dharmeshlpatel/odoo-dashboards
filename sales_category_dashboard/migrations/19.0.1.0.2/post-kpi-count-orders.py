# -*- coding: utf-8 -*-
"""Count distinct sale.order so category KPI numbers match opened lists."""

SLOTS = {
    "sales_category_dashboard.slot_scat_quotes": {
        "label": "Quotation",
        "label_plural": "Quotations",
        "compute_model": "sale.order.line",
        "relate_field": "categ_id",
        "compute_domain": "[('state', 'in', ('draft', 'sent'))]",
        "compute_aggregator": "order_id:count_distinct",
        "module_depends": "sale,product",
    },
    "sales_category_dashboard.slot_scat_to_deliver": {
        "label": "Order to Deliver",
        "label_plural": "Orders to Deliver",
        "compute_model": "sale.order.line",
        "relate_field": "categ_id",
        "compute_domain": (
            "[('state', 'in', ('sale', 'done')), "
            "('order_id.delivery_status', '!=', 'full')]"
        ),
        "compute_aggregator": "order_id:count_distinct",
        "action_domain": (
            "[('order_line.categ_id', 'child_of', '{{id}}'), "
            "('state', 'in', ('sale', 'done')), ('delivery_status', '!=', 'full')]"
        ),
        "module_depends": "sale,product,sale_stock",
    },
    "sales_category_dashboard.slot_scat_to_invoice": {
        "label": "Order to Invoice",
        "label_plural": "Orders to Invoice",
        "compute_model": "sale.order.line",
        "relate_field": "categ_id",
        "compute_domain": "[('invoice_status', '=', 'to invoice')]",
        "compute_aggregator": "order_id:count_distinct",
        "module_depends": "sale,product",
    },
    "sales_category_dashboard.slot_scat_to_upsell": {
        "label": "Order to Upsell",
        "label_plural": "Orders to Upsell",
        "compute_model": "sale.order.line",
        "relate_field": "categ_id",
        "compute_domain": "[('invoice_status', '=', 'upselling')]",
        "compute_aggregator": "order_id:count_distinct",
        "module_depends": "sale,product",
    },
    "sales_category_dashboard.slot_scat_bottom_orders": {
        "compute_model": "sale.order.line",
        "relate_field": "categ_id",
        "compute_domain": "[('state', 'in', ('sale', 'done'))]",
        "compute_aggregator": "order_id:count_distinct",
    },
}


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, vals in SLOTS.items():
        slot = env.ref(xmlid, raise_if_not_found=False)
        if slot:
            slot.write(vals)
