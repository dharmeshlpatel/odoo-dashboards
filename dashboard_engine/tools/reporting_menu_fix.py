# -*- coding: utf-8 -*-
"""Force Reporting menus + product qty layout fixes (noupdate seeds)."""

# Blueprint key -> Reporting menu xmlid (catalog §8.4)
MENU_BY_KEY = {
    "crm_customers": "crm.crm_menu_report",
    "crm_salespersons": "crm.crm_menu_report",
    "crm_campaigns": "crm.crm_menu_report",
    "crm_mediums": "crm.crm_menu_report",
    "crm_sources": "crm.crm_menu_report",
    "crm_sales_team": "crm.crm_menu_report",
    "customer_360": "crm.crm_menu_report",
    "salesperson_360": "crm.crm_menu_report",
    "company_crm": "crm.crm_menu_report",
    "company_360": "crm.crm_menu_report",
    "sales_customers": "sale.menu_sale_report",
    "sales_salespersons": "sale.menu_sale_report",
    "sales_products": "sale.menu_sale_report",
    "sales_categories": "sale.menu_sale_report",
    "sales_campaigns": "sale.menu_sale_report",
    "sales_mediums": "sale.menu_sale_report",
    "sales_sources": "sale.menu_sale_report",
    "sales_team": "sale.menu_sale_report",
    "company_sales": "sale.menu_sale_report",
    "product_360": "sale.menu_sale_report",
    "product_category_360": "sale.menu_sale_report",
    "invoice_customers": "account.menu_finance_reports",
    "vendor_bills": "account.menu_finance_reports",
    "company_invoice": "account.menu_finance_reports",
    "stock_products": "stock.menu_warehouse_report",
    "stock_categories": "stock.menu_warehouse_report",
    "warehouse_overview": "stock.menu_warehouse_report",
    "warehouse_360": "stock.menu_warehouse_report",
    "pos_customers": "point_of_sale.menu_point_rep",
    "pos_products": "point_of_sale.menu_point_rep",
    "pos_sessions": "point_of_sale.menu_point_rep",
    "pos_product_360": "point_of_sale.menu_point_rep",
    "website_customers": "website.menu_reporting",
    "website_products": "website.menu_reporting",
    "website_360": "website.menu_reporting",
}


def apply_reporting_menus(env):
    Blueprint = env["dashboard.blueprint"].sudo()
    for key, menu_xid in MENU_BY_KEY.items():
        bp = Blueprint.search([("key", "=", key)], limit=1)
        if not bp:
            continue
        if bp.menu_parent_xmlid != menu_xid:
            bp.write({"menu_parent_xmlid": menu_xid})
        if bp.state == "published":
            bp._sync_generated_artifacts()


def fix_stock_category_qty_slots(env):
    bp = env.ref(
        "stock_category_dashboard.blueprint_stock_categories",
        raise_if_not_found=False,
    )
    if not bp:
        return
    for slot in bp.slot_ids.filtered(lambda s: s.key in ("cat_on_hand", "cat_reserved")):
        vals = {
            "section": "button_box",
            "show_if_zero": True,
            "icon": "fa-cubes" if "on_hand" in slot.key else "fa-lock",
        }
        if "on_hand" in slot.key:
            vals.update({"key": "box_cat_on_hand", "label": "On Hand", "name": "On Hand"})
        else:
            vals.update({
                "key": "box_cat_reserved",
                "label": "Reserved",
                "name": "Reserved",
                "style": "warning",
                "style_mode": "when_positive",
                "is_attention_signal": True,
            })
        slot.write(vals)
