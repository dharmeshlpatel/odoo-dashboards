# Panel Filters, Linked My & Smart Maps — Product Design

**Date:** 2026-08-03  
**Module:** `dashboard_engine` (+ CRM / Sales / 360 presets)  
**Status:** Approved direction (architect + product dialogue)  
**Supersedes (partially):** surface rules in `2026-07-28-restrict-scope-surface-matrix-design.md` for **linked commercial** cards — that matrix stays true for unmapped / odd surfaces  
**Related:** hub persistence design, kanban lens design, dynamic graph config Studio

---

## Positioning (one line)

> Search decides **which cards**. Gear decides **panel numbers**. Linking + smart maps extend My and gear filters to **commercial** buttons; odd buttons opt in via Studio — never crash, never guess wrong dates in silence.

---

## Product mental model (locked)

| Question | Model | Tool |
|----------|--------|------|
| Which cards do I see? | **Host** | Kanban search bar + lenses |
| What numbers on each card? | **Graph** (+ mapped peers) | Configuration gear |

**One job → one place.** Do not put Host Custom Filter in the gear (duplicates search).

---

## Value goals

1. **Honest labels** — “My Pipeline and Sales Orders” only when Sales is installed **and** linked **and** maps are active.  
2. **Linked cards feel one product** — My and gear periods/custom filter narrow commercial CRM **and** Sales surfaces together.  
3. **Standalone stays simple** — same-model panel filters; no cross-app map required.  
4. **AI-smart, human-safe** — system suggests maps; only validated maps run; fail-open if unsure.  
5. **End users never open Studio to link** — seeds + auto-link cover CRM↔Sales.  
6. **Builders stay powerful** — Studio/Advanced maps + “when My ON” conditions for Meetings/Deliveries/etc.

---

## Surface matrix — Product B′ (default seed)

### When standalone (no share link)

| Surface | Gear include (Pipeline/Leads) | Gear period + Custom Filter | My |
|---------|-------------------------------|-----------------------------|-----|
| Graph / primary | Yes | Yes | Yes |
| Right KPIs (same model as graph) | No* | Yes (panel pack) | Yes |
| Bottoms / views / reports same model | No* | Yes (panel pack) | Yes (commercial) |
| Other-model bottoms (Meetings, …) | No | No | No unless Studio when-My |
| New | No | No | My **defaults** only |

\*Include scopes stay **graph-primary** (chart story). Panel pack applies **period + custom + My** to same-model commercial slots.

### When linked + Sales (maps active)

| Surface | My Pipeline and Sales Orders ON | Gear period / Custom Filter |
|---------|----------------------------------|-----------------------------|
| Graph / primary | Yes | Yes |
| Right KPIs CRM + Sales | Yes if mapped | Yes if mapped |
| Bottoms crm.lead / sale.order | Yes if mapped | Yes if mapped |
| Views / reports commercial (mapped) | Yes | Yes |
| New Opp / Quotation | My defaults | — |
| Meetings / Deliveries / unmapped | No | No — unless Studio when-My / period field map |

---

## Smart maps (dynamic + AI-assisted, crash-safe)

### Runtime hard rules

1. Missing field on target model → **skip leaf** (`_domain_applies_to_model`).  
2. Model not installed → **skip**.  
3. No map row → **do not filter** that surface (fail open).  
4. Never invent domains on every card load without a stored map.

### Who maps

| Actor | Role |
|-------|------|
| Product seeds | CRM↔Sales My + period (`user_id`, `date_order`) |
| Auto on share-link | High-confidence accept (same name + ttype; known aliases) |
| Studio / Advanced | Override / odd models (e.g. picking `scheduled_date`) |
| End user | Link or use standalone only — **no mapping UI** |

### Suggest heuristics (Studio “AI assist”)

| Gear concept | Suggest |
|--------------|---------|
| Assignee / My | `user_id`, else many2one→`res.users` ranked |
| Create period | `create_date`, `date_order`, `date` |
| Closed period | close/won/done-like names; builder confirms |
| Custom Filter leaf | Same field name + compatible ttype only |

Ambiguous (scheduled vs planned on deliveries) → **no silent auto**; seed default or Studio pick.

---

## Architecture building blocks

```text
Viewer blueprint (gear prefs)
    ├── include scopes          → graph (chart) only
    ├── restrict My + panel domain
    │       ├── same model slots     → direct apply
    │       └── scope.target maps    → translated apply
    └── when-My / when-panel conditions (Studio)
            └── odd slots (Meetings, …)

Share link → which slots appear
Seeds + auto-link → which maps exist
Lenses → host card list using full panel domain for With KPIs / Attention
```

**Bug to fix first:** shared slots must resolve My/panel filters against the **viewer** blueprint prefs, not the slot-owner blueprint.

---

## Implementation phases

### Phase 0 — Foundation & honesty (short, high ROI)

**Goal:** Stop lying labels and broken Group By / linked My ignore.

| # | Work | Success |
|---|------|---------|
| 0.1 | Viewer owns My for shared slots | Tick My on CRM card → linked Sales KPI respects it |
| 0.2 | Lens parity: With KPIs / Needs attention use full `_effective_graph_settings` domain | List cards match chart filters |
| 0.3 | Gear help copy: Host vs Graph (search vs Configuration) | Consultants stop mixing jobs |
| 0.4 | Label honesty: “…and Sales Orders” only if sale installed **and** share link / map active | Label matches behavior |

**Exit:** No new models yet; tests green; CRM Customers My + lenses trustworthy.

---

### Phase 1 — Cross-model My map (commercial core)

**Goal:** Linked My = pipeline + sales orders on mapped commercial surfaces.

| # | Work | Success |
|---|------|---------|
| 1.1 | Model `dashboard.blueprint.scope.target` (or equivalent o2m on restrict scope) | Fields: target model, domain, module_depends, apply_kpi/bottom/views/reports/new-defaults |
| 1.2 | Seed CRM My → `crm.lead` + `sale.order` | Defaults apply_kpi/bottom/views/reports true for commercial |
| 1.3 | Resolve restrict domain per slot model via viewer prefs + map | Fail-open if invalid |
| 1.4 | New menus: `default_user_id` / assignee context only | Create never blocked |
| 1.5 | Studio + Advanced UI for target maps (builder) | End user unused |
| 1.6 | Tests: linked My KPI/bottom/views; unmapped Meetings untouched | Regression CRM Customers |

**Exit:** Product B′ My for CRM↔Sales. Label correct when linked.

---

### Phase 2 — Panel filter pack (periods + Custom Filter beyond chart)

**Goal:** Gear “today” / Custom Filter also narrow mapped commercial bottoms/right/views/reports.

| # | Work | Success |
|---|------|---------|
| 2.1 | Extract “panel domain” from prefs (period + custom + My; not include-OR story) | Reusable API |
| 2.2 | Period field map on target (e.g. create→`date_order`) | Auto-suggest + seed |
| 2.3 | Apply panel domain to mapped surfaces | “Today” → Sales Orders bottom uses order date |
| 2.4 | Custom Filter leaves: copy only validated same-name fields; else skip | No crash |
| 2.5 | Include scopes stay chart-only | Pipeline/Leads do not rewrite Sales bottoms incorrectly |
| 2.6 | Tests for period on sale.order bottom; skip when unmapped | |

**Exit:** Gear filters feel like one panel control for commercial work.

---

### Phase 3 — Smart link & AI assist (delight, still safe)

**Goal:** Linking feels intelligent; no Studio for happy path.

| # | Work | Success |
|---|------|---------|
| 3.1 | On share-link write: propose + auto-accept high-confidence maps | CRM↔Sales zero-click maps |
| 3.2 | Studio “Suggest maps” wizard (ranked fields, one-click accept) | Builder trust |
| 3.3 | Warning: label promises Sales but no map | Honest UX |
| 3.4 | Optional: Graph Model picker (host-linked candidates) | Chart switch without breaking slots (phase-1 chart-only override) |

**Exit:** Consultants link boards; maps appear; odd models still opt-in.

---

### Phase 4 — Odd surfaces & Studio conditions

**Goal:** Meetings / Deliveries / custom apps can follow My or panel filters **when authored**.

| # | Work | Success |
|---|------|---------|
| 4.1 | Condition token: “restrict scope X ticked” / “panel filters active” | Slot compute + action |
| 4.2 | Studio/Advanced UX to attach when-My + domain | Meetings example optional seed |
| 4.3 | Delivery period map only after explicit field pick or seed | scheduled_date vs planned — never silent wrong guess |
| 4.4 | Docs for partners: when to map vs when-My | |

**Exit:** Full extensibility without forcing every bottom into My.

---

### Phase 5 — Polish, performance, catalog

**Goal:** Ship-ready product quality.

| # | Work | Success |
|---|------|---------|
| 5.1 | Batch domain apply; avoid N+1 on map resolve | Kanban stay fast |
| 5.2 | Multi-company: rely on record rules; no double company domain | |
| 5.3 | More preset seeds (Website, Invoice reports) as maps mature | |
| 5.4 | Auto-composed My labels from active maps (optional) | No drift |
| 5.5 | Partner guide + in-app help | |

---

## Phase sequence (dependency)

```text
Phase 0 (honesty + viewer My + lenses)
    → Phase 1 (My cross-model map)
        → Phase 2 (panel filter pack)
            → Phase 3 (smart link / Graph Model picker)
                → Phase 4 (Studio when-My for odd)
                    → Phase 5 (polish)
```

Do **not** start Phase 2 before Phase 1 (My map is the same plumbing).  
Do **not** force Phase 4 into Phase 1 (keeps first ship focused).

---

## Out of scope (explicit)

- Host Custom Filter inside Configuration gear (use search bar).  
- Live LLM inventing domains on every kanban load.  
- My domain on **New** create (defaults only).  
- Blind “My everywhere” including unmapped warehouse/calendar without Studio.

---

## Success criteria (product)

1. Standalone CRM: My + gear periods match chart and same-model commercial slots; Meetings unchanged.  
2. Linked CRM+Sales: label “My Pipeline and Sales Orders”; My + today narrow Sales Orders bottom via `date_order`.  
3. End user never opens Studio to link.  
4. Wrong/missing map → skip filter, kanban never crashes.  
5. Lenses With KPIs / Needs attention agree with chart filters.

---

## Recommended first sprint

**Ship Phase 0 + Phase 1 only.**  
That alone fixes consultant confusion (linked My + honest label + lenses) and unlocks the map model Phase 2–4 reuse.
