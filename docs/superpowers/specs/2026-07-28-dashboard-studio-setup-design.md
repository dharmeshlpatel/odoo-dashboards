# Dashboard Studio Setup — Host, Apps, Company, Share Links, Menu

**Date:** 2026-07-28  
**Module:** `dashboard_engine` (odoo-dashboards-19.1-v2)  
**Status:** Approved (design dialogue)  
**Depends on:** Studio Complete (Waves C–E) + Layout Studio (Wave F) shipped  
**Related:** blueprint form “Dashboard” / “Menu” groups in `dashboard_blueprint_views.xml`

## Positioning (one line)

> Studio can configure **what** the dashboard is (host, apps, company, share links, menu) with the same professionalism as Content and Layout — without treating host-model rebinding as a casual tweak.

## Problem

Studio today edits card content and page layout, but host model and menu placement still require the Advanced form. Admins who live in Studio hit a dead end for “Dashboard and Menu” parity. A naïve host dropdown would also break headers, host-tied KPI fields, and share-link pools without clear UX.

## Decision (locked)

| Choice | Decision |
|--------|----------|
| Product shape | Dedicated OWL **Setup** mode (Approach B) — not embedded form, not gear-only modal |
| Mode IA | **Setup \| Content \| Layout** (Setup first in the switcher) |
| Field parity | Full form **Dashboard + Menu** groups |
| Host model | **Guarded identity** — editable in **draft**; **locked when published** |
| Host change on Save | Confirm → surgical cleanup of invalid host field refs + incompatible share links → reload catalogs + banner |
| Header chip | Clickable summary (`host label · menu name`) jumps to Setup |
| Advanced form | Remains for name/key and other technical fields; Setup links there when host is locked |
| Approach rejected | A embed form (dual chrome); C settings dialog only (too cramped for M2M + host warnings) |

## Fields (parity map)

### Dashboard

| Studio control | Blueprint field(s) | Notes |
|----------------|-------------------|--------|
| Host model | `host_model_id` / `host_model_name` | Draft: editable. Published: read-only + helper |
| Required apps | `module_ids` ↔ `module_depends` | Many2many modules, no create |
| Company | `company_id` | Show when multi-company; empty = shared template |
| Share links | `share_link_ids` | Same-host domain; exclude self; symmetric sync unchanged |

### Menu

| Studio control | Blueprint field(s) | Notes |
|----------------|-------------------|--------|
| Menu name | `menu_name` | Translate-aware Char |
| Parent menu | `menu_parent_id` ↔ `menu_parent_xmlid` | Many2one `ir.ui.menu`, no create |
| Sequence | `menu_sequence` | Integer |

### Read-only meta (Setup footer / muted)

- Blueprint `key`
- `generated_menu_id` label if present (not editable)

### Explicitly out of Setup

- Blueprint display `name` / `key` rename  
- Auto-remap fields across host models  
- Changing host while **published** without unpublishing  
- Embedding raw domain / graph technical editors (stay in Content / Advanced)

## Architecture

```text
┌──────────────────────────────────────────────────────────┐
│  OWL Studio modes: Setup · Content · Layout              │
│  Setup: Dashboard card + Menu card + host lock UX        │
└────────────────────────────┬─────────────────────────────┘
                             │ studio_* RPC
┌────────────────────────────▼─────────────────────────────┐
│  get_studio_payload  (+ setup fields)                    │
│  studio_write_blueprint (extended whitelist)             │
│  studio_search_* pickers (models, menus, modules, bps)   │
│  On host change: _studio_cleanup_after_host_change()     │
│  Existing write/constrains · share sync · publish/menu   │
└──────────────────────────────────────────────────────────┘
```

**Reuse:** `studio_write_blueprint`, `_STUDIO_BP_WRITE_FIELDS`, `get_studio_payload`, toolbar Save/Discard, `openAdvanced`, existing `@api.constrains` on share links + host, menu publish path (`generated_menu_id` / `_ensure_menu`).

## Host change rules

1. **Published:** host control disabled. Helper: “Unpublish to change host, or use Advanced.”
2. **Draft:** changing `host_model_id` in the editor marks setup dirty; applying on Save requires confirm:
   - Title: Change host model?
   - Body: May invalidate header fields, host-based KPI/total fields, and share links.
3. **On Save after host change (server):**
   - Clear host-tied field names / `*_field_id` mirrors that do not exist on the new model (header title/image, header line field names, slot count/amount fields that target the host).
   - Drop `share_link_ids` partners whose `host_model_id` differs (constraint-safe).
   - Do **not** delete slot rows or manage/shortcut shells solely because host changed.
4. **After Save:** reload payload + field catalogs; Setup shows dismissible banner listing cleared reference count (and optionally short labels).
5. **Publish / health:** existing health issues remain the backstop for anything left broken.

## Studio UX

### Mode switcher

- Buttons (left → right): **Setup · Content · Layout**  
- **Locked default for first ship:** open on **Content** as today; Setup is one click away (mode tab or header chip). No auto-redirect to Setup unless a later plan adds a deep link.

### Setup body

- Two-column desktop (stack on narrow): **Dashboard** | **Menu**  
- Professional form spacing (labels above or Odoo form-like groups), not a dense settings sheet  
- Dirty state: `setupDirty` OR fold into existing `dirty` when setup fields change; Save enabled accordingly  
- Discard restores setup draft from last payload

### Header chip

- Subtitle or chip: human host model name (or technical fallback) · menu name (or “No menu name”)  
- Click → `setStudioMode('setup')`  
- Does not open Advanced

### Pickers

- Host: search `ir.model` (installed / usable models; reuse patterns from create wizard if any)  
- Parent menu: search `ir.ui.menu`  
- Required apps: search `ir.module.module` (installed or all selectable like form)  
- Share links: search `dashboard.blueprint` with domain same host, `id != self`  
- Prefer RPC search helpers over free-typed xmlids for parent menu

## Security & access

- Same Studio group as today (`group_dashboard_engine_studio`) for Setup writes  
- Company field visibility: multi-company group, matching form  
- No new public models; whitelist only Setup fields on `studio_write_blueprint`

## Success criteria

1. From Studio alone, admin can set menu name/parent/sequence, required apps, company, share links without opening Advanced.  
2. Draft: can change host with confirm; after Save, invalid host field refs and bad share links are cleared; live sample / catalogs use new host.  
3. Published: host cannot change in Setup; other Setup fields still save.  
4. Clicking header chip opens Setup.  
5. Publish still creates/updates menu from Setup menu fields (existing publish behavior).  
6. Tests cover payload keys, whitelist writes, host lock when published, and cleanup on host change.

## Non-goals

- Full form clone inside Studio (notebooks, graph advanced, slot lists)  
- Host change while published  
- Automatic field remapping across models  
- Renaming blueprint key/name in Setup  

## Implementation notes (for plan)

- Extend `get_studio_payload` with: `host_model_id`, `host_model_label`, `module_ids` (+ names), `company_id` (+ name), `share_link_ids` (+ names), `menu_name`, `menu_parent_id` (+ name), `menu_sequence`, `host_editable` (derived from `state == 'draft'`), `generated_menu_name`  
- Extend `_STUDIO_BP_WRITE_FIELDS` (and any M2M command handling) for Setup fields  
- Server helper `_studio_cleanup_after_host_change(old_model, new_model)` invoked from `studio_write_blueprint` when host changes  
- OWL: `studioMode: 'setup' | 'content' | 'layout'`; Setup template + SCSS; confirm dialog via existing Odoo dialog service  
- Version bump + `-u dashboard_engine` on `:19005`

## Next steps

1. User reviews this spec file.  
2. Implementation plan → `docs/superpowers/plans/2026-07-28-dashboard-studio-setup.md`.  
3. Ship Setup mode on `:19005`.
