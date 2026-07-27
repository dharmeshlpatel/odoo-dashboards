# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Dynamic Dashboard Engine module initialization.
"""

from . import models  # noqa: F401

# Odoo discovers tests/ automatically when --test-tags / --test-enable is used.


def _ensure_soft_host_blueprints(env):
    """Create example blueprints for hosts that only exist when apps are installed."""
    Blueprint = env["dashboard.blueprint"].sudo()
    Model = env["ir.model"].sudo()

    # Warehouse overview
    if "stock.warehouse" in env and not Blueprint.search(
        [("key", "=", "warehouse_overview")], limit=1
    ):
        host = Model.search([("model", "=", "stock.warehouse")], limit=1)
        if host:
            relate = (
                "warehouse_id"
                if "warehouse_id" in env["stock.picking"]._fields
                else False
            )
            bp = Blueprint.create(
                {
                    "name": "Warehouse Overview",
                    "key": "warehouse_overview",
                    "host_model_id": host.id,
                    "module_depends": "stock",
                    "menu_name": "Warehouses Dashboard",
                    "menu_parent_xmlid": "stock.menu_stock_root",
                    "menu_sequence": 5,
                    "primary_button_label": "Transfers",
                    "graph_model": "stock.picking",
                    "graph_data_field": relate or "",
                    "graph_measure": "__count",
                    "graph_groupby": "scheduled_date:month",
                    "graph_domain": "[]",
                    "graph_caption": "Transfers",
                    "state": "published",
                    "sequence": 50,
                    "slot_ids": [
                        (
                            0,
                            0,
                            {
                                "key": "pickings",
                                "name": "Transfers",
                                "section": "kpi",
                                "sequence": 10,
                                "label": "Transfer",
                                "label_plural": "Transfers",
                                "compute_model": "stock.picking",
                                "relate_field": relate or False,
                                "compute_domain": "[]",
                                "compute_aggregator": "__count",
                                "action_model": "stock.picking",
                                "action_domain": "[]",
                                "show_if_zero": True,
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "key": "view_transfers",
                                "name": "View Transfers",
                                "section": "menu_views",
                                "sequence": 10,
                                "label": "Transfers",
                                "action_model": "stock.picking",
                                "action_domain": "[]",
                                "show_if_zero": True,
                            },
                        ),
                    ],
                }
            )
            bp._sync_generated_artifacts()

    # Sales products
    if (
        "product.product" in env
        and "sale.order" in env
        and not Blueprint.search([("key", "=", "sales_products")], limit=1)
    ):
        host = Model.search([("model", "=", "product.product")], limit=1)
        if host:
            bp = Blueprint.create(
                {
                    "name": "Sales Products",
                    "key": "sales_products",
                    "host_model_id": host.id,
                    "module_depends": "sale,product",
                    "menu_name": "Products Dashboard",
                    "menu_parent_xmlid": "sale.sale_menu_root",
                    "primary_button_label": "Sales Analysis",
                    "graph_model": "sale.report"
                    if "sale.report" in env
                    else "sale.order.line",
                    "graph_data_field": "product_id",
                    "graph_measure": "price_subtotal:sum"
                    if "sale.report" in env
                    else "__count",
                    "graph_groupby": "date:month"
                    if "sale.report" in env
                    else "order_id",
                    "graph_caption": "Product Sales",
                    "state": "published",
                    "sequence": 40,
                    "slot_ids": [
                        (
                            0,
                            0,
                            {
                                "key": "product_quotations",
                                "name": "Quotations",
                                "section": "kpi",
                                "sequence": 10,
                                "label": "Quotation line",
                                "label_plural": "Quotation lines",
                                "compute_model": "sale.order.line",
                                "relate_field": "product_id",
                                "compute_domain": (
                                    "[('state', 'in', ('draft', 'sent'))]"
                                ),
                                "compute_aggregator": "__count",
                                "action_xmlid": (
                                    "sale.action_quotations_with_onboarding"
                                ),
                                "action_domain": (
                                    "[('order_line.product_id', '=', '{{id}}'),"
                                    " ('state', 'in', ('draft', 'sent'))]"
                                ),
                                "module_depends": "sale,product",
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "key": "product_to_invoice",
                                "name": "To Invoice",
                                "section": "kpi",
                                "sequence": 20,
                                "label": "Line to Invoice",
                                "label_plural": "Lines to Invoice",
                                "compute_model": "sale.order.line",
                                "relate_field": "product_id",
                                "compute_domain": (
                                    "[('invoice_status', '=', 'to invoice')]"
                                ),
                                "compute_aggregator": "__count",
                                "action_xmlid": "sale.action_orders_to_invoice",
                                "action_domain": (
                                    "[('order_line.product_id', '=', '{{id}}'),"
                                    " ('invoice_status', '=', 'to invoice')]"
                                ),
                                "module_depends": "sale,product",
                            },
                        ),
                        (
                            0,
                            0,
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
                                "action_domain": (
                                    "[('order_line.product_id', '=', '{{id}}')]"
                                ),
                                "module_depends": "sale,product",
                            },
                        ),
                    ],
                }
            )
            bp._sync_generated_artifacts()

    # POS products
    if (
        "product.product" in env
        and "pos.order" in env
        and not Blueprint.search([("key", "=", "pos_products")], limit=1)
    ):
        host = Model.search([("model", "=", "product.product")], limit=1)
        if host:
            bp = Blueprint.create(
                {
                    "name": "POS Products",
                    "key": "pos_products",
                    "host_model_id": host.id,
                    "module_depends": "point_of_sale,product",
                    "menu_name": "Products Dashboard",
                    "menu_parent_xmlid": "point_of_sale.menu_point_root",
                    "primary_button_label": "POS Orders",
                    "graph_model": "pos.order.line"
                    if "pos.order.line" in env
                    else "pos.order",
                    "graph_data_field": "product_id",
                    "graph_measure": "__count",
                    "graph_groupby": "id",
                    "graph_caption": "POS Sales",
                    "state": "published",
                    "sequence": 45,
                    "slot_ids": [
                        (
                            0,
                            0,
                            {
                                "key": "pos_lines",
                                "name": "POS Lines",
                                "section": "kpi",
                                "sequence": 10,
                                "label": "POS Line",
                                "label_plural": "POS Lines",
                                "compute_model": "pos.order.line",
                                "relate_field": "product_id",
                                "compute_domain": "[]",
                                "compute_aggregator": "__count",
                                "action_model": "pos.order",
                                "module_depends": "point_of_sale,product",
                                "show_if_zero": True,
                            },
                        ),
                    ],
                }
            )
            bp._sync_generated_artifacts()

    # Website products
    if (
        "product.product" in env
        and "website_sale" in {
            m.name
            for m in env["ir.module.module"].sudo().search(
                [("state", "=", "installed"), ("name", "=", "website_sale")]
            )
        }
        and not Blueprint.search([("key", "=", "website_products")], limit=1)
    ):
        host = Model.search([("model", "=", "product.product")], limit=1)
        if host and "sale.order.line" in env:
            bp = Blueprint.create(
                {
                    "name": "Website Products",
                    "key": "website_products",
                    "host_model_id": host.id,
                    "module_depends": "website_sale,product",
                    "menu_name": "Products Dashboard",
                    "menu_parent_xmlid": "sale.sale_menu_root",
                    "primary_button_label": "Online Orders",
                    "graph_model": "sale.order.line",
                    "graph_data_field": "product_id",
                    "graph_measure": "__count",
                    "graph_groupby": "order_id",
                    "graph_domain": "[('order_id.website_id', '!=', False)]",
                    "graph_caption": "Online Sales",
                    "state": "published",
                    "sequence": 46,
                    "slot_ids": [
                        (
                            0,
                            0,
                            {
                                "key": "online_lines",
                                "name": "Online Lines",
                                "section": "kpi",
                                "sequence": 10,
                                "label": "Online Line",
                                "label_plural": "Online Lines",
                                "compute_model": "sale.order.line",
                                "relate_field": "product_id",
                                "compute_domain": (
                                    "[('order_id.website_id', '!=', False)]"
                                ),
                                "compute_aggregator": "__count",
                                "action_xmlid": "sale.action_orders",
                                "module_depends": "website_sale,product",
                                "show_if_zero": True,
                            },
                        ),
                    ],
                }
            )
            bp._sync_generated_artifacts()


def _ensure_warehouse_blueprint(env):
    """Backward-compatible alias. """
    _ensure_soft_host_blueprints(env)


def post_init_hook(env):
    """Publish soft-dep blueprints and create host examples when possible."""
    Blueprint = env["dashboard.blueprint"].sudo()
    for bp in Blueprint.search([("state", "=", "published")]):
        bp._sync_generated_artifacts()
    _ensure_soft_host_blueprints(env)


# Backwards-compatible alias used by legacy packs during migration window
POST_INIT_COMPUTE_METHODS = (
    "_compute_default_graph_measure",
    "_compute_default_graph_groupby",
)


def _post_init_hook(env, initializer):
    """Legacy per-app post-init (kept for temporary compatibility)."""
    fields_model = env["ir.model.fields"]
    graph_parameter_model = env["dashboard.graph_parameter"]
    users_env = env["res.users"].with_context(initializer=initializer).sudo()
    graph_model = users_env._get_graph_model()
    graph_parameter_model.set_param(graph_model)
    date_field_values = fields_model._get_date_field_values_from_field(graph_model)
    if date_field_values:
        created_fields = fields_model.create(date_field_values)
        fields_model._set_company_defaults(graph_model, created_fields)
    all_users = users_env.search([])
    for method_name in POST_INIT_COMPUTE_METHODS:
        getattr(all_users, method_name)()
