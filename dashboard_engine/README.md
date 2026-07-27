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

## Share Links With (slot inheritance)

On **Kanban Card**, **Share Links With** pools Manage Menu / CARD RIGHT - KPIs / both CARD BOTTOM
layers across linked blueprints (bi-directional, N-level). Header and the left
primary button stay local. Duplicate `(section, key)` (else `action_xmlid`)
collapses with the **current** blueprint winning. Each slot still uses its own
groups / `module_depends` for visibility. All `res.partner` customer packs
(CRM, Sales, Website, POS) are seeded in one share pool; commercial slots are
owned once on Sales.
