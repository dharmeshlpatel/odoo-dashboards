# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

"""Stock Products pack install hooks."""

PRODUCT_SHARE = (
    "sales_product_dashboard.blueprint_sales_products",
    "stock_product_dashboard.blueprint_stock_products",
    "pos_sales_product_dashboard.blueprint_pos_products",
    "website_sales_product_dashboard.blueprint_website_products",
    "product_360_dashboard.blueprint_product_360",
    "pos_product_360_dashboard.blueprint_pos_product_360",
)

# Old right-side qty slots (replaced by button_box On Hand / Reserved).
OBSOLETE_SLOT_XMLIDS = (
    "stock_product_dashboard.slot_stprod_on_hand",
    "stock_product_dashboard.slot_stprod_reserved",
    "stock_product_dashboard.slot_stprod_bottom",
)


def link_product_share_pool(env):
    bps = [env.ref(x, raise_if_not_found=False) for x in PRODUCT_SHARE]
    bps = [b for b in bps if b]
    if len(bps) < 2:
        return
    for bp in bps:
        others = [o.id for o in bps if o.id != bp.id]
        bp.sudo().write({"share_link_ids": [(6, 0, others)]})


def cleanup_obsolete_qty_kpi_slots(env):
    Slot = env["dashboard.blueprint.slot"].sudo()
    for xid in OBSOLETE_SLOT_XMLIDS:
        slot = env.ref(xid, raise_if_not_found=False)
        if slot:
            slot.unlink()
    # Also drop by key on stock blueprint if xmlid was lost
    bp = env.ref(
        "stock_product_dashboard.blueprint_stock_products",
        raise_if_not_found=False,
    )
    if bp:
        bp.slot_ids.filtered(
            lambda s: s.key in ("on_hand", "reserved", "bottom_quants")
            and s.section in ("kpi", "bottom")
        ).unlink()


def post_init_hook(env):
    cleanup_obsolete_qty_kpi_slots(env)
    bp = env.ref(
        "stock_product_dashboard.blueprint_stock_products",
        raise_if_not_found=False,
    )
    if bp:
        if bp.menu_parent_xmlid != "stock.menu_warehouse_report":
            bp.sudo().write({"menu_parent_xmlid": "stock.menu_warehouse_report"})
        if bp.state != "published":
            bp.sudo().action_publish()
        else:
            bp.sudo()._sync_generated_artifacts()
    link_product_share_pool(env)
