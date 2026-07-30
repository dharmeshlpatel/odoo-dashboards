# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

"""Invoice Customers pack install hooks."""

PARTNER_CUSTOMER_BLUEPRINT_XMLIDS = (
    "crm_customer_dashboard.blueprint_crm_customers",
    "sales_customer_dashboard.blueprint_sales_customers",
    "invoice_customer_dashboard.blueprint_invoice_customers",
    "website_sales_customer_dashboard.blueprint_website_customers",
    "pos_sales_customer_dashboard.blueprint_pos_customers",
    "customer_360_dashboard.blueprint_customer_360",
)


def link_partner_customer_share_pool(env):
    """Link all installed partner-customer blueprints into one share pool."""
    bps = []
    for xid in PARTNER_CUSTOMER_BLUEPRINT_XMLIDS:
        bp = env.ref(xid, raise_if_not_found=False)
        if bp:
            bps.append(bp)
    if len(bps) < 2:
        return
    for bp in bps:
        others = [other.id for other in bps if other.id != bp.id]
        bp.sudo().write({"share_link_ids": [(6, 0, others)]})


def _densify_overdue_amount_slot(env):
    """Catalog Q4: overdue KPI shows amount_residual, not count."""
    slot = env.ref(
        "invoice_customer_dashboard.slot_inv_overdue_invoices",
        raise_if_not_found=False,
    )
    if not slot:
        return
    vals = {
        "name": "Overdue Amount",
        "label": "Overdue Amount",
        "label_plural": "Overdue Amount",
        "value_mode": "amount",
        "amount_aggregator": "amount_residual:sum",
        "compute_domain": (
            "[('move_type', 'in', ('out_invoice', 'out_refund')), "
            "('state', '=', 'posted'), "
            "('payment_state', 'in', ('not_paid', 'partial'))]"
        ),
        "action_domain": (
            "[('partner_id', '=', '{{id}}'), "
            "('move_type', 'in', ('out_invoice', 'out_refund')), "
            "('state', '=', 'posted'), "
            "('payment_state', 'in', ('not_paid', 'partial'))]"
        ),
        "is_attention_signal": True,
        "style": "danger",
        "style_mode": "when_positive",
    }
    slot.sudo().write(vals)


def post_init_hook(env):
    _densify_overdue_amount_slot(env)
    link_partner_customer_share_pool(env)
    bp = env.ref(
        "invoice_customer_dashboard.blueprint_invoice_customers",
        raise_if_not_found=False,
    )
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
