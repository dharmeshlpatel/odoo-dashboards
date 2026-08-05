# Studio Odoo Shell + Simple/All — Implementation Plan

> **For agentic workers:** Implement task-by-task. Checkboxes track progress.

**Goal:** Reshape Dashboard Studio Content mode into Odoo Studio–like toolbox · canvas · Properties with Simple/All, without removing any settings.

**Architecture:** CSS/XML shell around existing OWL handlers and `studio_write_*` RPCs. Progressive disclosure via `inspectorTab` / `inspectorMode` state; no new backend models.

**Tech Stack:** OWL, QWeb XML, SCSS, existing `dashboard_studio_action.js`

## Global Constraints

- Keep all current fields reachable under All / Setup / Layout.
- Prefer minimal JS changes; reuse selectZone / editor / save.
- Version bump `dashboard_engine` after ship; restart `:19005` with `-u dashboard_engine --dev=xml,assets`.

---

### Task 1: Design + state

- [x] Spec `2026-07-29-studio-odoo-shell-simple-all-design.md`
- [x] Add `inspectorTab` (`view`|`properties`), `inspectorMode` (`simple`|`all`) to studio state; persist mode in `localStorage`

### Task 2: Shell layout

- [x] Content mode: left toolbox (zones), center map pane, right properties pane
- [x] Hide horizontal `o_ds_zones` bar (toolbox replaces it)
- [x] Properties: View | Properties tabs; Simple | All controls
- [x] SCSS for studio workspace (Odoo-like density, no gradient chrome)

### Task 3: Progressive disclosure

- [x] Mark All-only sections with `o_ds_all_only` (or `t-if` on inspectorMode)
- [x] Simple labels for KPI / config primary fields
- [x] Ensure Conditions + Action defaults remain in All (and linked from Simple)

### Task 4: Verify

- [x] Manual smoke: select KPI, toggle Simple/All, save
- [x] Bump to `19.0.1.0.108`, restart `:19005`
