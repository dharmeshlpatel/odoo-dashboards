# Studio + Advanced Header Parity — Subtitle / Inline + Alignment

**Date:** 2026-07-28  
**Module:** `dashboard_engine` (odoo-dashboards-19.1-v2)  
**Status:** Approved (design dialogue)  
**Related:** Advanced Card layout Header in `dashboard_blueprint_views.xml`; Studio zone `header`; live `_header_arch` / `_header_line_arch`

## Positioning (one line)

> Header lines use **Subtitle** or **Inline**, each with **Left / Center / Right** alignment; Studio and Advanced match the Title & Image + Header Lines layout; field chips show **`Label (technical_name)`**.

## Problem

Studio Header today is a thin side editor (kind left/right/subtitle, comma-separated field names). Advanced already has Title & Image + M2M field tags, but Kind is still **Subtitle / Left / Right** with no Center and no shared alignment field. Product wants one model everywhere and Studio UI like the Advanced screenshot.

## Decision (locked)

| Choice | Decision |
|--------|----------|
| Scope | **Studio + Advanced form + live card** (Approach A / model approach 1) |
| Kind | `subtitle` \| `inline` only (replace `left` / `right`) |
| Alignment | `left` \| `center` \| `right` — **both** subtitle and inline (default `left`) |
| Field chip label | **`Label (technical_name)`** e.g. `Job Position (function)` — not `Label (Model)` |
| Icon | Visible when `kind == inline` and `alignment == left` |
| Title & Image | Studio gains parity: title field, image field, image style |
| Rejected | Studio-only mapping; keep left/right forever in DB |

## Model

### `dashboard.blueprint` (unchanged fields, Studio expose)

| Field | Role |
|-------|------|
| `header_title_field` / `_id` | Title |
| `header_image_field` / `_id` | Image (binary) |
| `header_image_style` | Fit / cover style as today |

### `dashboard.blueprint.header.item`

| Field | Values / notes |
|-------|----------------|
| `kind` | `subtitle`, `inline` (required; default `subtitle`) |
| `alignment` | `left`, `center`, `right` (required; default `left`) |
| `icon` | Existing `HEADER_ICONS`; UI when inline + left |
| `field_ids` / `field_names` / `ordered_field_ids` | Ordered host fields (M2M tags) |
| `separator` | “Shown as” join for multi text fields |
| `sequence` | Order |

## Migration

| Old `kind` | New |
|------------|-----|
| `subtitle` | `kind=subtitle`, `alignment=left` |
| `left` | `kind=inline`, `alignment=left` |
| `right` | `kind=inline`, `alignment=right` |

- Post-migration (or pre) script updates DB rows + selection metadata  
- Seeds, templates, portable export/import, tests updated  
- Invalid leftover `left`/`right` rejected on write after migrate  

## Live card render

| Kind | Alignment | Behavior |
|------|-----------|----------|
| `subtitle` | left / center / right | Under title; row/text align follows alignment |
| `inline` | left | Former Left row (icons allowed) |
| `inline` | center | New centered detail row under title column |
| `inline` | right | Former Right tags column |

Tag vs text field rules stay as today (`_header_field_is_tags`).

## Advanced form (Card layout → Header)

Keep two-column layout from the screenshot:

1. **Title & Image** — title, image, image style  
2. **Header Lines** — editable list: handle, Kind, Alignment, Icon (conditional), Fields (M2M ordered tags), Shown as, delete, Add a line  

Update Kind selection labels; add Alignment column; fix field tag display to **`Label (technical_name)`** (widget options or related display name helper).

## Studio Header zone

Mirror Advanced structure (not only a single-line side form):

- **Title & Image** controls (write via existing blueprint Studio whitelist: `header_title_field`, `header_image_field`, `header_image_style`)  
- **Header Lines** list: add / reorder / remove / edit Kind, Alignment, Icon, multi-field chips, Shown as  
- Field pickers and chips: **`Label (technical_name)`**  
- Persist via `studio_write_header_item` / create / unlink / reorder; extend write whitelist with `alignment`  

## Out of this pass

| Item | Why |
|------|-----|
| Rename technical storage of `field_names` | Seeds / portable format stable |
| Pixel-perfect Advanced CSS clone in Studio | Behavior + layout parity first |
| New icon set beyond `HEADER_ICONS` | Keep existing |

## Success criteria

- Migrated CRM Customers: old left/right lines become inline+left / inline+right; card still looks correct  
- Advanced: Kind subtitle/inline; Alignment on every line; field tags `Label (name)`  
- Studio Header: Title & Image + lines list with same controls; Save/reload matches Advanced  
- Center subtitle and center inline visible on live card  
- Tests for migration mapping + arch placement; `:19005` upgrade + hard-refresh  

## Ship notes

- Bump `dashboard_engine` version; restart `:19005` with `-u dashboard_engine --dev=xml,assets`  
- Commit only when the user asks  
