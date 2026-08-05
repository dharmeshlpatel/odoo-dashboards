# Dashboard Studio Layout — Visual Review (Screenshot-Based)

> **Repo:** `odoo-dashboards-19.1-v2` → `dashboard_engine/static/src/`  
> **Date:** 2026-07-30  
> **Reference:** 8 live screenshots of CRM Customers dashboard in Studio mode  
> **Reviewed by:** Primary agent (code + screenshots) + second agent verification  
> **Files reviewed:**
> - `static/src/xml/studio/dashboard_studio_action.xml`
> - `static/src/scss/studio/dashboard_studio.scss`
> - `static/src/js/studio/dashboard_studio_action.js`
> - `models/dashboard_blueprint.py` (lines 1997–2017 confirmed)

---

## ✅ What's Already Genuinely Good (confirmed from screenshots)

| What | Why it works |
|------|-------------|
| **Setup tab 2-column layout** | Dashboard card + Menu card side by side — clean, nothing crowded |
| **Share links chips** (Customer 360, Sales Customers…) | Chips with × remove — exactly right pattern |
| **3-column Content workspace** | Icon rail → card map → properties — proper IDE model |
| **Live sample with real chart bars** | "Barty McBly" showing actual pipeline bars — live preview is excellent |
| **Card map Configuration strip** | Bottom strip already shows `Scopes: Pipeline · measure Count · group by Stage > Expected Closing > Month` — the "add hover summaries" suggestion was already done |
| **Group By chips** (Stage ×, Expected Closing > Month ×) | Orderable chips with × — right pattern |
| **Header Lines** with Kind/Alignment/Icon/Fields | Very detailed, professional — Odoo Studio level |
| **Scope table** with drag handles | Mode dropdown (Include/Restrict) + domain + default checkbox — advanced in a simple table |
| **Manage menu "Add to section" dropdown** | Views / New / Reports — clean section routing |
| **Soft module depends** field per item | Conditional show per module — nice power feature |

---

## 🔴 Issue 1 — Search actions list is unfiltered (ONLY REAL BLOCKER)

**Seen in:** Screenshots 2, 3, 5, 6, 8 — every ACTION section in every zone  
**Second agent:** Confirmed and agrees this is correctly ranked #1.

### Root cause (confirmed in code)

```python
# dashboard_blueprint.py  Lines 1997–2017
def studio_search_actions(self, term="", limit=20):
    """Return window actions for Studio pickers (xmlid + label)."""
    self.ensure_one()
    limit = min(int(limit or 20), 50)
    Action = self.env["ir.actions.act_window"]
    domain = [("name", "ilike", term or "")]        # ← name only, no model scoping
    actions = Action.search(domain, limit=limit, order="name")
```

An empty `term` returns an alphabetical dump of all `ir.actions.act_window` records in the database. On any real instance that means 1099 tax forms, API key wizards, etc. appear on a CRM dashboard configuration pane.

### Recommended fix — soft filter with escape hatch

> ⚠️ Do **not** hard-filter to host model only — some valid actions target a different model (e.g. a wizard on `crm.lead` opened from a `res.partner` dashboard). Hard filter would hide those.

**Approach:** Scope default results to `res_model ∈ {host_model, graph_model}`, but:
1. If the scoped search returns 0 results, fall back automatically to full search
2. Add a small toggle in the UI: **"Show all models"** for power users who know the action xmlid
3. Show a label under the search box: `"Showing actions for Contact / Lead"` (or whatever the current host/graph are)

**Edge cases to handle:**

| Case | Handling |
|------|---------|
| `action.res_model` is `False` or empty | Include in default results — these are generic wizard actions that may be valid |
| `host_model == graph_model` | No change — single-model scope works fine |
| `host_model != graph_model` | Include both: `res_model in (host_model, graph_model)` |
| User needs action on a third model | "Show all models" toggle unlocks full search |

**Python change — corrected (third agent review — all bugs fixed):**

> Field corrections confirmed against [`dashboard_blueprint.py`](file:///Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/models/dashboard_blueprint.py):
> - `host_model_name` = `Char`, related to `host_model_id.model` (line 155) ✅
> - `graph_model` = `Char`, direct field (line 241) ✅
> - `("res_model", "=", False)` — correct ORM domain form ✅
>
> **Bug fixed (third review):** `fallback_used = all_models` in the `else` branch was wrong.
> When `all_models=True` the user explicitly requested all — `fallback_used` must stay `False`.
> The three label cases must be fully separate branches, never mixed.
>
> **Breaking change (third review):** Current JS at line 1268 does `this.state.catalogs.actions = actions` (expects a list).
> Current XML at lines 973 + 1394 does `t-foreach="state.catalogs.actions"` (iterates a list).
> Returning a `dict` breaks both. The `scope_label` key is valid **only if JS + XML are updated in the same commit**.

```python
def studio_search_actions(self, term="", limit=20, all_models=False):
    """Return window actions for Studio pickers (xmlid + label).

    Default scope: actions whose res_model matches host_model_name or
    graph_model, plus model-less actions (res_model = False).
    Pass all_models=True (or UI toggle) to bypass scope.

    Returns a dict — JS must be updated in same commit to unpack .actions:
        {
            'actions': [...],       # list — JS iterates this
            'scoped': bool,
            'scope_label': str,     # shown under search box
        }
    """
    self.ensure_one()
    limit = min(int(limit or 20), 50)
    Action = self.env["ir.actions.act_window"]

    host_model = self.host_model_name          # Char: e.g. "res.partner"
    graph_model = self.graph_model or host_model  # Char: e.g. "crm.lead"
    scoped_models = list({m for m in [host_model, graph_model] if m})

    base_domain = [("name", "ilike", term or "")]
    fallback_used = False

    if not all_models and scoped_models:
        scoped_domain = base_domain + [
            "|",
            ("res_model", "in", scoped_models),
            ("res_model", "=", False),          # model-less actions included
        ]
        actions = Action.search(scoped_domain, limit=limit, order="name")
        if not actions:
            # Auto-fallback: no scoped results — show all and flag it
            actions = Action.search(base_domain, limit=limit, order="name")
            fallback_used = True
    else:
        # all_models explicitly requested — fallback_used stays False
        actions = Action.search(base_domain, limit=limit, order="name")

    # Build label — three clean, separate branches (never mixed)
    host_label = self.host_model_id.name or host_model
    graph_label = (self.graph_model_id.name if self.graph_model_id
                   else graph_model)
    if all_models:
        scope_label = "Showing all actions"
    elif fallback_used:
        scope_label = "No matches for scoped models — showing all"
    else:
        scope_label = f"Showing actions for {host_label}"
        if graph_model and graph_model != host_model:
            scope_label += f" / {graph_label}"

    result = []
    for action in actions:
        xmlid = action.get_external_id().get(action.id) or ""
        if not xmlid:
            continue
        result.append({
            "id": action.id,
            "xmlid": xmlid,
            "name": action.display_name or action.name,
            "res_model": action.res_model or "",
        })
    return {
        "actions": result,
        "scoped": not fallback_used and not all_models,
        "scope_label": scope_label,
    }
```

**JS update required (same commit)** — [`dashboard_studio_action.js` line 1263–1268](file:///Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/static/src/js/studio/dashboard_studio_action.js#L1263-L1268):

```js
// BEFORE (expects list):
const actions = await this.orm.call(
    "dashboard.blueprint", "studio_search_actions",
    [[this.blueprintId], term || "", 25]
);
this.state.catalogs.actions = actions;

// AFTER (expects dict — unpack .actions so t-foreach still works):
const res = await this.orm.call(
    "dashboard.blueprint", "studio_search_actions",
    [[this.blueprintId], term || "", 25, this.state.actionsShowAll || false]
);
this.state.catalogs.actions = res.actions;      // list — keeps t-foreach working
this.state.actionScopeLabel = res.scope_label;  // new state key for UI label
this.state.actionScoped = res.scoped;           // drives toggle state
```

**XML update required (same commit)** — add scope label + toggle after the search input ([lines 968–979](file:///Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml#L968-L979)):

```xml
<label class="o_ds_field">
    <span>Search actions</span>
    <input type="text" class="form-control" t-att-value="state.actionQuery"
           t-on-input="onActionQueryInput" placeholder="Type to search…"/>
    <!-- NEW: scope label + toggle -->
    <div class="d-flex justify-content-between align-items-center mt-1">
        <small class="text-muted" t-esc="state.actionScopeLabel"/>
        <button type="button" class="btn btn-link btn-sm p-0"
                t-on-click="toggleActionsShowAll">
            <t t-if="state.actionsShowAll">Show scoped only</t>
            <t t-else="">Show all models</t>
        </button>
    </div>
</label>
```

**Tests:** any test mocking `studio_search_actions` returning a plain list must return `{"actions": [...], "scoped": true, "scope_label": "..."}` instead.

---

## 🟠 Issue 2 — Empty context key row always visible

**Seen in:** Screenshot 2 (Action defaults)

The pre-rendered empty row `Key (e.g. default_type) | [Always the same value ▾] | 🗑` is always rendered, even when no new key is being added. The `Add context key` link already exists but doesn't replace the empty row.

**Fix:** Remove the pre-rendered empty row from the XML template. The `Add context key` button is sufficient and already there.

---

## 🟠 Issue 3 — "Or host method" has no developer context

**Seen in:** Screenshots 2, 3, 5, 6, 8

A raw Python method name field sits in the middle of user-facing ACTION config with no explanation.

**Fix options (pick one):**
- Wrap in a `<details>` / collapsed accordion labelled `⚙ Developer options`
- Or add a `form-text` note: `"Python method name on the host model — leave blank if using action above"`

> Second agent notes: the fold/accordion approach is cleaner since it also keeps the ACTION section height predictable.

---

## 🟡 Issue 4 — Scope table columns truncate

**Seen in:** Screenshot 7 (Configuration → General Settings)

"My Pic", "Pipelin...", domain `[('type', '='` all cut off in the grid.

**Fix:** Add `title` attribute to each cell value (native browser tooltip). Zero JS, 15 minutes.

---

## 🟡 Issue 5 — Properties pane subtitle is generic across all zones

**Seen in:** All Content screenshots — every zone shows `"Full configuration for this block."`

**Fix:** Make it zone-aware:

| Zone | Subtitle |
|------|---------|
| Header | `Title, image, and subtitle lines shown on the card` |
| Chart & Primary | `Graph data source, measure, and primary action button` |
| KPIs | `Count badges shown in the KPI strip` |
| Totals | `Currency/amount boxes shown below the chart` |
| Shortcuts | `Quick-action chips on the card` |
| Manage menu | `Actions in the ⋮ menu on the live card` |
| Configuration | `Scopes, graph model, and date filters` |

> Second agent: agrees this is correct but moves it to lower priority — nice polish, not task-critical. Ship after #1–#4.

---

## 🟡 Issue 6 — KPI filter label terminology mismatch

**Seen in:** Screenshot 5

- `Extra filter (domain)` and `Extra filters (conditions)` are not Odoo-standard terms.

**Fix:**
- `Extra filter (domain)` → `Domain filter`
- `Extra filters (conditions)` → `Linked conditions` with subtext: `"Shared filter conditions (unlink to remove from this KPI only)"`

---

## 🟡 Issue 7 — Layout mode has no visual grid representation

Based on code review (Layout tab not shown in screenshots).

Layout mode shows row cards with a span `<select>` per column — functional, but no visual representation of what the 12-column grid looks like.

**Fix:** Add a proportional colored tile strip inside each row's `card-body`:

```
┌──────────────┬──────────────┬────────────────────────┐
│   KPI col-3  │   KPI col-3  │    Chart col-6          │
└──────────────┴──────────────┴────────────────────────┘
```

Pure CSS — teal for chart widgets, slate for KPIs. No JS required.

> Second agent: agrees this is the right fix. Correctness gap (#1) is more important but this is the main remaining *visual* gap.

---

## 🟢 Issue 8 — Publish confirmation (conditional only)

**Original suggestion:** Always show a confirmation modal on Publish.  
**Second agent correction:** Odoo rarely confirms primary Publish actions — unconditional confirm causes click fatigue.

**Revised fix:** Only warn when the menu parent or name would change from what's currently live:

> `"Publish will rename/move the menu entry from 'CRM / Customers Dashboard' to 'CRM / {new name}'. Continue?"`

No modal when menu config is unchanged.

---

## ✅ Retracted Suggestions (Already Done in Current Code)

| Suggestion | Reality |
|-----------|---------|
| Card map zone hover tooltips | ✅ Configuration strip already shows `Scopes + graph + groupby` summary |
| Empty state in properties pane | ✅ Icon rail always has a zone active — not needed |

---



---

## Overall Verdict

The studio is **production-quality** — not a basic form wrapper. The 3-column workspace, live sample, scope drag-and-drop, group-by chips, and header line builder are at or above Odoo Studio's own quality level.

**Only Issue #1 (unfiltered Search actions) is a real blocker** before calling Studio polished. Every other item is incremental improvement. The soft-filter approach (scope by default, "Show all models" escape hatch) is the right architecture — not a hard model restriction.

---

## 🆕 Feature Request — `scope_warning`: Warning when all include-scopes are unticked

### Background

v1 (`odoo-dashboards-19.1`) already has this pattern in the hard-coded config dict
([`crm_customer_dashboard/models/res_users.py` line 61](file:///Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1/crm_customer_dashboard/models/res_users.py#L61)):

```python
"graph_data_scope": {
    "fields": [...],
    "warning": "You cannot disable both 'Pipeline' and 'Leads' setting because at least one should be enable.",
},
```

v2 has no equivalent — a user can untick every `include`-mode scope in the gear popup and get an empty chart with no feedback.

### Design — fully data-driven, no hardcoding

The warning is stored on the `dashboard.blueprint` itself, configured in Studio, and evaluated client-side when all `include` scopes are unticked.

---

### Step 1 — New field on `dashboard.blueprint`

```python
# dashboard_blueprint.py  — DashboardBlueprint model

scope_warning = fields.Char(
    string="Scope warning",
    translate=True,
    help="Message shown in the live settings popup when all 'Include' scopes "
         "are unticked. Leave empty for no warning. "
         "Example: \"At least one of 'Pipeline' or 'Leads' must stay on.\"",
)
```

### Step 2 — Expose to the gear popup via `dashboard.user.pref`

> ⚠️ The live gear popup is a **form view on `dashboard.user.pref`**
> ([`dashboard_blueprint_views.xml` line 65](file:///Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/views/dashboard_blueprint_views.xml#L65-L94)),
> **not** a consumer of `get_studio_payload()`. Adding it to `get_studio_payload()` is still
> correct for Studio — but the live popup needs a separate path.

**Option A — related field on `dashboard.user.pref` (cleanest):**

```python
# In DashboardUserPref model:
scope_warning = fields.Char(
    related="blueprint_id.scope_warning",
    readonly=True,
)
```

Add as an **invisible** field in the pref form view ([`dashboard_blueprint_views.xml` line 76 area](file:///Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/views/dashboard_blueprint_views.xml#L76-L84)), alongside the existing hidden fields:

```xml
<!-- In dashboard.user.pref.form, with the other invisible fields -->
<field name="scope_warning" invisible="1"/>
```

This ensures `record.data.scope_warning` is loaded and available to `DashboardScopeCheckboxesField` via `props.record.data.scope_warning`.

**Option B — pass via `get_studio_payload()` only (Studio-only):**

```python
# In get_studio_payload(), after "scopes": scopes:
"scope_warning": self.scope_warning or "",
```

This covers the Studio preview path only. The live popup still needs Option A.

**Recommended: implement both** — Option B for Studio, Option A for live popup.

### Step 3 — Whitelist `scope_warning` in `_STUDIO_BP_WRITE_FIELDS`

[`dashboard_blueprint.py` line 1385](file:///Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/models/dashboard_blueprint.py#L1385-L1413):

```python
_STUDIO_BP_WRITE_FIELDS = frozenset(
    {
        # ... existing fields ...
        "scope_warning",   # ← add this
    }
)
```

Also add to the Advanced form view (`dashboard_blueprint_views.xml` — the `Configuration` tab near the `scope_ids` field at line 316) for parity:

```xml
<field name="scope_warning"
       placeholder="e.g. At least one of 'Pipeline' or 'Leads' must stay on."
       help="Shown when all Include scopes are unticked in the gear popup."/>
```

### Step 4 — Studio UI: editable field in the Config zone

In [`dashboard_studio_action.xml`](file:///Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/static/src/xml/studio/dashboard_studio_action.xml) — inside the Config zone's General Settings block, after the scope list rows:

```xml
<!-- After scope list, before Graph Configuration -->
<label class="o_ds_field mt-3">
    <span>Scope warning</span>
    <input type="text" class="form-control"
           t-att-value="state.payload.scope_warning or ''"
           t-on-change="async (ev) => {
               const payload = await this.orm.call(
                   'dashboard.blueprint',
                   'studio_write_blueprint',
                   [[this.blueprintId], { scope_warning: ev.target.value || false }]
               );
               await this.applyPayload(payload, false);
           }"
           placeholder="e.g. At least one of 'Pipeline' or 'Leads' must stay on."/>
    <div class="form-text">
        Shown in the live ⚙️ popup when all Include scopes are unticked.
        Leave empty for no warning.
    </div>
</label>
```

> **Real write pattern confirmed** from [`dashboard_studio_action.js` line 1659](file:///Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/static/src/js/studio/dashboard_studio_action.js#L1659-L1678):
> Studio writes directly via `this.orm.call("dashboard.blueprint", "studio_write_blueprint", [[id], {field: value}])` then calls `this.applyPayload(...)`. There is **no** `updateBlueprintField` wrapper — that name was incorrect in the previous draft.
> For cleanliness, add a small helper (like `updateHeaderBlueprint`) to keep the scope_warning write DRY:

```js
// In DashboardStudioAction — reuse the same pattern as updateHeaderBlueprint:
async updateConfigBlueprint(field, value) {
    try {
        const payload = await this.orm.call(
            "dashboard.blueprint",
            "studio_write_blueprint",
            [[this.blueprintId], { [field]: value || false }]
        );
        await this.applyPayload(payload, false);
    } catch (error) {
        this.notification.add(
            error?.data?.message || error.message || _t("Config update failed"),
            { type: "danger" }
        );
        await this.loadPayload();
    }
}
```

Then the XML `t-on-change` simplifies to:
```xml
t-on-change="(ev) => this.updateConfigBlueprint('scope_warning', ev.target.value)"
```

### Step 5 — Live gear popup: warn on `onChange` in `DashboardScopeCheckboxesField`

The correct file is [`dashboard_scope_checkboxes.js`](file:///Users/dharmesh/Applications/odoo/19.0/custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine/static/src/js/fields/dashboard_scope_checkboxes.js) — the `onChange` method (line 105) runs on every tick.

The `scope_warning` value is available on the pref record as `props.record.data.scope_warning` (from the related field in Step 2).
The include scopes list comes from `this.items.filter(s => s.mode === 'include')`.

```js
// dashboard_scope_checkboxes.js — extend setup() and onChange:
setup() {
    // ... existing setup code ...
    this.state = useState({ scopeWarning: "" });

    // ⚠️ useSpecialData resolves asynchronously — this.items is empty at
    // onMounted time. Use useEffect watching specialData.data so the warning
    // is evaluated once the RPC returns (and again if scopes reload).
    useEffect(
        () => { this._updateScopeWarning(); },
        () => [this.specialData.data]   // re-runs whenever the data reference changes
    );

    // Also re-check when the record's scope_ids field changes externally
    onWillUpdateProps(() => this._updateScopeWarning());
}

onChange(resId, checked) {
    // ... existing add/remove logic ...
    this.debouncedCommitChanges();
    this._updateScopeWarning();    // ← check on every tick
}

_updateScopeWarning() {
    const warning = this.props.record.data.scope_warning || "";
    if (!warning) {
        this.state.scopeWarning = "";
        return;          // no warning configured — nothing to show
    }

    const includeScopes = this.items.filter(s => s.mode === "include");
    if (!includeScopes.length) {
        this.state.scopeWarning = "";
        return;          // no include scopes — nothing to guard
    }

    const currentIds = this.props.record.data[this.props.name].currentIds;
    const pendingOn = new Set([...currentIds, ...this.idsToAdd]);
    this.idsToRemove.forEach(id => pendingOn.delete(id));

    const anyIncludeOn = includeScopes.some(s => pendingOn.has(s.id));
    this.state.scopeWarning = anyIncludeOn ? "" : warning;
}
```

> **Why `useEffect(() => [...], () => [this.specialData.data])`:**
> `useSpecialData` stores its result in a reactive slot. OWL's `useEffect` re-runs
> its callback whenever the dependency array value changes — so it fires once when
> `specialData.data` goes from `null → [...scopes]` after the RPC, and again if the
> domain changes and the data reloads. `onMounted` alone fires too early.
>
> **Import additions needed:**
> ```js
> import { Component, onWillUnmount, onWillUpdateProps, useEffect } from "@odoo/owl";
> import { useState } from "@odoo/owl";
> ```

Add `state = useState({ scopeWarning: "" })` to `setup()` and render the warning in the component template:

```xml
<!-- dashboard_scope_checkboxes.xml — after the scope rows -->
<div t-if="state.scopeWarning"
     class="alert alert-warning d-flex align-items-center gap-2 py-2 mt-2 mb-0">
    <i class="fa fa-exclamation-triangle"/>
    <span t-esc="state.scopeWarning"/>
</div>
```

### Step 6 — Seed CRM Customers (and any preset with include scopes) in XML data

Blueprint presets are not yet defined in XML data files (only `dashboard_graph_periods_data.xml` exists under `data/`). When blueprints are first created via Studio or SQL, seed the `scope_warning` via an `ir.model.data` update or a migration script:

```xml
<!-- Example: if a CRM Customers blueprint preset is ever added to XML data -->
<record id="blueprint_crm_customers" model="dashboard.blueprint">
    <!-- ... other fields ... -->
    <field name="scope_warning">You cannot disable both 'Pipeline' and 'Leads' because at least one must stay on.</field>
</record>
```

For existing live blueprints (already in the DB), set via Studio Config zone or directly:

```python
# In a migration script or shell:
bp = env['dashboard.blueprint'].search([('key', '=', 'crm_customers')])
bp.scope_warning = "You cannot disable both 'Pipeline' and 'Leads' because at least one must stay on."
```

### Why this approach is "very dynamic"

| Property | How it works |
|---------|-------------|
| **Per-dashboard message** | Stored on the blueprint record — different warning per dashboard |
| **Translatable** | `translate=True` on the field — works with Odoo's built-in translation |
| **Studio-editable** | No code change needed to set/update the warning — purely data |
| **Non-blocking** | Warning shown but save is not prevented — same UX as v1 |
| **Graceful fallback** | Empty `scope_warning` = no warning shown, zero behaviour change |
| **Correct popup path** | Exposed via `related` field on pref — not from `get_studio_payload()` |

### What triggers the warning

Only when **all `include`-mode scopes are unticked** (pending state including unsaved add/remove). `restrict`-mode scopes (e.g. "My Pipeline") never trigger it.

---

## 📦 Updated Ship Order

| Order | Issue | Effort |
|-------|-------|--------|
| **1** | Filter `studio_search_actions` by host/graph model + "Show all models" toggle | 1–2 h |
| **2** | Remove pre-rendered empty context key row | 20 min |
| **3** | "Or host method" — fold into dev accordion or add help text | 30 min |
| **4** | Scope table truncation — add `title` attrs | 15 min |
| **5** | `scope_warning` field: model + payload + Studio UI + gear popup guard | 1–1.5 h |
| **6** | Zone-aware properties pane subtitles | 15 min |
| **7** | KPI filter label rename | 10 min |
| **8** | Layout mode visual grid strip | 1–2 h |
| **9** | Conditional Publish warning (menu change only) | 30 min |
| **10** | `Soft module depends` help text | 10 min |

