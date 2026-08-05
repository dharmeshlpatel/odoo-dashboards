# Attendance Compliance Dashboards — Build Inventory

**Date:** 2026-07-29  
**Status:** Planning inventory (widget checklist)  
**Host:** `Custom ACD OWL` — `ir.actions.client` per dashboard inside `hr-attendance-compliance-v2` modules  
**Host decision:** NOT `odoo-dashboards-19.1-v2` engine — see implementation plan for rationale (SKU isolation + release independence)  
**Baseline:** action-599 / `hr_attendance_dashboard_core` Compliance Dashboard  
**Source of truth for count & ownership:**  
`docs/superpowers/specs/2026-07-29-eu-compliance-dashboards-gap-map-design.md`

This file answers: **how many dashboards**, and **what KPIs / graphs / donuts / lists** each one shows.

---

## How many dashboards?

| Phase | Count | Dashboards |
|-------|------:|------------|
| **Phase 1 — EU core** | **6** | Hub, Rest, Breaks, Worktime, Protected workers, Policy Admin |
| **Phase 2 — Ops** | **+2 → 8** | + Punctuality, + Overtime balance |
| **Phase 3 — Adjacent** | **+2–3 → 10–11** | + HSE hub, + DE works council/evidence, (+ optional classic-599) |

```text
Phase 1:  6 dashboards   ← build first
Phase 2:  8 dashboards
Phase 3: 10–11 dashboards
```

**Not a dashboard (any phase):** attendance form, pack apply wizards, settings, full violation workflow — boards only **deep-link** to filtered lists/forms.

**Shared chrome (every board):** company scope, date range (or “as of”), last refresh, module-not-installed → hide tile (never fake zero).

---

## Widget legend

| Code | Meaning |
|------|---------|
| **KPI** | Summary card (number ± trend) |
| **Line** | Line / area trend chart |
| **Bar** | Vertical or horizontal bar chart |
| **Donut** | Doughnut / pie distribution |
| **Heat** | Heatmap (day × hour or weekday) |
| **List** | Table / list view (top-N or queue) |
| **Strip** | Policy / status strip (not a chart) |
| **Link** | Deep link to Odoo list/form (filtered) |

---

## Phase 1 — six dashboards (must build)

Build order: **A → H → R → B → W → P**.

### 1. Policy Admin (**A**) — `attendance_compliance_policy_admin`

**Job:** Country/company trust before judging findings.

| Type | Widget | Shows |
|------|--------|--------|
| **Strip** | Settings health | Enable off, blank hours, notify flags, cron, import QA |
| **List** / matrix | Multi-company pack matrix | DE / FR / CH / NL / ES (and others installed) side-by-side |
| **List** | Company vs pack default | Hours, counsel, last apply user/date, Modified flag |
| **KPI** | Missing catalogue types | Count of missing violation types |
| **KPI** | Upgrade / config drift | Pending upgrade or drift chips |
| **Link** | Suite settings / pack apply | Open settings or pack wizard |

**Charts in Phase 1:** none required (matrix + lists are enough).  
**Out:** full legal text on cards.

---

### 2. Compliance Hub (**H**) — `attendance_compliance_hub`

**Job:** Replace action-599 as the EU hero snapshot; more than 599, not a mega form.

| Type | Widget | Shows |
|------|--------|--------|
| **Strip** | Company policy strip | Pack, country, counsel, Modified, effective hours, Enable |
| **Strip** | Suite status | Deployment / go-live readiness, upgrade pending |
| **KPI** | Open violations | Count → Link filtered violation list |
| **KPI** | Critical violations | Count → Link |
| **KPI** | Pending approval violations | Workflow queue |
| **KPI** | Pending attendance requests | Workflow queue |
| **KPI** | At-risk employees (summary) | Top count; domain boards own full lists |
| **KPI** | Thin punctuality (optional) | Late / early **count only** if punctuality installed (full board = Phase 2) |
| **Strip** | Why this finding | Rule + pack hours (manager sees legal basis) |
| **Strip** | Channel chip | Kiosk / import / form / systray |
| **Line** | Findings / blocks trend | Last 7–30 days (cross-domain) |
| **Donut** | Open findings by domain | Rest / Breaks / Worktime / Protected / Other |
| **List** | Recent open violations | Top-N queue |
| **List** | At-risk employees (top-N) | Summary only |
| **Link** | DE shortcuts (if installed) | Month-end, ArbZG reports, Betriebsrat, evidence — header only |

**Out of Hub Phase 1:** full punctuality analytics, GDPR/payroll tiles, duplicate full violation lists for every domain.

---

### 3. Rest Period (**R**) — `attendance_rest_dashboard`

**Job:** Daily / weekly rest, blocks, compensatory ledger.

| Type | Widget | Shows |
|------|--------|--------|
| **Strip** | Rest policy strip | Min rest hours, pack, Strict/Warn, intra-gap setting |
| **KPI** | Insufficient rest (open) | Count |
| **KPI** | Strict blocked check-ins | Count |
| **KPI** | Compensatory due | Count |
| **KPI** | Compensatory overdue | Count |
| **KPI** | Weekly rest gaps | Count |
| **KPI** | Same-spell / intra-gap skips | Trust metric (false overnight avoided) |
| **KPI** | Derogation usage | Used / max / period (CH/NL packs) |
| **KPI** | Youth floor applied | Applied vs not |
| **Line** | Rest findings trend | 7–30 days |
| **Donut** | Rest finding mix | Daily vs weekly vs compensatory |
| **Bar** | Dept / team rest pressure | Optional manager filter |
| **List** | Blocked / short-rest queue | Employee, earliest allowed time, gap hours |
| **List** | Compensatory ledger | Due → overdue + **Mark fulfilled** action |
| **Link** | Attendance / violation | Drill to record |

---

### 4. Breaks (**B**) — `attendance_breaks_dashboard`

**Job:** Break quota, interrupt, continuity.

| Type | Widget | Shows |
|------|--------|--------|
| **Strip** | Break policy strip | Pack/sector, Flexible vs Fixed/Planned, 6h/9h (or tiers) |
| **KPI** | Break quota debt | Employees / open tickets |
| **KPI** | >6h interrupt breaches | Count |
| **KPI** | Continuity / auto sign-out events | Count (if enabled) |
| **KPI** | Continuity interrupt countdown | Still checked-in, minutes to breach |
| **Line** | Break findings trend | 7–30 days |
| **Donut** | Break finding mix | Quota / interrupt / continuity / other |
| **Bar** | Dept break pressure | Optional |
| **List** | Open break violations | Queue with mode/engine |
| **List** | Open spells needing break | Live interrupt watch list |
| **Link** | Attendance / violation | Drill |

---

### 5. Worktime Limits (**W**) — `attendance_worktime_dashboard`

**Job:** Caps, averages, headroom (absorbs §3/avg tiles from 599).

| Type | Widget | Shows |
|------|--------|--------|
| **Strip** | Worktime policy strip | Daily / weekly / average limits, pack |
| **KPI** | Over daily limit | Count |
| **KPI** | Over weekly limit | Count |
| **KPI** | Over average limit | Count (ex-§3 narrative → EU avg) |
| **KPI** | Near average (headroom) | e.g. 7.5–8h band |
| **KPI** | Forecast breach | If planned hours continue |
| **Line** | Average hours trend | Rolling window |
| **Donut** | Breach type mix | Daily / weekly / average |
| **Bar** | Dept / team hours vs limit | Headroom view |
| **List** | Employees over / near limit | Full at-risk for worktime |
| **Link** | Attendance / timesheet / violation | Drill |

---

### 6. Protected workers (**P**) — `attendance_protected_workers_dashboard`

**Job:** Night + youth + holiday rest (one board).

| Type | Widget | Shows |
|------|--------|--------|
| **Strip** | Protected policy strip | Night window, youth rules, holiday rest pack |
| **KPI** | Night ban breaches | Count |
| **KPI** | Youth workers | Count in scope |
| **KPI** | Youth night / Sunday issues | Count |
| **KPI** | Overdue holiday rest | Count |
| **KPI** | Next banned window | At-risk people with next ban start |
| **Donut** | Protected finding mix | Night / youth / holiday |
| **Bar** | Night breaches by hour/window | Optional |
| **List** | At-risk protected employees | With next banned window |
| **List** | Open protected violations | Queue |
| **Link** | Rest board (youth floor) | Cross-link when floor applies |

---

## Phase 2 — +2 ops dashboards

### 7. Punctuality (**Pu**) — thin ops board (not the full mock)

**Job:** Daily manager ops for late / early departure. Full “enterprise” widgets later.

| Type | Widget | Shows | Phase |
|------|--------|--------|-------|
| **KPI** | On-time rate % | Period | **v1** |
| **KPI** | Late arrivals | Count ± trend | **v1** |
| **KPI** | Avg delay (min) | Period | **v1** |
| **KPI** | Early departures | Count | **v1** |
| **KPI** | Attendance completion % | Expected vs checked-in | **v1** |
| **KPI** | Employees at risk | Repeat late / threshold | **v1** |
| **KPI** | Pending corrections | Count | **v1** |
| **KPI** | Avg early arrival | Informational only | **v1** (optional) |
| **Line** | Arrival / on-time trend | 30 days | **v1** |
| **Donut** | Arrival status | Early / On-time / Late | **v1** |
| **Bar** | Department performance | On-time % | **v2** |
| **Bar** | Shift performance | On-time % | **v2** |
| **Bar** | Late arrivals by hour | Histogram | **v2** |
| **Heat** | Weekly late heatmap | Mon–Fri × hours | Later |
| **List** | Top late employees | Late count, avg delay, trend | **v1** |
| **List** | Top punctual employees | On-time %, streak | **v2** |
| **List** | Employees requiring attention | Warnings / patterns | **v1** |
| **List** | Pending actions | Corrections, approvals, letters | **v1** |
| **List** | Live attendance feed | Recent punches + status | Later (costly) |
| **List** | Rule insights | Threshold bullets (not black-box AI) | **v2** |

**Out of Punctuality v1:** 12 KPI wall, AI essay block, PDF/email schedules, branch rankings, monthly calendar, trophy widgets.

**Filters (v1):** date range, company, department, shift, manager, attendance status.  
**Drill-down:** Late → dept → employee → attendance → correction / violation.

---

### 8. Overtime balance (**O**)

**Job:** OT ledger / TOIL — not the same as Worktime caps (**W**).

| Type | Widget | Shows |
|------|--------|--------|
| **KPI** | Compensable OT hours | Period / open balance |
| **KPI** | TOIL due / overdue | Counts |
| **KPI** | Paid OT vs time-off | Split |
| **Line** | OT balance trend | Weeks |
| **Donut** | OT by reason / tier | If tiered rules installed |
| **Bar** | Dept OT pressure | Optional |
| **List** | Employees with OT balance | Ledger rows |
| **Link** | OT lines / payslip inputs | When payroll bridge installed |

Depends on `overtime_eu` and/or DE OT modules.

---

## Phase 3 — +2–3 adjacent dashboards

### 9. HSE hub

| Type | Widget | Shows |
|------|--------|--------|
| **KPI** | Open incidents / overdue training / equipment due | From `odoo-eu-hse` |
| **Donut** | HSE status mix | By severity or type |
| **List** | Overdue actions | Queue |
| **Link** | Attendance bridge | When HSE attendance bridge installed |

### 10. DE works council / evidence

| Type | Widget | Shows |
|------|--------|--------|
| **KPI** | Pending Betriebsrat matters | Count |
| **KPI** | Open Betriebsvereinbarung | Count |
| **KPI** | Evidence packs | Ready / pending |
| **List** | Matters queue | DE workflow |
| **Link** | Evidence pack / ArbZG reports | Classic DE tools |

### 11. DE compliance classic (optional)

Only if consultants still need form-599 parity after Hub replaces the menu. Prefer **redirect to Hub**, not a permanent twin board.

---

## Quick matrix (Phase 1 + Punctuality v1)

| Dashboard | KPIs | Line | Bar | Donut | Heat | Lists |
|-----------|-----:|------|-----|-------|------|-------|
| Policy Admin | 2–3 | — | — | — | — | Matrix + health + drift |
| Hub | 5–8 | 1 | — | 1 | — | Violations + at-risk top-N |
| Rest | 6–8 | 1 | 0–1 | 1 | — | Blocks + compensatory |
| Breaks | 4–6 | 1 | 0–1 | 1 | — | Violations + interrupt watch |
| Worktime | 5–7 | 1 | 1 | 1 | — | Over/near limit |
| Protected | 4–6 | — | 0–1 | 1 | — | At-risk + violations |
| Punctuality v1 | 6–8 | 1 | — | 1 | — | Top late + attention + pending |

---

## What not to build as a dashboard

- Full attendance form / kiosk UI  
- Pack apply wizard as a “board”  
- Violation resolution workflow (use list + form)  
- Settings pages  
- Payroll / DATEV / GDPR as Phase 1 Hub tiles  

---

## Related docs

- Gap map / phases: `2026-07-29-eu-compliance-dashboards-gap-map-design.md`  
- Phase 1 plan: `../plans/2026-07-29-eu-compliance-dashboards-phase-1.md`  
- UI prototype: `../../.superpowers/brainstorm/compliance-dashboards-detail-prototype.html`
