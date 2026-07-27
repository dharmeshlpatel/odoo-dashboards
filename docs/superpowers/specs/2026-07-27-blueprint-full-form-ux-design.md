# Blueprint form UX — whole-form professional polish

**Date:** 2026-07-27  
**Module:** `dashboard_engine`  
**Status:** Approved for implementation  
**Prototype:** [blueprint-full-form-ux-prototype.canvas.tsx](/Users/dharmesh/.cursor/projects/Users-dharmesh-Applications-odoo-19-0/canvases/blueprint-full-form-ux-prototype.canvas.tsx)  
**Supersedes (naming / chrome only):** zone labels in `2026-07-26-blueprint-form-ux-design.md` (structure from that spec remains)

## Goal

Make the **entire** Dashboard Blueprint form feel professional and layman-friendly: sheet + all notebook pages — not only Card layout. Same mental model as the live dashboard (Configuration ⚙️, card anatomy, ⋮ Manage menu).

## Non-goals

- No new models or slot sections
- No runtime kanban / OWL renderer redesign
- No live mini-preview of the card (future phase)
- No change to field technical names already aligned to V1 for primary button (`primary_button_label`, `primary_label_alt*`)

## Form shell (keep structure)

| Layer | Role |
|---|---|
| Header | Publish / Unpublish / Check References / Export · statusbar |
| Sheet | Name + **Dashboard** + **Menu** (always visible) |
| Page · Configuration | Scopes, Graph, Filters — live ⚙️ parity |
| Page · Card layout | Header → Primary → KPIs → Totals → Shortcuts |
| Page · Manage menu | Views / New / Reports |
| Page · Technical | Managers only — generated artifacts + stored names |

Draft how-to alert stays; shorten copy if it repeats page help.

## Naming map (UI strings only)

| Today | Proposed |
|---|---|
| Kanban Card | **Card layout** |
| CARD LEFT | **Primary button** |
| CARD RIGHT - KPIs | **Right · KPIs** |
| CARD BOTTOM - Stats Buttons | **Footer · Totals** |
| CARD BOTTOM - Smart Buttons | **Footer · Shortcuts** |
| Manage Menu | **Manage menu** |
| Technical | **Technical** (unchanged; already manager-gated) |

O2M field **API** names stay (`kpi_slot_ids`, `button_box_slot_ids`, `bottom_slot_ids`, …). Update `string=` on those O2Ms to the proposed labels (or leave `nolabel="1"` and rely on separators).

Slot `section` selection labels in Python (`SLOT_SECTIONS`) should match the proposed separator titles for consistency in Technical “All Links”.

## Sheet polish

- Keep two-column **Dashboard** / **Menu**
- Field titles already good (`Host Model`, `Required Apps`, `Menu Name`, `Parent Menu`)
- Help: one short line per field max; remove redundant sheet vs page duplication
- Company field remains multi-company only

## Configuration page

- Keep **General settings** / **Graph** / **Filters** section headings (sentence case: “General settings” optional; prefer Title Case for Odoo consistency: **General Settings**)
- Scopes O2M: Name, Mode, Filter (domain), Default — Description optional
- Graph: Graph Model, Link to card, Include Child Records, Caption, Group By, Measures
- Filters: Creation Date, Closed Date; **Custom Filter…** remains manager-only
- One muted intro under the page title: “Defaults for the live Configuration popup.”

## Card layout page

### Share links

- Keep at top; shorten help to one line about what is pooled vs local

### Card map (phase 1 — recommended)

Static HTML/QWeb block at top of the page (or compact CSS grid) showing Header / Primary+KPIs / Totals / Shortcuts.  
**Phase 1:** visual only (labels match separators below) — no scroll-spy required.  
**Phase 2 (optional):** click-to-scroll via OWL — out of this spec unless explicitly pulled in.

### Zone behaviour (unchanged data model)

| Zone | Number source | Default columns |
|---|---|---|
| Right · KPIs | Related model (`compute_model` + Link) | Shows, Label, Count Model, Link to card, Amount shown, Action |
| Footer · Totals | Host fields | Shows, Label, Icon, Count Field, Amount Field, Action |
| Footer · Shortcuts | Either | See progressive disclosure |

### Progressive disclosure — Footer · Shortcuts

Add a UI-only choice (preferred: inferred + optional Char/Selection `value_source` if inference is ambiguous):

1. **Related records** → show Count Model + Link (+ amount measure if Shows needs amount); hide host Count/Amount Field  
2. **Fields on this card** → show Count Field / Amount Field; hide Count Model + Link  

Inference without new field (acceptable for v1):

- If `compute_model` set → related mode  
- Else if `count_field` or `amount_field` set → host mode  
- Else default related mode for new rows  

Existing seeds must keep working without re-entry.

### Primary button

Keep current two-column layout (Button Label | Action) + full-width Extra Domain / Context for managers.  
Help for `{{id}}`: one concrete sentence (“On customer Acme, `{{id}}` becomes Acme’s id…”).

### Advanced columns

Default-hide across KPI / Totals / Shortcuts / Manage lists: Technical Name, Required Apps, Only for / groups, Show if zero, Style, Conditions (KPIs: Conditions `optional="show"` is fine).  
Managers already see Extra Domain/Context; no new “Advanced” notebook page.

## Manage menu page

- Page title **Manage menu**
- Separators: **Views** / **New** / **Reports** (unchanged)
- Columns: Label, Action; optional hide for Technical Name, Required Apps, Only for
- Short intro: “Same as the live ⋮ menu — links only.”

## Technical page

- Unchanged audience (managers)
- Soften copy; keep generated ids + stored field names + All Links
- All Links section labels should use the new zone names via `SLOT_SECTIONS`

## Look & feel (Odoo-native)

- Prefer standard notebook + separators + muted `<p class="text-muted">` — no custom theme CSS unless needed for the card map
- Card map: light border, flat, no shadows/gradients; match backend density
- Align help `colspan="2"` with field rows (same pattern as Primary Extra Domain note)
- Avoid ALL-CAPS section titles except if matching an existing product pattern; proposed titles use Title Case / middle dot

## Impact

- Views + a few `string=` / `SLOT_SECTIONS` labels + optional Shortcut column `invisible` attrs  
- Possible small slot onchange/compute for Shortcuts mode inference  
- Migrations: none if no new stored field; if `value_source` is added, bump module version + optional pre/post

## Edge cases

- Shortcut rows with both compute_model and host fields: prefer related mode in UI; runtime already merges — do not drop data on write  
- Shared blueprints (`share_link_ids`): rename does not affect pooling  
- Translations: update `string=` / view XML for en_US; existing `.po` may need refresh later

## Testing

1. Open CRM Customers blueprint — sheet + all four pages render; new separator titles visible  
2. Primary button still flips Pipeline ↔ Leads Analysis  
3. KPI Open Opportunity still counts; Totals Total Due still reads host field  
4. Shortcut with compute_model shows related columns; host-only shortcut shows Count Field  
5. Non-manager: no Technical page, no Extra Domain/Context, no Custom Filter  
6. Upgrade existing DB: no data loss on slots  

## Implementation order

1. Rename page/separator/O2M/SLOT_SECTIONS strings + help copy  
2. Shortcuts progressive columns (inference first)  
3. Card map static block on Card layout  
4. Optional: `value_source` field if inference proves insufficient  

## Out of scope follow-ups

- Live card preview pane  
- Click-to-scroll map  
- Wizard / multi-step create flow  
