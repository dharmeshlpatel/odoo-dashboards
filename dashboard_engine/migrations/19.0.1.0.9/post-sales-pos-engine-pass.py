# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Ensure sales_products thin blueprints get the Phase-11 KPI fill on upgrade.

New installs create the richer slot set from post_init_hook. Existing DBs that
already have a one-slot sales_products row only get the missing keys added
here (never deleting user-edited slots).
"""
from odoo import api, SUPERUSER_ID

EXTRA_SLOTS = (
    {
        "key": "product_to_invoice",
        "name": "To Invoice",
        "section": "kpi",
        "sequence": 20,
        "label": "Line to Invoice",
        "label_plural": "Lines to Invoice",
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": "[('invoice_status', '=', 'to invoice')]",
        "compute_aggregator": "__count",
        "action_xmlid": "sale.action_orders_to_invoice",
        "action_domain": (
            "[('order_line.product_id', '=', '{{id}}'),"
            " ('invoice_status', '=', 'to invoice')]"
        ),
        "module_depends": "sale,product",
    },
    {
        "key": "bottom_sales",
        "name": "Sales Button",
        "section": "bottom",
        "sequence": 10,
        "label": "Sales",
        "icon": "fa-usd",
        "show_if_zero": True,
        "compute_model": "sale.order.line",
        "relate_field": "product_id",
        "compute_domain": "[('state', '!=', 'cancel')]",
        "action_xmlid": "sale.action_orders",
        "action_domain": "[('order_line.product_id', '=', '{{id}}')]",
        "module_depends": "sale,product",
    },
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    bp = env["dashboard.blueprint"].search(
        [("key", "=", "sales_products")], limit=1
    )
    if not bp:
        return
    existing = set(bp.slot_ids.mapped("key"))
    Slot = env["dashboard.blueprint.slot"]
    for vals in EXTRA_SLOTS:
        if vals["key"] in existing:
            continue
        Slot.create({**vals, "blueprint_id": bp.id})
