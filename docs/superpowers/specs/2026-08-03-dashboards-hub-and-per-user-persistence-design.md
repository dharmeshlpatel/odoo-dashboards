# Dashboards Hub + per-user/per-company persistence

**Date:** 2026-08-03
**Module:** `dashboard_engine`
**Status:** Approved (design) — ready for implementation planning
**Scope:** A new comprehensive "Dashboards" hub screen (module-wise list + embedded viewer), plus two persistence changes: chart settings become per user *and* per company, and the hub remembers the last-opened dashboard for the current login session.

## Goal

Give end users one central place to browse every dashboard, grouped by module, similar to Odoo's standard Dashboards app (`spreadsheet_dashboard`) — without rebuilding how a dashboard itself renders. Alongside this, make saved chart settings company-aware, and let the hub reopen where the user left off, for as long as they stay logged in.

## Out of scope

- Rebuilding dashboard rendering (cards, KPIs, smart buttons, search bar). The hub reuses the existing per-blueprint kanban view unchanged.
- Removing or repurposing the existing standalone per-app menu generation (Parent Menu, Menu Visibility Groups, Web Icon). These keep their current job untouched.
- Deciding which dashboards are "360" style vs. not, or renaming/merging existing dashboards. That is a content/curation task for whoever assigns Groups, done outside this spec.
- Any new "Subtitle" or dashboard-description field — dropped in favor of a naming cleanup pass done by whoever assigns Groups.
- Cross-device or cross-browser sync of "last opened dashboard" (it is session-scoped by design, see below).

## 1. Dashboards Hub

### Where it lives

A new "Dashboards" menu item is added inside the existing `menu_dashboard_engine_root` app (no new top-level app). It sits alongside the existing admin-facing items (Blueprints, New Dashboard, Relation Paths, Conditions, Import Template), visible to the existing `dashboard_engine.group_dashboard_engine_user` group (unchanged security — no new groups, no default-widening; admins keep assigning this group as they do today).

### Grouping model

New model `dashboard.blueprint.group`, mirroring standard Odoo's `spreadsheet.dashboard.group`:

- `name` (Char, required, translate)
- `sequence` (Integer)
- `dashboard_ids` (One2many `dashboard.blueprint`, inverse of the new `group_id`)

New field on `dashboard.blueprint`:

- `group_id` (Many2one `dashboard.blueprint.group`, optional)

**`group_id` is the single toggle for hub visibility.** A blueprint with a group set appears in the hub; one without a group does not (it is simply skipped when building the hub's left list — no error, no "Ungrouped" catch-all bucket). It remains fully reachable through whatever other access it already has (its own Blueprints admin record, and/or its existing standalone app menu if `menu_parent_xmlid` is set).

This is intentionally independent from the existing menu-generation fields (`menu_parent_xmlid`, `menu_group_ids`, `menu_web_icon`, `menu_web_icon_data`), which are **not changed or repurposed** by this project. A blueprint can have any combination:

| Has `group_id`? | Has `menu_parent_xmlid`? | Result |
|---|---|---|
| Yes | Yes | Shows in the hub **and** in its app's own Reporting-style menu |
| Yes | No | Hub only |
| No | Yes | Standalone app menu only, not in the hub |
| No | No | Only reachable from the admin's Blueprints list |

### Left panel

Lists every published, currently-visible blueprint that has a `group_id`, grouped under its Group's name, ordered by:
1. Group `sequence`
2. Within a group, the blueprint's existing `menu_sequence` field (reused — no new ordering field needed)

Visibility respects everything a blueprint already respects today (published state, required-apps `module_ids`, multi-company `company_id` rule) — the hub does not introduce new visibility logic, it filters the same list an admin already sees minus drafts.

### Right panel

When a dashboard is picked from the left list, the right panel shows that dashboard's **existing, unmodified** screen: same KPI cards, same smart buttons, same primary View/New/Reports actions (scoped to that dashboard's own host model only — nothing from other dashboards mixes in), same search bar, same gear icon (Customize / personal settings). This is an embedded, in-place swap — the left list stays visible; picking a different dashboard does not navigate away from the hub. Exact embedding mechanism (which Odoo action-container technique to use) is an implementation-time decision, not a design-level one.

## 2. Per-user, per-company chart settings (extends `dashboard.user.pref`)

Today, `dashboard.user.pref` is keyed by `(user_id, blueprint_id)` only — one saved Group By/Measure/Filters config per user, shared across every company.

**Change:** add `company_id` (Many2one `res.company`) to `dashboard.user.pref`. The lookup in `DashboardBlueprint._current_pref()` (and anywhere else that searches this model) matches on `(user_id, blueprint_id, company_id)`, using `self.env.company` as the active company.

- Persisted in the database, forever (unaffected by login/logout, unlike the hub's "last opened" state below).
- **Migration:** existing rows have no `company_id`. On upgrade, backfill each existing row's `company_id` to that row's user's current company (`user_id.company_id`), so the company a user is already working in keeps its saved settings. Any other company the user later switches to starts with the blueprint's plain defaults (as if never configured) — this is an accepted, one-time side effect of splitting a previously-shared setting per company.

## 3. Per-user, per-company "last opened dashboard" (new, session-only)

Purpose: when a user opens the hub, it should default to showing the dashboard they were last looking at — but only for as long as they stay logged in.

- Stored **server-side in the Odoo login session** (e.g. `request.session`), keyed by the active company id. **Not** written to any database table.
- Survives page refresh, closing/reopening the browser tab, and restarting the browser — as long as the session itself is still valid (user has not logged out).
- Cleared automatically on logout, because Odoo invalidates the session then. The next login always opens the hub on the **first** dashboard (first group by sequence, first dashboard in it by `menu_sequence`).
- Switching active company mid-session tracks a separate "last opened" per company within that same session (a dict keyed by company id inside the session, not a single flat value).
- **Fallback:** if the remembered blueprint has since been deleted, unpublished, or the user lost access to it (group change, company change), the hub falls back to the first dashboard the user can still see, and quietly forgets the stale value.

## Data model summary

| Model | Change |
|---|---|
| `dashboard.blueprint.group` | New model: `name`, `sequence`, `dashboard_ids` |
| `dashboard.blueprint` | New field: `group_id` (Many2one `dashboard.blueprint.group`) |
| `dashboard.user.pref` | New field: `company_id` (Many2one `res.company`); lookup domain updated everywhere `_current_pref`-style logic runs |
| (session, no model) | Last-opened dashboard per company, server-side session data |

## Security

No new security groups or record rules are required:

- `dashboard.blueprint.group` is simple reference data — reuse the existing manager/studio groups for create/write access (same as `dashboard.blueprint.scope` and similar lookup models today), readable by internal users.
- `dashboard.user.pref`'s existing "own preferences only" rule (`rule_dashboard_user_pref_own`) is unaffected by adding `company_id` — a user still only ever sees their own rows.
- The hub itself uses the same visibility rules blueprints already have (published/company/module gating); no new rule needed.

## Testing considerations

- `dashboard.user.pref` per-company: a user with two companies gets independent saved settings per company; switching company and back preserves each company's own settings.
- Migration: an existing `dashboard.user.pref` row's `company_id` backfills to that user's company; a second company for the same user/blueprint starts from blueprint defaults, not the migrated row.
- Hub left list: a blueprint with no `group_id` is absent from the hub but still reachable via its Blueprints record and/or its standalone menu if it has one.
- Hub "last opened": stored value survives a simulated page reload within the same session; is gone after simulated logout/login; falls back to the first visible dashboard when the remembered one is archived or access is revoked.
- Right panel parity: opening a dashboard through the hub shows identical cards/buttons/search results as opening it through its normal menu (if it still has one) — no divergent behavior between the two entry points.

## Risks

- Splitting `dashboard.user.pref` by company is a one-way migration; users will notice a "reset to defaults" the first time they view a dashboard from a company they hadn't used it in before. This is expected and accepted per this design.
- The hub's right-panel embedding technique (how an existing window action is shown in-place inside a custom OWL screen, while keeping its own search bar/gear button fully functional) is the main implementation risk and should be spiked early during implementation planning.
- Blueprints not yet assigned a `group_id` simply won't appear in the hub — this is silent by design (not an error), but means the hub will look sparse until an admin does the group-assignment pass across existing dashboards.

## Success criteria

- Opening "Dashboards" under the Dashboard Engine app shows a left list of dashboards grouped by module, and clicking one shows its live cards/search/gear on the right without leaving the hub.
- A user's Group By/Measure/Filters for a given dashboard in Company A no longer appear when that user switches to Company B, and vice versa; each is independently editable and saved.
- Logging in fresh always opens the hub on the first dashboard; navigating around and refreshing the page keeps the last-picked dashboard until logout.
- No existing standalone per-app menu entry, Studio "Menu" setup field, or existing dashboard behavior changes as a side effect of this project.
