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


def _dedupe_overdue_amount_display(env):
    """Overdue money stays on smart button only; right KPI is overdue count.

    Avoids duplicating the same amount on Right · KPIs and Footer · Totals
    (same pattern as product On Hand qty).
    """
    kpi = env.ref(
        "invoice_customer_dashboard.slot_inv_overdue_invoices",
        raise_if_not_found=False,
    )
    if kpi:
        kpi.sudo().write({
            "name": "Overdue Invoices",
            "label": "Overdue Invoice",
            "label_plural": "Overdue Invoices",
            "value_mode": "count",
            "amount_aggregator": False,
            "section": "kpi",
            "style": "danger",
            "style_mode": "when_positive",
            "is_attention_signal": True,
            "show_if_zero": True,
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
        })
    box = env.ref(
        "invoice_customer_dashboard.slot_inv_box_total_overdue",
        raise_if_not_found=False,
    )
    if box:
        box.sudo().write({
            "name": "Overdue Amount",
            "label": "Overdue Amount",
            "section": "button_box",
            "style": "danger",
            "style_mode": "when_positive",
            "is_attention_signal": True,
            "show_if_zero": True,
        })
    # Sales pack smart button: same label so share pool is consistent
    sale_box = env.ref(
        "sales_customer_dashboard.slot_sale_box_total_overdue",
        raise_if_not_found=False,
    )
    if sale_box:
        sale_box.sudo().write({
            "name": "Overdue Amount",
            "label": "Overdue Amount",
            "is_attention_signal": True,
            "show_if_zero": True,
        })


# Back-compat for migration 19.0.1.0.2 (old name forced amount; now dedupes).
_densify_overdue_amount_slot = _dedupe_overdue_amount_display


def post_init_hook(env):
    _dedupe_overdue_amount_display(env)
    link_partner_customer_share_pool(env)
    bp = env.ref(
        "invoice_customer_dashboard.blueprint_invoice_customers",
        raise_if_not_found=False,
    )
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
