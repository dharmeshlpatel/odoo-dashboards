# Customer 360 Suite — Wave 4 Implementation Plan

> **For agentic workers:** Implement task-by-task. Checkboxes track progress.

**Goal:** Ship all Wave 4 packs (Category, Attribution, Company, Vendor Bills) as six Apps modules.

**Architecture:** Thin clones of existing customer/product presets. Share pools per design. Reuse health + attention. No engine layout changes.

**Spec:** `docs/superpowers/specs/2026-07-29-customer-360-wave4-packs-design.md`

## Global Constraints

- Classic stack only; soft-hide via `module_depends`
- Vendor does **not** join customer partner share pool
- Do not commit unless user asks
- Install on `dashboard_engine_v2.ee`, restart `:19016`

---

### Task 1: Category (Sales + Stock)

- [ ] `sales_category_dashboard` — host `product.category`, graph `sale.report`/`categ_id`
- [ ] `stock_category_dashboard` — host `product.category`, graph `stock.move`/`product_category_id`
- [ ] Share pool Sales ↔ Stock; `include_child_records`

### Task 2: Attribution (CRM + Sales × 3 hosts)

- [ ] `crm_attribution_dashboard` — campaign / medium / source
- [ ] `sales_attribution_dashboard` — same hosts
- [ ] Share CRM ↔ Sales per host

### Task 3: Company trio + Vendor Bills

- [ ] `company_dashboard` — CRM / Sales / Invoice on `res.company`
- [ ] `vendor_bills_dashboard` — supplier partners, AP bills
- [ ] Company share triangle; vendor standalone

### Task 4: Verify

- [ ] Install all six; confirm blueprints published + menus
