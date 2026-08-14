# Dashboard Studio — native Odoo form widgets

**Date:** 2026-08-11  
**Module:** `dashboard_engine`  
**Status:** Unified Studio field kit (19.0.1.0.243)  
**Prototype:** Cursor canvas `studio-native-form-look-prototype.canvas.tsx`

## Goal

Make Studio **field areas** look like Odoo Enterprise **backend** forms:

- Labels, help text, control height / padding / radius
- many2many tags as **capsules** (`badge rounded-pill`, same as CRM)
- Prefer stock widgets over custom HTML chrome

Keep Studio shell (toolbar · map · properties). Do **not** copy website styling.

## Field types (target)

| ttype | Widget look |
|-------|-------------|
| char / integer / float / monetary | `o_input` / form-control height |
| text | multi-line input |
| boolean | checkbox |
| selection | form-select |
| date / datetime | DateTimeInput |
| many2one | link + dropdown (Many2OneField when wired) |
| many2many | capsule tags (`many2many_tags`) |
| one2many | list + Add a line (when wired) |
| image / binary | preview + Edit / Clear (when wired) |

## This pass (look)

1. Remap Studio SCSS tokens to Odoo CSS vars (border, radius, ink, panel).
2. Bold form labels; form-sized controls (even when class is `*-sm`).
3. Reinforce capsule `border-radius: 50rem` on Studio / ordered tags.
4. Quieter record-picker dropdown (no drop shadow).

## Widget wiring (19.0.1.0.239)

- When Opened relational values → stock `RecordSelector` / `MultiRecordSelector`
- Setup Parent Menu / Hub Group → `RecordSelector`
- Setup Web Icon Image → standalone `Record` + `ImageField` (`StudioBinaryImage`)

## Unified field kit (19.0.1.0.243)

One kit across all Studio sections + Advanced When Opened:

| Control | Stock piece |
|---------|-------------|
| boolean | `CheckBox` (Published stays form-switch) |
| many2one | `RecordSelector` |
| many2many | `MultiRecordSelector` |
| char/select | `form-control` / `form-select` + `.o_ds_field` |
| domain | summary + Edit dialog |
| image | `StudioBinaryImage` |

Helper: `static/src/js/studio/studio_field_kit.js`

## Later passes

- one2many “Add a line” lists

## Chart Model Options (19.0.1.0.247–248)

- Chart Model + Primary Action: one `RecordSelector` shell; search types inside.
- Kit SCSS: outer border only; caret stays in-shell on hover (no wrap to line 2).
- Slot Source Model + Click Action + Primary (no variants): same `RecordSelector`.
- Numbered section heads: step + title always left (`flex-start` / `head_main`).

## Out of scope

- Website theme fonts / marketing spacing
- Full clone of `web_studio` layout
