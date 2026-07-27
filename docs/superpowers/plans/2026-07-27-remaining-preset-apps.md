# Remaining preset Apps (Phase A follow-up)

Created 2026-07-27. Naming strips V1 `_enterprise` suffix.

| V1 module | V2 Apps module | Host / key |
|---|---|---|
| *(done)* crm_customer_dashboard | crm_customer_dashboard | partner / crm_customers |
| *(done)* sales_customer_dashboard(_enterprise) | sales_customer_dashboard | partner / sales_customers |
| *(done)* crm_salesperson_dashboard_enterprise | crm_salesperson_dashboard | users / crm_salespersons |
| pos_sales_customer_dashboard_enterprise | pos_sales_customer_dashboard | partner / pos_customers |
| website_sales_customer_dashboard_enterprise | website_sales_customer_dashboard | partner / website_customers |
| sales_product_dashboard_enterprise | sales_product_dashboard | product / sales_products |
| pos_sales_product_dashboard_enterprise | pos_sales_product_dashboard | product / pos_products |
| website_sales_product_dashboard_enterprise | website_sales_product_dashboard | product / website_products |
| stock_dashboard_enterprise / report_stock_enterprise | warehouse_dashboard | warehouse / warehouse_overview |
| *(sales SP twin; not shipped as V1 tree module)* | sales_salesperson_dashboard | users / sales_salespersons |

**Not ported as card presets** (V1 shells / non-card analytics):
- `customer_dashboard`, `product_dashboard`, `salesperson_dashboard`, `base_dashboard`
- `pos_sale_dashboard_enterprise` (store analytics reports, not partner/product cards)
- `report_*` helper modules (depend when actions need them)

Engine `19.0.1.0.79` ships no business preset XML.
