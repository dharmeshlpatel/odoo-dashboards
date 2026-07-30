# Customer 360 Suite — Wave 4 Packs Design

**Date:** 2026-07-29  
**Status:** Approved  
**Parent:** `docs/superpowers/specs/2026-07-29-customer-360-suite-design.md`  
**Repo:** `odoo-dashboards-19.1-v2`

## Goal

Ship every Wave 4 clone pack: Category, Attribution, Company, Vendor Bills. Same classic stack + health/attention. No new layout patterns.

## Module map (locked)

| Module | Blueprints | Host |
|--------|------------|------|
| `sales_category_dashboard` | `sales_categories` | `product.category` |
| `stock_category_dashboard` | `stock_categories` | `product.category` |
| `crm_attribution_dashboard` | `crm_campaigns`, `crm_mediums`, `crm_sources` | `utm.campaign` / `utm.medium` / `utm.source` |
| `sales_attribution_dashboard` | `sales_campaigns`, `sales_mediums`, `sales_sources` | same UTM hosts |
| `company_dashboard` | `company_crm`, `company_sales`, `company_invoice` | `res.company` |
| `vendor_bills_dashboard` | `vendor_bills` | `res.partner` (suppliers) |

## Share pools

- Category: Sales ↔ Stock  
- Attribution: CRM ↔ Sales **per host** (campaign↔campaign, medium↔medium, source↔source)  
- Company: CRM ↔ Sales ↔ Invoice  
- Vendor: standalone (do **not** join customer partner pool)

## Density (v1)

Per suite tables: graph + KPIs + bottoms/menus; soft-hide via `module_depends`; health on overdue / to-invoice / to-pay; attention signals on those slots where present. `include_child_records` on category blueprints.

## Out of scope

Website/POS clones, engine layout changes, AI/scores, Invoice×UTM unless fields exist.

## Success

All six modules install on `dashboard_engine_v2.ee`; menus open; shared slots appear across peers when both sides installed.
