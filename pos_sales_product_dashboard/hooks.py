# -*- coding: utf-8 -*-
# Part of GritXi. See LICENSE file for full copyright and licensing details.

PRODUCT_SHARE = (
    "sales_product_dashboard.blueprint_sales_products",
    "stock_product_dashboard.blueprint_stock_products",
    "pos_sales_product_dashboard.blueprint_pos_products",
    "website_sales_product_dashboard.blueprint_website_products",
    "product_360_dashboard.blueprint_product_360",
    "pos_product_360_dashboard.blueprint_pos_product_360",
)


def pre_init_hook(env):
    cr = env.cr
    for key in {"pos_products"}:
        cr.execute(
            """
            DELETE FROM dashboard_blueprint bp
             WHERE bp.key = %s
               AND NOT EXISTS (
                    SELECT 1 FROM ir_model_data d
                     WHERE d.model = 'dashboard.blueprint'
                       AND d.res_id = bp.id
                       AND d.module = %s
               )
            """,
            (key, "pos_sales_product_dashboard"),
        )


def link_product_share_pool(env):
    bps = [env.ref(x, raise_if_not_found=False) for x in PRODUCT_SHARE]
    bps = [b for b in bps if b]
    if len(bps) < 2:
        return
    for bp in bps:
        others = [o.id for o in bps if o.id != bp.id]
        bp.sudo().write({"share_link_ids": [(6, 0, others)]})


def post_init_hook(env):
    slot = env.ref(
        "pos_sales_product_dashboard.slot_pos_prod_lines",
        raise_if_not_found=False,
    )
    if slot and not slot.is_attention_signal:
        # Keep densify light: style only when already attention-worthy elsewhere
        pass
    bp = env.ref(
        "pos_sales_product_dashboard.blueprint_pos_products",
        raise_if_not_found=False,
    )
    if bp and bp.state == "published":
        bp._sync_generated_artifacts()
    link_product_share_pool(env)
