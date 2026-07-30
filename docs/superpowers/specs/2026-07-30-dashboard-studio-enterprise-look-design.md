# Dashboard Studio — Odoo Enterprise look & feel

**Date:** 2026-07-30  
**Module:** `dashboard_engine`  
**Status:** Approved — **color remap only** (layout/structure unchanged)  
**Scope:** Replace custom teal/slate accents with Odoo Enterprise primary + greys. No layout rebuild.

## Goal

Make Dashboard Studio **controls** feel native to Odoo Enterprise:

- Colors (primary / borders / muted surfaces)
- Buttons (`btn-primary`, `btn-secondary`, standard radius)
- Inputs / selects (Odoo border + focus ring)
- Form panels / fieldset borders (same radius and border color as forms)

Keep the current Studio layout structure (toolbar · tabs · blocks · map · properties).

## Approach

SCSS token remap + light XML button class cleanup. No layout rebuild.


## Out of scope

- Slot compute / preview / share-pool logic
- Layout schema or Content workspace structure
- Matching every Odoo Studio (web_studio) interaction
- Dark mode as a separate project (inherit whatever Odoo theme vars already provide)

## Design details

### Colors

| Token / use | Before | After |
|-------------|--------|--------|
| Accent / selection | Teal `#0f766e` | `var(--primary)` (Enterprise brand) |
| Accent soft | Teal rgba | Primary at low opacity / Bootstrap soft |
| Borders | `#e5e7eb` | `var(--border-color)` or Odoo grey border |
| Panel bg | `#f8fafc` / `#f1f5f9` | Odoo control-panel / form muted surfaces |
| Ink | `#0f172a` | Inherit body / `--body-color` |

### Chrome

1. **Toolbar** — Flat white (or theme surface), 1px bottom border, no backdrop blur. Keep badge + standard `btn-sm` actions.
2. **Mode tabs (Setup / Content / Layout)** — Odoo-like nav tabs: quiet inactive, active uses primary underline or selected tab style (not black filled pills).
3. **Blocks toolbox** — Light muted rail; active item: primary left border + primary text (no teal).
4. **Card map** — Keep structure; zone selection ring uses primary; drop teal glow.
5. **Properties pane** — Standard form labels / inputs; section headers like form notebook groups.
6. **Layout mode tiles** — Neutral greys; use primary only for emphasis, not a teal palette.

### Markup touch-ups

- `o_ds_btn_accent` → `btn btn-primary` (or `btn-sm btn-primary`) in `dashboard_studio_action.xml`.
- Prefer existing Bootstrap / Odoo utility classes over new custom button skins.
- Keep `o_ds_*` layout hooks; only remove accent-specific styling where replaced.

### Files

- `dashboard_engine/static/src/scss/studio/dashboard_studio.scss` (main)
- `dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml` (button classes)
- Bump `dashboard_engine` patch version; restart `:19016` with `--dev=xml,assets` for verify

## Success criteria

- No teal accent remains in Studio chrome.
- Primary actions match other Odoo Enterprise screens (same purple/primary).
- Setup / Content / Layout tabs read as native Odoo tabs.
- Left map + right editor still usable; no layout regression on desktop.
- Hard-refresh Studio on `:19016` shows the new look.

## Risks

- Hard-coded hex elsewhere in the SCSS may need a second pass.
- Very light primary-on-white contrast: rely on Odoo’s own primary, do not invent a third brand color.
