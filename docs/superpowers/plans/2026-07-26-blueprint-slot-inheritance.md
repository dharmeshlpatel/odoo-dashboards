# Blueprint Slot Inheritance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let blueprints bi-directionally share Manage / right KPI / bottom slot links (V1 pool parity), with key-based dedupe and existing per-slot group/module visibility.

**Architecture:** Add a symmetric `share_blueprint_ids` M2M on `dashboard.blueprint`. At payload time, resolve the connected component, union shared-section slots, order current blueprint first, dedupe by `(section, key)` then `(section, action_xmlid)`, then apply `_is_visible`. Header and primary button stay local. Seeds link CRM↔Sales customer blueprints and drop duplicated Sales-owned keys from CRM.

**Tech Stack:** Odoo 19 ORM (`dashboard.blueprint` / `dashboard.blueprint.slot`), existing OWL slot renderer (no JS change if payload shape unchanged), XML form + seed data, Python tests in `test_dashboard_blueprint.py`.

**Design spec:** `docs/superpowers/specs/2026-07-26-blueprint-slot-inheritance-design.md`

## Global Constraints

- Module path: `custom/addons/gritxi/odoo-dashboards-19.1-v2/dashboard_engine`
- Bump `__manifest__.py` version once at the end of the feature (e.g. `19.0.1.0.37` or next free)
- Shared sections only: `kpi`, `button_box`, `bottom`, `menu_views`, `menu_new`, `menu_reports`
- Never share: header / `header_item_ids` / primary button / `primary_action_variant_ids`
- Visibility: reuse `dashboard.blueprint.slot._is_visible` (groups + modules + context)
- Dedupe: first wins — current blueprint first, then peers by `(blueprint.sequence, blueprint.id)`, slots by `sequence`
- Same `host_model_id` required between shared blueprints (ValidationError otherwise)
- Upgrade-safe: `_inherit` patterns only; no core edits
- Staging: do not delete issue attendance records (N/A here); keep commits when verifying UI
- After code changes: `-u dashboard_engine`, restart :19005 with `--dev=xml,assets`, hard-refresh

## File map

| File | Responsibility |
|---|---|
| `models/dashboard_blueprint.py` | `share_blueprint_ids`, component walk, `_effective_slots()`, wire into `_build_slots_payloads` |
| `views/dashboard_blueprint_views.xml` | “Share links with” on Card layout / Manage |
| `data/seed_crm_parity.xml` | Drop keys owned by Sales once shared; keep CRM-only keys |
| `data/seed_sales_parity.xml` | Set `share_blueprint_ids` ↔ CRM (or companion data file) |
| `data/seed_website_parity.xml` / POS (if present) | Optional share links to sales/crm customer packs |
| `tests/test_dashboard_blueprint.py` | Unit tests for union, dedupe, visibility, host mismatch |
| `migrations/19.0.1.0.XX/post-*.py` | Wire share M2M + unlink duplicate CRM slots on existing DBs |
| Design/plan docs | Already created under `docs/superpowers/` |

---

### Task 1: Model — share M2M + connected component + effective slots

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py`
- Test: `dashboard_engine/tests/test_dashboard_blueprint.py`

**Interfaces:**
- Produces:
  - `share_blueprint_ids: Many2many("dashboard.blueprint")`
  - `SHARED_SLOT_SECTIONS: frozenset[str]`
  - `_share_component(self) -> dashboard.blueprint` (recordset, includes self)
  - `_effective_slots(self) -> dashboard.blueprint.slot` (ordered, deduped, not yet visibility-filtered)
  - `_slot_dedupe_key(slot) -> tuple | None`

- [ ] **Step 1: Write failing tests**

Add tests (names indicative):

```python
def test_share_blueprints_union_slots_bidirectional(self):
    """A↔B: each sees the other's kpi/menu/bottom slots."""

def test_share_dedupe_prefers_current_blueprint_key(self):
    """Same (section, key): current blueprint wins."""

def test_share_dedupe_falls_back_to_action_xmlid(self):
    """Empty key: collapse on (section, action_xmlid)."""

def test_share_rejects_different_host_model(self):
    """ValidationError when sharing across host models."""

def test_share_does_not_merge_header_or_primary(self):
    """Header items / primary label stay local (smoke assert on payload builder inputs)."""

def test_shared_slot_still_respects_groups(self):
    """Slot from peer with group user lacks → filtered by _is_visible."""
```

- [ ] **Step 2: Run tests — expect FAIL**

Run:

```bash
PY=venv/python3.12.11/bin/python
$PY server/odoo-bin -c config/dashboard_engine_v2.conf --stop-after-init \
  -d dashboard_engine_v2.ee -u dashboard_engine \
  --test-enable --test-tags /dashboard_engine:TestDashboardBlueprint \
  --log-level=test
```

Expected: missing attribute / FAIL on new tests.

- [ ] **Step 3: Implement model helpers**

On `DashboardBlueprint`:

```python
SHARED_SLOT_SECTIONS = frozenset({
    "kpi", "button_box", "bottom",
    "menu_views", "menu_new", "menu_reports",
})

share_blueprint_ids = fields.Many2many(
    "dashboard.blueprint",
    "dashboard_blueprint_share_rel",
    "blueprint_id",
    "share_blueprint_id",
    string="Share links with",
    help="Bi-directional: Manage / right KPIs / bottom layers are pooled "
         "with these blueprints (same host model). Header and primary "
         "button stay local.",
)

@api.constrains("share_blueprint_ids", "host_model_id")
def _check_share_same_host(self):
    for rec in self:
        for other in rec.share_blueprint_ids:
            if other.host_model_id and rec.host_model_id \
                    and other.host_model_id != rec.host_model_id:
                raise ValidationError(...)
```

Helpers (sketch):

```python
def _share_component(self):
    """Undirected BFS over share_blueprint_ids, including self."""

def _slot_dedupe_key(self, slot):
    if slot.key:
        return ("key", slot.section, slot.key)
    if slot.action_xmlid:
        return ("action", slot.section, slot.action_xmlid)
    return None  # never dedupe

def _effective_slots(self):
    """Ordered union of shared-section slots; current BP first; dedupe."""
```

Keep ownership: `_effective_slots` returns slot records from **peer blueprints unchanged** (action/domain/groups still those records’).

- [ ] **Step 4: Wire payload builder**

In `_build_slots_payloads` (today filters `self.slot_ids`), switch to:

```python
candidates = self._effective_slots()
visible = candidates.filtered(lambda s: s._is_visible(ctx))
# preserve effective order — do not re-sort only by sequence across owners
```

If `.filtered` loses order, iterate manually:

```python
visible = [s for s in candidates if s._is_visible(ctx)]
```

Ensure `_run_slot_action` / click handlers can resolve a slot by id even when the slot’s `blueprint_id` ≠ rendering blueprint (search by id globally, still check visibility).

- [ ] **Step 5: Run tests — expect PASS**

Same command as Step 2. Expected: new tests green; existing suite still green.

- [ ] **Step 6: Commit** (only if user asks)

```text
feat(dashboard_engine): bi-directional blueprint slot sharing with key dedupe
```

---

### Task 2: Form UX — Share links with

**Files:**
- Modify: `dashboard_engine/views/dashboard_blueprint_views.xml`
- Test: manual UI on :19005

**Interfaces:**
- Consumes: `share_blueprint_ids`
- Produces: editable M2M on blueprint form

- [ ] **Step 1: Add field to Card layout page**

Place near the top of **Card layout** (before Header), with short help:

```xml
<group>
  <group>
    <field name="share_blueprint_ids" widget="many2many_tags"
           options="{'no_create': True}"
           domain="[('id', '!=', id), ('host_model_id', '=', host_model_id)]"/>
  </group>
</group>
<p class="text-muted">
  Bi-directional: Manage, right KPIs, and both bottom layers are pooled
  with these dashboards. Header and the left primary button stay local.
  Each link still respects its own groups / installed apps.
</p>
```

- [ ] **Step 2: Upgrade + hard-refresh**

```bash
# -u dashboard_engine, restart :19005 --dev=xml,assets
```

Expected: field visible; picking Sales on CRM also shows CRM on Sales after save (symmetric M2M).

- [ ] **Step 3: Commit** (only if user asks)

---

### Task 3: Seeds + migration — CRM ↔ Sales customer pack

**Files:**
- Modify: `dashboard_engine/data/seed_crm_parity.xml`
- Modify: `dashboard_engine/data/seed_sales_parity.xml` (or small new `seed_share_links.xml`)
- Create: `dashboard_engine/migrations/19.0.1.0.XX/post-share-customer-slots.py`
- Modify: `dashboard_engine/__manifest__.py` (version bump + data file if new)

**Interfaces:**
- Consumes: Task 1 runtime union
- Produces: CRM↔Sales share; CRM no longer owns duplicate Sales keys

**Duplicate keys to prefer Sales-owned (verify against current XML before deleting):**

- `box_total_due`, `box_total_overdue`
- `bottom_deliveries`, `bottom_invoiced`, `bottom_sales` (if identical intent)
- Any other `(section, key)` present on both

CRM-only keys (`unassigned`, `view_leads`, meetings, …) stay on CRM.

- [ ] **Step 1: Add share link in seed data**

On both blueprints (or one side if relation is written both ways by ORM):

```xml
<field name="share_blueprint_ids" eval="[(4, ref('dashboard_engine.blueprint_crm_customers'))]"/>
```

(Use real xmlids from `seed_blueprints.xml` / parity files.)

- [ ] **Step 2: Remove CRM copies of Sales-owned slots**

Delete/comment CRM slot records whose keys are owned by Sales after sharing. Keep module_depends/groups on the Sales-owned slots.

- [ ] **Step 3: Migration for existing DBs**

Post-migrate:

1. Search blueprints `crm_customers` / `sales_customers` by `key`.
2. `write` symmetric `share_blueprint_ids`.
3. Unlink CRM slots whose `(section, key)` exist on Sales (only those known duplicate keys — be conservative).

- [ ] **Step 4: Test**

- Automated: extend a test that published CRM payload includes Sales `to_deliver` KPI when share is set and `sale` installed / groups allow.
- Manual: open CRM Customers and Sales Customers on :19005; confirm Manage/KPI/bottom union; header/primary differ; user without Sales group does not see Sales links.

- [ ] **Step 5: Commit** (only if user asks)

---

### Task 4: Action resolution safety + N-level smoke

**Files:**
- Modify: `dashboard_engine/models/dashboard_blueprint.py` (slot action entrypoints)
- Test: `dashboard_engine/tests/test_dashboard_blueprint.py`

**Interfaces:**
- Consumes: `_effective_slots`, slot ids from peer blueprints
- Produces: clicks work for shared peer slots

- [ ] **Step 1: Audit click / RPC paths**

Find methods that do `bp.slot_ids.filtered(lambda s: s.key == …)` (e.g. around line ~2357). Switch to search on `dashboard.blueprint.slot` by id/key **within `_share_component()`** so peer slots resolve.

- [ ] **Step 3: N-level test**

```python
def test_share_transitive_three_blueprints(self):
    """A↔B and B↔C ⇒ A sees C's shared slots (connected component)."""
```

- [ ] **Step 4: Run full `/dashboard_engine` tests — expect 0 failed**

- [ ] **Step 5: Bump manifest version, upgrade, restart UI**

---

### Task 5: Docs sync (German HR N/A — engine docs only)

**Files:**
- Modify: `docs/superpowers/specs/2026-07-26-blueprint-slot-inheritance-design.md` if behavior drifts
- Optional: short note in `dashboard_engine/README.md` under builder concepts

- [ ] **Step 1: Document Share links with + dedupe rules** in README (10–15 lines)
- [ ] **Step 2: Commit** (only if user asks)

---

## Manual verification checklist

1. CRM Customers + Sales Customers both installed/published, `share_blueprint_ids` linked.
2. CRM card shows Sales KPIs/Manage/bottom **and** CRM ones; Sales card shows both.
3. User without Sales groups: Sales links hidden on both cards.
4. Uninstall/disable Sales soft-dep modules: Sales links hide via `module_depends`.
5. Header title/image and left primary button remain different per blueprint.
6. Duplicate `box_total_due` appears once (Sales definition wins when viewing Sales; when viewing CRM, CRM-owned copy removed so Sales definition shows once).
7. Third blueprint sharing with Sales appears on CRM via transitive component.

## Out of scope (follow-ups)

- Read-only “inherited slots” UI on the form
- Sharing graph/scopes/menu
- Cross-host-model sharing
- Automatic creation of a blank “pool” blueprint
