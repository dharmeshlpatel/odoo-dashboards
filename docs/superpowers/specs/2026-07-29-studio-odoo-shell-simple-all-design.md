# Dashboard Studio — Odoo Studio Shell + Simple/All Properties

**Date:** 2026-07-29  
**Module:** `dashboard_engine`  
**Status:** Approved for implementation (Wave 1)  
**Mockups:** `studio-odoo-standard-ux-mockup.canvas.tsx`, `studio-simple-all-settings-mockup.canvas.tsx`  
**Related:** Studio Complete, Setup, Configuration parity specs

## Positioning (one line)

> Odoo Studio–shaped chrome (toolbox · canvas · Properties) with **Simple** and **All** views of the **same** blueprint fields — nothing removed.

## Product rules (locked)

1. **Full power kept** — every current Setup / Content / Configuration / Layout control remains available under **All** (or Setup / Layout modes).
2. **Simple first** — default Properties view uses plain labels and the 80% fields; one click opens **All**.
3. **One storage** — `dashboard.blueprint` + slots / headers / scopes; no second config model.
4. **Advanced form** — remains for partners who prefer the classic form.

## Shell (Odoo Studio pattern)

```text
┌────────────────────────────────────────────────────────────┐
│ Studio bar · name · Setup/Content/Layout · Save/Publish    │
├────┬─────────────────────────────┬─────────────────────────┤
│ +  │  Live card / card map       │  View | Properties      │
│ H  │  (click widget = select)    │  [ Simple | All ]       │
│ C  │                             │  fields…                │
│ K  │                             │                         │
│ …  │                             │                         │
└────┴─────────────────────────────┴─────────────────────────┘
```

| Pane | Role |
|------|------|
| Left toolbox | Zones = building blocks (Header, Chart, KPI, Totals, Shortcuts, Manage, Configuration) |
| Center | Existing card map + live sample (unchanged behavior) |
| Right Properties | **View** tab (structure list) · **Properties** tab (Simple/All editors) |

## Coverage

| Area | Simple | All |
|------|--------|-----|
| Setup mode | Unchanged dedicated mode | Same |
| Layout mode | Unchanged | Same |
| Header / Primary / KPI / Totals / Shortcuts / Manage | Plain questions | Full current inspector |
| Configuration (scopes, periods, lenses, graph domain) | Short summaries + primary toggles | Full current config UI |
| Conditions, Action defaults, domains, xmlids, modules | Linked from Simple “Extra…” | Full editors |

## Non-goals (Wave 1)

- Rewriting runtime kanban widgets  
- Removing Advanced form  
- New token languages / DSL  
- Pixel-perfect clone of Enterprise Studio purple branding (use product tokens; Studio **layout pattern** only)

## Success

1. Admin can configure a KPI with Simple alone for common cases.  
2. Every previous Studio field is reachable in ≤1 click (All or Setup/Layout).  
3. Visual chrome matches the approved Odoo Studio–style mockup structure.
