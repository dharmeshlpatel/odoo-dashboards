# Primary Button CARD LEFT UX — design

**Date:** 2026-07-27  
**Module:** `dashboard_engine`  
**Status:** Approved (Approach B) — implementing

## Goal

Replace the flat Primary Button field list (`[]` / `{}`, unclear alternate
label/actions) with layered, Odoo-standard UI.

## Layers

1. **Button** — Label, Action (everyone)
2. **Label by setting** — Scope + “Label when off” (everyone)
3. **App-specific screen** — Alternate actions O2M (managers)
4. **Advanced** — Domain builder + context editor (managers)

## Storage

Unchanged Char fields: `primary_action_domain`, `primary_action_context`.
Runtime helpers unchanged.

## UI details

- Domain: `widget="domain"` (or `dashboard_domain`), model `graph_model`
- Context: structured editor or clearer Char with placeholder; keep `{{id}}`
- Renames: Settings filter / Label when off; App-specific screen help
- Alternate Actions: clearer group string + help paragraph

## Non-goals

- No new models
- No change to alternate-action win order or label-scope runtime
