# Preset Packs Full Parity Implementation Plan

> **For agentic workers:** Implement pack-by-pack via seed XML only. Engine stays generic.

**Goal:** Bring every V2 preset App to CRM/Sales Customers density (header, KPIs, button_box, bottoms, Views/New/Reports) with working actions.

**Architecture:** Data-only packs under `*_dashboard/data/`. Soft `module_depends` hide slots until apps install. Primary analysis uses graph-model-matching xmlids + engine context (measure bare name, graph_mode).

**Tech Stack:** Odoo 19, `dashboard.blueprint` / `.slot` / `.header.item`, standard `ir.actions.act_window`.

## Global Constraints

- No `_enterprise` in module names
- No business logic in `dashboard_engine`
- Prefer standard xmlids (`sale.*`, `stock.*`, `account.*`, `point_of_sale.*`)
- Cross-model primaries need `primary_action_domain`; same-model use host leaf
- Pack order: sales_products → sales_salespersons → POS/Website customers → POS/Website products → warehouse

---
