# EU Compliance Dashboards — action-599 Gap Map (Handoff)

**Date:** 2026-07-29  
**Status:** Approved (design dialogue) · Phase 1 implementation in progress (Task 10 acceptance: not merge-ready)  
**Phase 1 plan:** `docs/superpowers/plans/2026-07-29-eu-compliance-dashboards-phase-1.md`  
**Baseline:** `hr_attendance_dashboard_core` — Attendances → Management → Compliance Dashboard  
**Reference UI:** `http://localhost:19010/odoo/action-599` (DB action id may differ per DB; xmlid `hr_attendance_dashboard_core.action_compliance_dashboard` / server action)  
**Target host:** `dashboard_engine` presets (odoo-dashboards-19.1-v2) — Odoo-standard KPI / graph / list layouts  
**Related:** compliance detail prototype  
`odoo-dashboards-19.1-v2/.superpowers/brainstorm/compliance-dashboards-detail-prototype.html`

## Positioning (one line)

> action-599 is the **baseline Hub snapshot** (form). Wave 1 rebuilds it as a richer Hub preset and splits depth into five sibling dashboards — more information than 599, without stuffing everything into one form.

## Locked product shape (Wave 1 = 6)

| Code | Dashboard | Preset app (proposed) |
|------|-----------|------------------------|
| **H** | Compliance Hub | `attendance_compliance_hub` |
| **R** | Rest Period | `attendance_rest_dashboard` |
| **B** | Breaks | `attendance_breaks_dashboard` |
| **W** | Worktime Limits | `attendance_worktime_dashboard` |
| **P** | Protected workers (night + youth + holidays) | `attendance_protected_workers_dashboard` |
| **A** | Admin Policy Matrix | `attendance_compliance_policy_admin` |

**Out of Wave 1 EU SKU (keep on DE companions / later):** MiLoG, BUrlG leave alerts, ArbMedVV exams, Betriebsrat deep queues, ArbZG report runners — may remain as Hub *optional tiles* when DE modules installed, or stay on action-599 until a DE Hub SKU.

**Layout rule:** Hub + siblings = `dashboard_engine` blueprints (slots), not another `view_mode=form` mega-sheet.

---

## Gap map: action-599 → owner dashboard

Legend: **H/R/B/W/P/A** = Wave 1 owner · **DE** = German companion (not EU wave-1 depth) · **List** = stay as filtered list/action, dashboard only links · **New** = not on 599 today

### Header / suite chrome

| action-599 item | Field / action | Owner | Notes |
|-----------------|----------------|-------|-------|
| Company | `company_id` | **H** (+ all) | Every preset company-scoped; Hub shows active company |
| Generated at | `generated_at` | **H** | “Last refresh” meta on Hub |
| Refresh | `action_refresh` | **H** | Recompute Hub snapshot / invalidate caches |
| German HR Month-End | `action_open_month_end_wizard` | **DE** / Suite Ops link | Hub header shortcut only if `suite_ops` installed |
| Run Go-Live Checklist | `action_open_go_live_checklist` | **H** (link) | Keep as Hub admin shortcut |
| ArbZG §16 Reports | `action_open_arbzg_reports` | **DE** | Optional Hub button when module present |
| Works Council Matters | `action_open_betriebsrat_matters` | **DE** | Optional Hub / later DE board |
| Evidence Pack | `action_open_evidence_pack` | **DE** / List | Link only |
| Suite Settings | `action_open_settings` | **A** + Hub link | Policy Admin is primary; Hub keeps shortcut |

### Suite status

| action-599 item | Field | Owner | Notes |
|-----------------|-------|-------|-------|
| Deployment readiness | `deployment_readiness` | **H** | Hub status chip |
| Go-live readiness | `go_live_readiness` | **H** | Hub status chip |
| Upgrade pending | `upgrade_pending_count` | **H** or **A** | Prefer **A** if config-health; Hub can mirror count |

### KPI tiles (today)

| action-599 item | Field | Owner | Notes |
|-----------------|-------|-------|-------|
| Open violations | `open_violations_count` | **H** | Split also by domain on R/B/W/P when type known |
| Critical violations | `critical_violations_count` | **H** | Same |
| View all / critical | `action_open_*` | **List** | Deep link to violation list (filtered) |
| Pending retro (h) | `retro_pending_hours`, `pending_retro_count` | **DE** | Optional Hub tile if retro installed |
| §3 over 8h average | `employees_over_avg_count` | **W** | Move narrative to Worktime (EU avg), not DE-only §3 label |
| Near avg (7.5–8h) | `employees_near_avg_count` | **W** | Headroom / near-limit widget |

### Workflow queue

| action-599 item | Field | Owner | Notes |
|-----------------|-------|-------|-------|
| Pending approval violations | `pending_approval_violations_count` | **H** | Hub action queue |
| Missing catalogue types | `missing_violation_catalogue_count` | **A** or **H** | Config health → prefer **A** |
| Violation catalogue | `action_open_violation_catalogue` | **List** / **A** | Link |
| Pending Betriebsrat | `pending_betriebsrat_matters_count` | **DE** | Optional Hub |
| Pending requests | `pending_requests_count` | **H** | Hub workflow group |

### Holiday / extended (today)

| action-599 item | Field | Owner | Notes |
|-----------------|-------|-------|-------|
| Overdue holiday rest | `overdue_holiday_rest_count` | **P** | Protected workers (holidays section) |
| Youth workers count | `youth_workers_count` | **P** | + youth rest floor note on **R** when applies |
| Below Mindestlohn | `below_mindestlohn_count` | **DE** | Not EU wave-1 board |
| Open leave alerts (BUrlG) | `open_leave_alerts_count` | **DE** | |
| Overdue ArbMedVV exams | `overdue_arbmedvv_exams_count` | **DE** | |
| GDPR failed runs | `gdpr_failed_runs_count` | Wave 2 / optional Hub | Not a Wave-1 board |
| Open Betriebsvereinbarung | `open_betriebsvereinbarung_count` | **DE** | |

### Notebook lists

| action-599 item | Field | Owner | Notes |
|-----------------|-------|-------|-------|
| At-risk employees | `employee_risk_line_ids` | **H** (summary) + **W/P** | Hub top-N; domain boards full lists |
| Recent open violations | `violation_line_ids` | **H** | Hub queue; domain boards filter by type |

---

## New information (not on action-599) — must ship for “more than 599”

| New widget / info | Owner | Why it adds value |
|-------------------|-------|-------------------|
| **Company policy strip** (pack, country, counsel, Modified, effective hours, Enable) | **H** + strip on R/B/W | Country/company truth before judging findings |
| **Multi-company pack matrix** | **A** | Admin compare DE/FR/CH/NL/ES |
| **Settings health** (Enable off, blank hours, notify flags, cron, import QA) | **A** | Prevent false findings |
| Short daily rest + Strict blocked CI + earliest allowed time | **R** | Rest product core |
| Same-spell / intra-gap skip counts | **R** | Trust (no false overnight) |
| Compensatory due → overdue + **Mark fulfilled** | **R** | Open gap #3 from rest requirements |
| Weekly rest gaps | **R** | Art. 5 style |
| Break quota debt + >6h interrupt | **B** | Breaks product core |
| Pack/sector / Flexible vs Fixed | **B** / **A** | Country pack context |
| Daily / weekly / avg over + **headroom** | **W** | Planner value before breach |
| Night ban window breaches | **P** | Protected |
| Youth night/Sunday / rest floor applied | **P** (+ **R** floor) | Protected |
| Punctuality late/early (thin KPI) | Optional Hub only | Full punctuality board = Wave 2 |
| Trend graphs (week findings / blocks) | **H** / domain | Standard dashboard layout (graph slots) |
| Dept / team heat | Domain boards | Manager filter |

---

## Phase 1 must-have widgets (locked add-ons)

Same **6 dashboards** — extra widgets only (no new boards).

| Dashboard | Must-have widget | Purpose |
|-----------|------------------|---------|
| **H** Hub | “Why this finding” (rule + pack hours) | Manager sees legal basis without opening settings |
| **H** Hub | Channel chip (kiosk / import / form / systray) | Trust import vs live punch |
| **R** Rest | Derogation usage (used / max / period + avg window) | CH / NL packs — not DE-only |
| **R** Rest | Youth floor applied vs not | Sync with `youth_minimum_rest_hours` |
| **B** Breaks | Continuity interrupt countdown (still checked in) | Prevent breach before it lands |
| **W** Worktime | Forecast breach if planned hours continue | Planner value before Friday |
| **P** Protected | Next banned window per at-risk person | Night / Sunday / holiday |
| **A** Policy Admin | Company vs pack default side-by-side + last apply user/date | Drift and audit |

**Explicitly out of Phase 1 widgets:** full legal text on cards; badge-second debug; duplicate full violation lists on every board; GDPR/payroll as Hub tiles.

---

## Ownership cheat-sheet (quick)

```text
H  Hub          ← 599 suite status + open/critical + workflow + at-risk summary
                 + policy strip + cross-domain action queue + graphs
R  Rest         ← rest findings, blocks, earliest allow, comp ledger, weekly rest
B  Breaks       ← quota, interrupt, pack/sector break context
W  Worktime     ← caps, averages, headroom (absorbs §3/avg tiles from 599)
P  Protected    ← holidays overdue rest, youth, night
A  Policy Admin ← matrix, counsel, drift, Enable, catalogue gaps, settings health
DE             ← retro, Betriebsrat, MiLoG, BUrlG, ArbMedVV, ArbZG reports (links / later SKU)
List           ← full violation/request/attendance forms (dashboards only deep-link)
```

---

## Migration stance (action-599)

| Option | Decision |
|--------|----------|
| Keep form dashboard forever | **No** as EU hero UI |
| Replace menu with Hub preset | **Yes** (Wave 1 end state) |
| Keep server action as redirect | **Yes** — `action_open_dashboard` → Hub blueprint URL |
| Dual-run period | Optional: form behind “Classic snapshot” for DE consultants |

---

## Phases — how many dashboards

| Phase | Count | Dashboards | Goal |
|-------|------:|------------|------|
| **Phase 1 — EU core** | **6** | Hub (**H**), Rest (**R**), Breaks (**B**), Worktime (**W**), Protected workers (**P**), Policy Admin (**A**) | More than action-599; country/company policy; Working Time Directive depth |
| **Phase 2 — Ops** | **+2** (total **8**) | Punctuality, Overtime balance | Daily manager ops (late/early, OT ledger) |
| **Phase 3 — Adjacent SKUs** | **+2–3** (total **10–11**) | HSE hub; DE Betriebsrat/evidence (and optional classic-599 redirect retire) | Other product lines — not mixed into EU Hub |

**Running total**

```text
Phase 1:  6 dashboards
Phase 2:  8 dashboards  (+2)
Phase 3: 10–11 dashboards  (+2–3)
```

**Not a dashboard (any phase):** full attendance form, pack apply wizards, violation workflow, settings — dashboards only deep-link there.

### Phase 1 build order (inside the 6)

1. **A** Policy Admin (matrix + health) — country/company trust  
2. **H** Hub preset (599 parity + policy strip + graph/list slots)  
3. **R** Rest (blocks, earliest allow, compensatory ledger)  
4. **B** Breaks  
5. **W** Worktime (absorbs §3 / avg tiles from 599)  
6. **P** Protected workers (night + youth + holidays)

### Phase 2 detail

| # | Dashboard | Notes |
|---|-----------|--------|
| 7 | **Punctuality** | Late / early / negl clamps / dept heat (was Hub-only thin KPI in Phase 1) |
| 8 | **Overtime balance** | When `overtime_eu` (or DE OT) feeds balances — not the same as Worktime caps |

### Phase 3 detail

| # | Dashboard | Notes |
|---|-----------|--------|
| 9 | **HSE hub** | From `odoo-eu-hse` (+ attendance bridge if installed) |
| 10 | **DE works council / evidence** | German SKU — Betriebsrat, evidence pack |
| 11 (optional) | **DE compliance classic** | Only if consultants still need form-599 parity after Hub replaces menu |

---

## Acceptance checks

- Every visible field/button on action-599 is mapped above (H/R/B/W/P/A/DE/List).  
- Hub on `dashboard_engine` shows **more** than 599 for EU: policy strip + domain KPIs + trends.  
- Phase 1 must-have widgets (Hub why/channel, Rest derogation/youth, Breaks countdown, Worktime forecast, Protected next ban, Admin pack diff) are present or explicitly ticketed.  
- Switching company changes pack numbers (e.g. ES 12h vs DE 11h) on strip / matrix.  
- Module not installed → tile hidden or “not installed”, never fake zero.  
- DE-only counts do not block EU Hub publish.

---

## Prototype reference

Interactive mock (policy strip + matrix + company switcher):  
`custom/addons/gritxi/odoo-dashboards-19.1-v2/.superpowers/brainstorm/compliance-dashboards-detail-prototype.html`
