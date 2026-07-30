# Phase 1 — Sales Team + Salesperson 360 + Customer 360 densify

> **Repo:** `odoo-dashboards-19.1-v2`
> **Date:** 2026-07-30
> **Source:** `docs/2026-07-30-app-store-catalog-plan.md` Tier A Phase 1

## Scope

1. **Sales Team daily boards** (host `crm.team`)
   - CRM Sales Team → menu `crm.crm_menu_report`
   - Sales Team → menu `sale.menu_sale_report`
   - Share pool between the two dailies
2. **Salesperson 360 hub** (host `res.users`)
   - Compose CRM + Sales salesperson packs
   - Needs attention lens on
   - Menu under `crm.crm_menu_report`
3. **Customer 360 densify**
   - Menu → `crm.crm_menu_report`
   - Partner share pool includes Website Customers when installed
   - Invoice overdue KPI uses **amount** (`amount_residual:sum`) as primary attention signal

## Out of scope

- Company 360 host realign (`res.company` vs `res.partner`)
- Sales Team 360 hub (Phase later; dailies first)
- AR aging graph buckets
