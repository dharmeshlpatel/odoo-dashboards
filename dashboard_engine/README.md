# Dynamic Dashboard Engine

Technical name: `dashboard_engine`

Single Odoo application that builds kanban dashboards for **any model** through
`dashboard.blueprint` configuration. Soft module checks replace hard depends on
CRM, Sales, Stock, POS, etc.

## Dependencies

- `base`
- `web`

No business-app dependencies.

## Quick start

1. Install **Dynamic Dashboard Engine**
2. Open **Dashboard Engine → Blueprints**
3. Create a blueprint (host model + graph + slots) and **Publish**
4. Open the generated menu

Seed blueprints for CRM/Sales customers activate automatically when those apps
are installed. A Warehouse example is created when Inventory (`stock`) is present.

## Share Links With (slot + chart option inheritance)

On **Kanban Card**, **Share Links With** pools Manage Menu / CARD RIGHT - KPIs / both CARD BOTTOM
layers across linked blueprints (bi-directional, N-level). It also pools
**Chart Model Options** into the gear picker (always pool): CRM charts stay
editable on CRM, Sales on Sales, but both appear on each linked dashboard and
on Customer 360. In Studio, peer options are **read-only** (same pattern as
shared KPIs) with a link to open the owner dashboard. Pack dashboards (CRM /
Sales / …) own the options; *360 hubs compose them and do not seed duplicates.
Header and this dashboard’s **Default** chart option stay local. Duplicate slot
`(section, key)` (else `action_xmlid`) and duplicate chart `graph_model`
collapse with the **current** blueprint winning (packs before *360 hubs). Each
slot still uses its own groups / `module_depends` for visibility. All
`res.partner` customer packs (CRM, Sales, Website, POS) are seeded in one
share pool; commercial slots are owned once on Sales.
