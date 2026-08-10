# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Dashboard Studio — payload, CRUD, catalogs."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDashboardStudio(TransactionCase):
    def _host_model(self):
        return self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def _make_bp_with_graph(self):
        """Blueprint with graph_model set (Studio graph config tests)."""
        return self._studio_blueprint()

    def _studio_blueprint(self):
        return self.env["dashboard.blueprint"].create(
            {
                "name": "Studio Partners",
                "key": "test_studio_partners",
                "host_model_id": self._host_model().id,
                "primary_button_label": "Open",
                "graph_caption": "Partners",
                "graph_model": "res.partner",
                "graph_measure": "__count",
                "graph_groupby": "id",
                "state": "draft",
                "slot_ids": [
                    (
                        0,
                        0,
                        {
                            "key": "child_count",
                            "name": "Children",
                            "section": "kpi",
                            "label": "Child",
                            "label_plural": "Children",
                            "compute_model": "res.partner",
                            "relate_field": "parent_id",
                            "compute_domain": "[]",
                            "action_model": "res.partner",
                            "show_if_zero": True,
                        },
                    )
                ],
            }
        )

    def test_get_studio_payload_includes_kpi(self):
        bp = self._studio_blueprint()
        payload = bp.get_studio_payload()
        self.assertEqual(payload["key"], "test_studio_partners")
        self.assertEqual(payload["state"], "draft")
        self.assertEqual(payload["host_model"], "res.partner")
        kpi = next(s for s in payload["slots"] if s["section"] == "kpi")
        self.assertEqual(kpi["label"], "Child")
        self.assertEqual(kpi["label_plural"], "Children")
        self.assertIn("condition_ids", kpi)
        self.assertTrue(kpi.get("owned"))

    def test_get_studio_payload_marks_shared_slots_readonly(self):
        """Studio lists share-pool slots as owned=False (edit on source)."""
        host = self.env["ir.model"]._get("res.partner")
        hub = self.env["dashboard.blueprint"].create(
            {
                "name": "Studio Hub",
                "key": "test_studio_hub_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 1,
            }
        )
        pack = self.env["dashboard.blueprint"].create(
            {
                "name": "Studio Pack",
                "key": "test_studio_pack_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 2,
            }
        )
        shared = self.env["dashboard.blueprint.slot"].create(
            {
                "blueprint_id": pack.id,
                "key": "shared_open",
                "name": "Shared Open",
                "section": "kpi",
                "label": "Shared Open",
                "show_if_zero": True,
                "compute_model": "res.partner",
                "relate_field": "parent_id",
            }
        )
        hub.share_link_ids = [(4, pack.id)]
        self.assertIn(shared, hub._effective_slots())
        payload = hub.get_studio_payload()
        row = next(s for s in payload["slots"] if s["id"] == shared.id)
        self.assertFalse(row["owned"])
        self.assertEqual(row["source_blueprint_key"], pack.key)
        preview = hub.studio_preview_payload()
        kpi_keys = [s.get("key") for s in (preview.get("slots") or {}).get("kpis") or []]
        self.assertIn("shared_open", kpi_keys)

    def test_studio_write_slot_updates_kpi_label(self):
        bp = self._studio_blueprint()
        slot = bp.slot_ids.filtered(lambda s: s.key == "child_count")
        payload = bp.studio_write_slot(
            slot.id,
            {
                "label": "Kid",
                "label_plural": "Kids",
                "show_if_zero": False,
                "icon": "fa-star",
            },
        )
        slot.invalidate_recordset()
        self.assertEqual(slot.label, "Kid")
        self.assertEqual(slot.label_plural, "Kids")
        self.assertFalse(slot.show_if_zero)
        self.assertEqual(slot.icon, "fa-star")
        updated = next(s for s in payload["slots"] if s["id"] == slot.id)
        self.assertEqual(updated["label"], "Kid")

    def test_action_open_studio_returns_client_action(self):
        bp = self._studio_blueprint()
        action = bp.action_open_studio()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "dashboard_engine.studio")
        self.assertEqual(action["params"]["blueprint_id"], bp.id)

    def test_studio_write_blueprint_primary(self):
        bp = self._studio_blueprint()
        payload = bp.studio_write_blueprint(
            {
                "primary_button_label": "Analyze",
                "graph_caption": "Trend",
                "graph_measure": "__count",
            }
        )
        self.assertEqual(bp.primary_button_label, "Analyze")
        self.assertEqual(payload["graph_caption"], "Trend")
        self.assertEqual(bp.graph_measure, "__count")

    def test_studio_create_reorder_unlink_kpi(self):
        bp = self._studio_blueprint()
        payload = bp.studio_create_slot(
            "kpi",
            {"label": "New KPI", "label_plural": "New KPIs"},
        )
        created_id = payload["created_slot_id"]
        self.assertTrue(created_id)
        kpis = [s for s in payload["slots"] if s["section"] == "kpi"]
        self.assertEqual(len(kpis), 2)
        ordered = [created_id, bp.slot_ids.filtered(lambda s: s.key == "child_count").id]
        payload = bp.studio_reorder_slots("kpi", ordered)
        kpis = [s for s in payload["slots"] if s["section"] == "kpi"]
        self.assertEqual([s["id"] for s in kpis], ordered)
        payload = bp.studio_unlink_slot(created_id)
        self.assertEqual(len([s for s in payload["slots"] if s["section"] == "kpi"]), 1)

    def test_studio_totals_and_shortcuts_lock_count_amount(self):
        """Totals/Shortcuts share KPI figure path; Shows is always Count + Amount."""
        bp = self._studio_blueprint()
        total_payload = bp.studio_create_slot("button_box", {"label": "Due"})
        total = bp.slot_ids.browse(total_payload["created_slot_id"])
        self.assertEqual(total.section, "button_box")
        self.assertEqual(total.value_mode, "count_amount")
        self.assertEqual(total.compute_model, "res.partner")
        total.write({"value_mode": "count"})
        self.assertEqual(total.value_mode, "count_amount")

        short_payload = bp.studio_create_slot("bottom", {"label": "Meetings"})
        shortcut = bp.slot_ids.browse(short_payload["created_slot_id"])
        self.assertEqual(shortcut.section, "bottom")
        self.assertEqual(shortcut.value_mode, "count_amount")
        bp.studio_write_slot(
            shortcut.id,
            {
                "compute_model": "res.partner",
                "relate_field": "parent_id",
                "compute_domain": "[('is_company', '=', True)]",
                "value_mode": "amount",
            },
        )
        shortcut.invalidate_recordset()
        self.assertEqual(shortcut.value_mode, "count_amount")
        self.assertEqual(shortcut.compute_domain, "[('is_company', '=', True)]")
        self.assertEqual(shortcut.relate_field, "parent_id")

    def test_studio_reorder_slots_rejects_stale_list(self):
        bp = self._studio_blueprint()
        with self.assertRaises(UserError):
            bp.studio_reorder_slots("kpi", [999999])

    def test_studio_catalogs(self):
        bp = self._studio_blueprint()
        fields = bp.studio_model_fields("res.partner")
        self.assertTrue(any(f["name"] == "name" for f in fields))
        icons = bp.studio_header_icons()
        self.assertTrue(any(i["value"] == "fa-envelope" for i in icons))
        actions = bp.studio_search_actions("partner", limit=10)
        self.assertTrue(isinstance(actions, dict))
        self.assertIn("actions", actions)
        self.assertIn("scope_label", actions)
        self.assertTrue(isinstance(actions["actions"], list))

        scoped = bp.studio_search_actions("", limit=20, all_models=False)
        self.assertTrue(scoped.get("scope_label"))
        if scoped.get("scoped"):
            allowed = {bp.host_model_name, bp.graph_model or bp.host_model_name}
            for hit in scoped["actions"]:
                res_model = hit.get("res_model") or False
                if res_model:
                    self.assertIn(res_model, allowed)

        all_hits = bp.studio_search_actions("", limit=20, all_models=True)
        self.assertFalse(all_hits["scoped"])
        self.assertEqual(all_hits["scope_label"], "Showing all actions")

        focused = bp.studio_search_actions(
            "", limit=20, all_models=False, res_model=bp.graph_model or bp.host_model_name
        )
        self.assertTrue(focused.get("scope_label"))
        if focused.get("scoped") and (bp.graph_model or bp.host_model_name):
            allowed = {bp.graph_model or bp.host_model_name}
            for hit in focused["actions"]:
                res_model = hit.get("res_model") or False
                if res_model:
                    self.assertIn(res_model, allowed)

        chart_models = bp.studio_search_chart_models("", limit=20, all_models=False)
        self.assertIn("models", chart_models)
        self.assertTrue(chart_models.get("scoped"))
        self.assertTrue(chart_models.get("scope_label"))
        all_chart = bp.studio_search_chart_models("", limit=20, all_models=True)
        self.assertFalse(all_chart.get("scoped"))

        groupby = bp.studio_groupby_fields(bp.graph_model or bp.host_model_name)
        self.assertTrue(isinstance(groupby, list))
        self.assertTrue(all("id" in row and "name" in row for row in groupby))
        self.assertFalse(any(row["name"] == "id" for row in groupby))
        # Raw date/datetime excluded; period virtual tags (x_*) allowed.
        for row in groupby:
            if row["ttype"] in ("date", "datetime"):
                self.assertTrue(row["name"].startswith("x_"))

        stored = bp.studio_model_fields(
            bp.host_model_name, ["integer", "float", "monetary"], True
        )
        self.assertTrue(all(row.get("store") for row in stored))

    @staticmethod
    def _menu_publish_would_confirm(payload):
        """Mirror Studio OWL publish() confirm gate (payload contract)."""
        live_leaf = payload.get("generated_menu_leaf") or ""
        if not live_leaf:
            return False
        next_name = payload.get("menu_name") or ""
        live_parent = payload.get("generated_menu_parent_id") or False
        next_parent = payload.get("menu_parent_id") or False
        return next_name != live_leaf or next_parent != live_parent

    def test_scope_warning_studio_write_payload_and_pref(self):
        bp = self._studio_blueprint()
        msg = "At least one of 'Pipeline' or 'Leads' must stay on."
        # No Chart Model Options yet — blueprint field still works.
        payload = bp.studio_write_blueprint({"scope_warning": msg})
        self.assertEqual(bp.scope_warning, msg)
        self.assertEqual(payload.get("scope_warning"), msg)

        pref = self.env["dashboard.user.pref"].create(
            {
                "blueprint_id": bp.id,
                "user_id": self.env.user.id,
            }
        )
        self.assertEqual(pref.scope_warning, msg)

        payload = bp.studio_write_blueprint({"scope_warning": False})
        self.assertFalse(bp.scope_warning)
        self.assertEqual(payload.get("scope_warning") or "", "")
        pref.invalidate_recordset()
        self.assertFalse(pref.scope_warning)

    def test_scope_warning_per_graph_variant(self):
        bp = self._studio_blueprint()
        bp.write(
            {
                "primary_action_xmlid": "base.action_partner_form",
                "scope_warning": "Blueprint fallback",
            }
        )
        # Payload heal creates the Default option and copies the warning.
        payload = bp.get_studio_payload()
        self.assertTrue(payload.get("graph_variants"))
        default_id = payload["default_graph_variant_id"]
        self.assertTrue(default_id)
        self.assertEqual(
            next(
                r["scope_warning"]
                for r in payload["graph_variants"]
                if r["id"] == default_id
            ),
            "Blueprint fallback",
        )

        lead_msg = "Keep Pipeline or Leads on."
        sale_msg = "Keep at least one Sales filter on."
        payload = bp.studio_write_graph_variant(
            default_id, {"scope_warning": lead_msg}
        )
        self.assertEqual(
            next(
                r["scope_warning"]
                for r in payload["graph_variants"]
                if r["id"] == default_id
            ),
            lead_msg,
        )
        bp.invalidate_recordset(["scope_warning"])
        self.assertEqual(bp.scope_warning, lead_msg)

        payload = bp.studio_create_graph_variant(
            {
                "graph_model": "res.partner",
                "primary_button_label": "Second",
                "primary_action_xmlid": "base.action_partner_form",
            }
        )
        second_id = payload.get("created_graph_variant_id")
        bp.studio_write_graph_variant(second_id, {"scope_warning": sale_msg})

        pref = self.env["dashboard.user.pref"].create(
            {
                "blueprint_id": bp.id,
                "user_id": self.env.user.id,
            }
        )
        # No gear pick → Default option warning.
        self.assertEqual(pref.scope_warning, lead_msg)
        pref.preferred_graph_variant_id = second_id
        pref.invalidate_recordset(["scope_warning"])
        self.assertEqual(pref.scope_warning, sale_msg)

    def test_publish_confirm_payload_menu_contract(self):
        """Payload fields must drive the Studio Publish confirm dialog."""
        bp = self._studio_blueprint()
        parent = self.env.ref("base.menu_administration")
        bp.write(
            {
                "menu_name": "Studio Partners Menu",
                "menu_parent_id": parent.id,
            }
        )
        payload = bp.get_studio_payload()
        self.assertFalse(payload.get("generated_menu_leaf"))
        self.assertFalse(self._menu_publish_would_confirm(payload))

        bp.action_publish()
        payload = bp.get_studio_payload()
        self.assertEqual(payload["generated_menu_leaf"], "Studio Partners Menu")
        self.assertEqual(payload["generated_menu_parent_id"], parent.id)
        self.assertTrue(payload.get("generated_menu_name"))
        self.assertFalse(self._menu_publish_would_confirm(payload))

        # Live menu out of sync with blueprint (confirm gate uses leaf vs menu_name).
        bp.generated_menu_id.write({"name": "Stale Live Menu"})
        bp.invalidate_recordset()
        payload = bp.get_studio_payload()
        self.assertEqual(payload["menu_name"], "Studio Partners Menu")
        self.assertEqual(payload["generated_menu_leaf"], "Stale Live Menu")
        self.assertTrue(self._menu_publish_would_confirm(payload))

        bp.action_publish()
        payload = bp.get_studio_payload()
        self.assertEqual(payload["generated_menu_leaf"], "Studio Partners Menu")
        self.assertFalse(self._menu_publish_would_confirm(payload))

    def test_studio_preview_payload_live(self):
        bp = self._studio_blueprint()
        partner = self.env["res.partner"].create({"name": "Studio Preview Co"})
        samples = bp.studio_sample_records("Studio Preview")
        self.assertTrue(any(s["id"] == partner.id for s in samples))
        preview = bp.studio_preview_payload(partner.id)
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["res_id"], partner.id)
        self.assertIn("Studio Preview", preview["title"])
        self.assertIn("kpis", preview["slots"])
        self.assertTrue(isinstance(preview["graph_bars"], list))

    def test_studio_preview_keeps_zero_kpis(self):
        """Studio live map must not hide KPIs the editor still lists."""
        bp = self._studio_blueprint()
        slot = bp.slot_ids.filtered(lambda s: s.key == "child_count")
        slot.show_if_zero = False
        partner = self.env["res.partner"].create({"name": "Zero KPI Co"})
        # Live kanban hides zeros.
        live = bp._build_slots_payload(partner)
        self.assertFalse(any(k["key"] == "child_count" for k in live["kpis"]))
        # Studio preview keeps them so left map matches the right list.
        preview = bp.studio_preview_payload(partner.id)
        self.assertTrue(preview["ok"])
        keys = [k["key"] for k in preview["slots"]["kpis"]]
        self.assertIn("child_count", keys)

    def test_action_open_studio_for_key(self):
        bp = self._studio_blueprint()
        action = self.env["dashboard.blueprint"].action_open_studio_for_key(bp.key)
        self.assertEqual(action["tag"], "dashboard_engine.studio")
        self.assertEqual(action["params"]["blueprint_id"], bp.id)

    def test_create_wizard_opens_studio(self):
        host = self._host_model()
        wiz = self.env["dashboard.blueprint.create.wizard"].create(
            {
                "name": "Wizard Dash",
                "host_model_id": host.id,
                "key": "test_wizard_dash",
                "open_studio": True,
            }
        )
        action = wiz.action_create()
        bp = self.env["dashboard.blueprint"].search([("key", "=", "test_wizard_dash")])
        self.assertTrue(bp)
        self.assertTrue(bp.slot_ids.filtered(lambda s: s.key == "starter_kpi"))
        self.assertEqual(action["tag"], "dashboard_engine.studio")
        self.assertEqual(action["params"]["blueprint_id"], bp.id)

    def test_action_open_advanced(self):
        bp = self._studio_blueprint()
        action = bp.action_open_advanced()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "dashboard.blueprint")
        self.assertEqual(action["res_id"], bp.id)
        self.assertEqual(action["views"], [(False, "form")])

    def test_studio_layout_default_and_validate(self):
        bp = self._studio_blueprint()
        default = bp.studio_default_layout()
        self.assertEqual(default["version"], 1)
        self.assertTrue(default["rows"])
        payload = bp.get_studio_payload()
        self.assertFalse(payload["layout_is_custom"])
        self.assertEqual(payload["layout"]["version"], 1)
        with self.assertRaises(UserError):
            bp.studio_write_layout(
                {
                    "version": 1,
                    "rows": [
                        {
                            "id": "r1",
                            "cols": [
                                {
                                    "id": "c1",
                                    "span": 15,
                                    "widget": {"type": "kpis"},
                                }
                            ],
                        }
                    ],
                }
            )

    def test_studio_layout_publish_order(self):
        bp = self._studio_blueprint()
        bp.write(
            {
                "graph_model": "res.partner",
                "graph_measure": "__count",
                "graph_groupby": "id",
            }
        )
        layout = {
            "version": 1,
            "rows": [
                {
                    "id": "r1",
                    "cols": [
                        {"id": "c1", "span": 12, "widget": {"type": "kpis"}},
                    ],
                },
                {
                    "id": "r2",
                    "cols": [
                        {"id": "c2", "span": 12, "widget": {"type": "primary"}},
                    ],
                },
            ],
        }
        bp.studio_write_layout(layout)
        self.assertTrue(bp.studio_layout)
        bp.action_publish()
        arch = bp.generated_view_id.arch_db
        kpi_pos = arch.find('data-studio-widget="kpis"')
        primary_pos = arch.find('data-studio-widget="primary"')
        self.assertGreater(kpi_pos, 0)
        self.assertGreater(primary_pos, kpi_pos)
        # Manage must not leak into the card body (stays in ⋮ menu).
        self.assertNotIn('name="kanban_manage_views"', arch.split('<t t-name="menu"')[0])

    def test_studio_layout_classic_patterns(self):
        bp = self._studio_blueprint()
        layout = bp.studio_default_layout()
        bp.studio_write_layout(layout)
        bp.action_publish()
        arch = bp.generated_view_id.arch_db
        card = arch.split('<t t-name="menu"')[0]
        self.assertIn('data-studio-widget="primary"', card)
        self.assertIn('data-studio-widget="kpis"', card)
        self.assertIn('class="row footer"', card)
        self.assertNotIn('name="kanban_manage_views"', card)

    def test_studio_payload_includes_setup_fields(self):
        bp = self._studio_blueprint()
        bp.write({"menu_name": "Partners Dash", "menu_sequence": 42})
        payload = bp.get_studio_payload()
        self.assertEqual(payload["host_model_id"], bp.host_model_id.id)
        self.assertTrue(payload["host_editable"])
        self.assertEqual(payload["menu_name"], "Partners Dash")
        self.assertEqual(payload["menu_sequence"], 42)
        self.assertIn("module_ids", payload)
        self.assertIn("share_link_ids", payload)
        self.assertIn("multi_company", payload)

    def test_studio_write_menu_fields(self):
        bp = self._studio_blueprint()
        parent = self.env.ref("dashboard_engine.menu_dashboard_engine_root")
        payload = bp.studio_write_blueprint(
            {
                "menu_name": "Studio Menu",
                "menu_parent_id": parent.id,
                "menu_sequence": 15,
            }
        )
        self.assertEqual(bp.menu_name, "Studio Menu")
        self.assertEqual(bp.menu_parent_id, parent)
        self.assertEqual(bp.menu_sequence, 15)
        self.assertEqual(payload["menu_name"], "Studio Menu")
        self.assertEqual(payload["setup_cleanup_count"], 0)

    def test_studio_payload_includes_hub_group(self):
        bp = self._studio_blueprint()
        group = self.env["dashboard.blueprint.group"].create(
            {
                "name": "Sales Hub",
                "sequence": 10,
                "hub_menu_id": self.env.ref("dashboard_engine.dashboard_hub_default").id,
            }
        )
        bp.write({"group_id": group.id})
        payload = bp.get_studio_payload()
        self.assertEqual(payload["group_id"], group.id)
        self.assertEqual(payload["group_name"], "Sales Hub")

    def test_studio_write_hub_group(self):
        bp = self._studio_blueprint()
        group = self.env["dashboard.blueprint.group"].create(
            {
                "name": "CRM Hub",
                "sequence": 20,
                "hub_menu_id": self.env.ref("dashboard_engine.dashboard_hub_default").id,
            }
        )
        payload = bp.studio_write_blueprint({"group_id": group.id})
        self.assertEqual(bp.group_id, group)
        self.assertEqual(payload["group_id"], group.id)
        self.assertEqual(payload["group_name"], "CRM Hub")

        payload = bp.studio_write_blueprint({"group_id": False})
        self.assertFalse(bp.group_id)
        self.assertFalse(payload["group_id"])
        self.assertEqual(payload.get("group_name") or "", "")

    def test_studio_host_change_blocked_when_published(self):
        bp = self._studio_blueprint()
        bp.write(
            {
                "graph_model": "res.partner",
                "graph_measure": "__count",
                "graph_groupby": "id",
                "menu_name": "Pub",
            }
        )
        bp.action_publish()
        self.assertEqual(bp.state, "published")
        other = self.env["ir.model"].search([("model", "=", "res.users")], limit=1)
        with self.assertRaises(UserError):
            bp.studio_write_blueprint({"host_model_id": other.id})

    def test_studio_host_change_clears_invalid_header_field(self):
        bp = self._studio_blueprint()
        bp.write({"header_title_field": "__not_a_real_field__"})
        users = self.env["ir.model"].search([("model", "=", "res.users")], limit=1)
        self.assertTrue(users)
        payload = bp.studio_write_blueprint({"host_model_id": users.id})
        self.assertEqual(bp.host_model_name, "res.users")
        self.assertFalse(bp.header_title_field)
        self.assertGreaterEqual(payload["setup_cleanup_count"], 1)

    def test_studio_search_setup_catalogs(self):
        bp = self._studio_blueprint()
        models = bp.studio_search_models("partner", limit=10)
        self.assertTrue(any(m["model"] == "res.partner" for m in models))
        menus = bp.studio_search_menus("Dashboard", limit=10)
        self.assertTrue(isinstance(menus, list))
        modules = bp.studio_search_modules("base", limit=10)
        self.assertTrue(any(m.get("technical") == "base" for m in modules))
        self.env["dashboard.blueprint.group"].create({
            "name": "Search Sales",
            "sequence": 1,
            "hub_menu_id": self.env.ref("dashboard_engine.dashboard_hub_default").id,
        })
        hub_groups = bp.studio_search_hub_groups("Sales", limit=10)
        self.assertTrue(any(g["name"] == "Search Sales" for g in hub_groups))

    def _partner_create_date_field(self):
        return self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "create_date")],
            limit=1,
        )

    def test_studio_payload_includes_graph_link_and_custom_filter(self):
        bp = self._studio_blueprint()
        create_date = self._partner_create_date_field()
        bp.write(
            {
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_domain": "[]",
                "period_field_id": create_date.id,
                "include_child_records": False,
            }
        )
        payload = bp.get_studio_payload()
        self.assertEqual(payload.get("graph_data_field"), "parent_id")
        self.assertIn("graph_domain", payload)
        self.assertEqual(payload["graph_domain"], "[]")
        self.assertIn("period_field_id", payload)
        self.assertEqual(payload["period_field_id"], create_date.id)
        self.assertIn("closed_period_field_id", payload)
        self.assertIn("include_child_records", payload)
        self.assertFalse(payload["include_child_records"])

    def test_studio_write_graph_data_field_and_domain(self):
        bp = self._studio_blueprint()
        bp.write({"graph_model": "res.partner"})
        bp.studio_write_blueprint(
            {
                "graph_data_field": "parent_id",
                "graph_domain": "[('name', '!=', False)]",
                "include_child_records": True,
            }
        )
        self.assertEqual(bp.graph_data_field, "parent_id")
        self.assertIn("name", bp.graph_domain or "")
        self.assertTrue(bp.include_child_records)

    def test_studio_write_rejects_invalid_graph_domain(self):
        bp = self._studio_blueprint()
        with self.assertRaises(UserError):
            bp.studio_write_blueprint({"graph_domain": "not a domain"})

    def test_studio_variant_custom_filter_per_option(self):
        """Custom Filter lives on the Chart Model Option and feeds runtime domain."""
        bp = self._studio_blueprint()
        bp.write(
            {
                "primary_action_xmlid": "base.action_partner_form",
                "graph_data_field": "parent_id",
                "graph_domain": "[('is_company', '=', True)]",
            }
        )
        payload = bp.studio_create_graph_variant({})
        vid = payload["created_graph_variant_id"]
        row = next(v for v in payload["graph_variants"] if v["id"] == vid)
        self.assertIn("is_company", row.get("graph_domain") or "")

        bp.studio_write_graph_variant(
            vid, {"graph_domain": "[('active', '=', True)]"}
        )
        variant = self.env["dashboard.blueprint.graph.variant"].browse(vid)
        self.assertIn("active", variant.graph_domain or "")
        self.assertIn("active", bp.graph_domain or "")  # Default option mirrors

        with self.assertRaises(UserError):
            bp.studio_write_graph_variant(vid, {"graph_domain": "not a domain"})

        settings = bp._effective_graph_settings()
        self.assertTrue(
            any(
                isinstance(leaf, (list, tuple)) and leaf[0] == "active"
                for leaf in settings["domain"]
            ),
            settings["domain"],
        )

    def test_studio_payload_scope_includes_domain_and_description(self):
        bp = self._studio_blueprint()
        Scope = self.env["dashboard.blueprint.scope"]
        scope = Scope.create(
            {
                "blueprint_id": bp.id,
                "name": "Pipeline",
                "description": "Open opportunities",
                "mode": "include",
                "domain": "[('type', '=', 'opportunity')]",
                "default_on": True,
                "sequence": 10,
            }
        )
        payload = bp.get_studio_payload()
        row = next(s for s in payload["scopes"] if s["id"] == scope.id)
        self.assertEqual(row["description"], "Open opportunities")
        self.assertIn("opportunity", row["domain"] or "")
        self.assertEqual(row["mode"], "include")

    def test_studio_scope_crud_and_reorder(self):
        bp = self._studio_blueprint()
        payload = bp.studio_create_scope(
            {
                "name": "Leads",
                "mode": "include",
                "domain": "[('type', '=', 'lead')]",
                "default_on": False,
            }
        )
        sid = payload["created_scope_id"]
        self.assertTrue(sid)
        bp.studio_write_scope(
            sid,
            {
                "description": "Lead rows",
                "default_on": True,
                "domain": "[('type', '=', 'lead')]",
            },
        )
        scope = self.env["dashboard.blueprint.scope"].browse(sid)
        self.assertEqual(scope.description, "Lead rows")
        self.assertTrue(scope.default_on)
        other = bp.studio_create_scope(
            {"name": "Mine", "mode": "restrict", "domain": "[]"}
        )
        oid = other["created_scope_id"]
        bp.studio_reorder_scopes([oid, sid])
        names = bp.scope_ids.sorted("sequence").mapped("name")
        self.assertEqual(names[:2], ["Mine", "Leads"])
        bp.studio_unlink_scope(oid)
        self.assertFalse(self.env["dashboard.blueprint.scope"].browse(oid).exists())

    def test_studio_write_scope_rejects_bad_domain(self):
        bp = self._studio_blueprint()
        payload = bp.studio_create_scope(
            {"name": "X", "mode": "include", "domain": "[]"}
        )
        with self.assertRaises(UserError):
            bp.studio_write_scope(
                payload["created_scope_id"], {"domain": "not a domain"}
            )

    def test_studio_graph_variant_crud_and_reorder(self):
        bp = self._studio_blueprint()
        bp.write(
            {
                "primary_action_xmlid": "base.action_partner_form",
                "graph_data_field": "parent_id",
            }
        )
        payload = bp.studio_create_graph_variant({})
        vid = payload["created_graph_variant_id"]
        self.assertTrue(vid)
        row = next(v for v in payload["graph_variants"] if v["id"] == vid)
        self.assertEqual(row["graph_model"], "res.partner")
        self.assertTrue(row["is_default"])
        bp.studio_write_graph_variant(
            vid,
            {
                "primary_button_label": "Partner chart",
                "graph_data_field": "commercial_partner_id",
            },
        )
        variant = self.env["dashboard.blueprint.graph.variant"].browse(vid)
        self.assertEqual(variant.primary_button_label, "Partner chart")
        self.assertEqual(bp.primary_button_label, "Partner chart")
        other = bp.studio_create_graph_variant(
            {
                "graph_model": "res.partner",
                "primary_button_label": "Second",
                "primary_action_xmlid": "base.action_partner_form",
            }
        )
        oid = other["created_graph_variant_id"]
        bp.studio_set_default_graph_variant(oid)
        self.assertTrue(
            self.env["dashboard.blueprint.graph.variant"].browse(oid).is_default
        )
        self.assertFalse(variant.is_default)
        self.assertEqual(bp.primary_button_label, "Second")
        bp.studio_reorder_graph_variants([oid, vid])
        labels = bp.graph_variant_ids.sorted("sequence").mapped("primary_button_label")
        self.assertEqual(labels[:2], ["Second", "Partner chart"])
        bp.studio_unlink_graph_variant(oid)
        self.assertFalse(
            self.env["dashboard.blueprint.graph.variant"].browse(oid).exists()
        )
        self.assertTrue(variant.exists().is_default)

    def test_studio_graph_variant_date_filter_crud(self):
        """Per-option Date Filters list (Studio step 1 — config only)."""
        bp = self._studio_blueprint()
        bp.write(
            {
                "primary_action_xmlid": "base.action_partner_form",
                "graph_data_field": "parent_id",
            }
        )
        Field = self.env["ir.model.fields"]
        create_date = Field.search(
            [("model", "=", "res.partner"), ("name", "=", "create_date")], limit=1
        )
        write_date = Field.search(
            [("model", "=", "res.partner"), ("name", "=", "write_date")], limit=1
        )
        if not create_date or not write_date:
            self.skipTest("create_date/write_date missing on res.partner")
        bp.write({"period_field_id": create_date.id})
        payload = bp.studio_create_graph_variant({})
        vid = payload["created_graph_variant_id"]
        row = next(v for v in payload["graph_variants"] if v["id"] == vid)
        self.assertTrue(row.get("date_filters"))
        self.assertEqual(row["date_filters"][0]["field_name"], "create_date")

        created = bp.studio_create_graph_variant_date_filter(
            vid, {"field_id": write_date.id, "label": "Last Update"}
        )
        df_id = created["created_graph_variant_date_filter_id"]
        self.assertTrue(df_id)
        labels = [
            d["label"]
            for v in created["graph_variants"]
            if v["id"] == vid
            for d in v["date_filters"]
        ]
        self.assertIn("Last Update", labels)

        bp.studio_write_graph_variant_date_filter(df_id, {"label": "Updated On"})
        df = self.env["dashboard.blueprint.graph.variant.date.filter"].browse(df_id)
        self.assertEqual(df.label, "Updated On")
        self.assertEqual(df.field_name, "write_date")

        bp.studio_unlink_graph_variant_date_filter(df_id)
        self.assertFalse(df.exists())
        # Blur-after-remove must not raise (Studio label blur can race unlink).
        bp.studio_write_graph_variant_date_filter(df_id, {"label": "Gone"})

    def test_date_filter_default_periods_seed_pref(self):
        """Builder default months/years seed first gear open; user picks win later."""
        bp = self._studio_blueprint()
        bp.write(
            {
                "primary_action_xmlid": "base.action_partner_form",
                "graph_data_field": "parent_id",
            }
        )
        Field = self.env["ir.model.fields"]
        create_date = Field.search(
            [("model", "=", "res.partner"), ("name", "=", "create_date")], limit=1
        )
        mq = self.env["period.month.quarter"].search([], limit=1)
        year = self.env["period.year"].search([], limit=1)
        if not create_date or not mq or not year:
            self.skipTest("date field or period catalogs missing")
        bp.write({"period_field_id": create_date.id})
        payload = bp.studio_create_graph_variant({})
        vid = payload["created_graph_variant_id"]
        row = next(v for v in payload["graph_variants"] if v["id"] == vid)
        df_id = row["date_filters"][0]["id"]
        self.assertTrue(payload.get("period_mq_catalog"))
        self.assertTrue(payload.get("period_year_catalog"))

        bp.studio_write_graph_variant_date_filter(
            df_id,
            {
                "default_period_mq_ids": [mq.id],
                "default_period_year_ids": [year.id],
            },
        )
        df = self.env["dashboard.blueprint.graph.variant.date.filter"].browse(df_id)
        self.assertEqual(df.default_period_mq_ids, mq)
        self.assertEqual(df.default_period_year_ids, year)

        pref = self.env["dashboard.user.pref"].create(bp._default_pref_values())
        line = pref.period_line_ids.filtered(lambda l: l.field_name == "create_date")[:1]
        self.assertTrue(line)
        self.assertEqual(line.period_mq_ids, mq)
        self.assertEqual(line.period_year_ids, year)

        other_year = self.env["period.year"].search([("id", "!=", year.id)], limit=1)
        if other_year:
            line.write({"period_year_ids": [(6, 0, other_year.ids)]})
            pref._sync_pref_period_lines()
            kept = pref.period_line_ids.filtered(
                lambda l: l.field_name == "create_date"
            )[:1]
            self.assertEqual(kept.period_year_ids, other_year)

    def test_pref_period_lines_follow_chart_model_option(self):
        """Live gear date rows sync from option date_filter_ids; domain uses them."""
        bp = self._studio_blueprint()
        bp.write(
            {
                "primary_action_xmlid": "base.action_partner_form",
                "graph_data_field": "parent_id",
            }
        )
        Field = self.env["ir.model.fields"]
        create_date = Field.search(
            [("model", "=", "res.partner"), ("name", "=", "create_date")], limit=1
        )
        write_date = Field.search(
            [("model", "=", "res.partner"), ("name", "=", "write_date")], limit=1
        )
        year = self.env["period.year"].search([], limit=1)
        if not create_date or not write_date or not year:
            self.skipTest("date fields or period.year missing")
        bp.write({"period_field_id": create_date.id})
        payload = bp.studio_create_graph_variant({})
        vid = payload["created_graph_variant_id"]
        bp.studio_create_graph_variant_date_filter(
            vid, {"field_id": write_date.id, "label": "Updated On"}
        )

        pref = self.env["dashboard.user.pref"].create(bp._default_pref_values())
        self.assertTrue(pref.period_line_ids)
        names = pref.period_line_ids.sorted("sequence").mapped("field_name")
        self.assertIn("create_date", names)
        self.assertIn("write_date", names)

        open_line = pref.period_line_ids.filtered(
            lambda l: l.field_name == "create_date"
        )[:1]
        open_line.write({"period_year_ids": [(6, 0, year.ids)]})
        domain = pref._period_domain()
        self.assertTrue(
            any(
                isinstance(leaf, tuple) and leaf[0] == "create_date"
                for leaf in domain
            ),
            domain,
        )

        # Switching Chart Model rebuilds rows but keeps years for same field.
        # Second option is seeded from blueprint period_field_id (create_date only).
        other = bp.studio_create_graph_variant(
            {
                "graph_model": "res.partner",
                "primary_button_label": "Second",
                "primary_action_xmlid": "base.action_partner_form",
            }
        )["created_graph_variant_id"]
        other_variant = self.env["dashboard.blueprint.graph.variant"].browse(other)
        self.assertEqual(
            other_variant.date_filter_ids.mapped("field_name"), ["create_date"]
        )
        pref.preferred_graph_variant_id = other
        pref.invalidate_recordset()
        names2 = pref.period_line_ids.sorted("sequence").mapped("field_name")
        self.assertEqual(names2, ["create_date"])
        kept = pref.period_line_ids.filtered(lambda l: l.field_name == "create_date")
        self.assertEqual(kept.period_year_ids, year)

    def test_graph_variant_defaults_override_blueprint(self):
        """Variant Group By / Measure / Include win over blueprint until pref."""
        bp = self._studio_blueprint()
        bp.write(
            {
                "primary_action_xmlid": "base.action_partner_form",
                "graph_data_field": "parent_id",
                "graph_measure": "__count",
            }
        )
        Field = self.env["ir.model.fields"]
        country = Field.search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")], limit=1
        )
        credit = Field.search(
            [
                ("model", "=", "res.partner"),
                ("name", "=", "credit"),
                ("store", "=", True),
            ],
            limit=1,
        )
        if not country:
            self.skipTest("country_id missing on res.partner")
        payload = bp.studio_create_graph_variant({})
        vid = payload["created_graph_variant_id"]
        variant = self.env["dashboard.blueprint.graph.variant"].browse(vid)
        scope = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": bp.id,
                "name": "Companies",
                "mode": "include",
                "domain": "[('is_company', '=', True)]",
                "default_on": False,
            }
        )
        write_vals = {
            "default_groupby_field_ids": country.ids,
            "default_scope_ids": scope.ids,
        }
        if credit:
            write_vals["default_measure_field_id"] = credit.id
            write_vals["default_measure_aggregator"] = "sum"
        bp.studio_write_graph_variant(vid, write_vals)
        variant.invalidate_recordset()
        self.assertEqual(variant.default_groupby_ids, country)
        self.assertEqual(variant.default_scope_ids, scope)

        settings = bp._effective_graph_settings()
        self.assertEqual(settings["groupby"], "country_id")
        self.assertIn("country_id", settings["groupbys"])
        if credit:
            self.assertEqual(settings["measure"], "credit:sum")

        # Fresh pref seeds from the option (options-only source of truth).
        pref_vals = bp._default_pref_values()
        self.assertIn(country.id, pref_vals["groupby_ids"][0][2])
        self.assertIn(scope.id, pref_vals["scope_ids"][0][2])
        if credit:
            self.assertEqual(pref_vals["measure_field_id"], credit.id)

        # Empty option Group By / Measure → id / Count (not blueprint leftovers).
        bp.studio_write_graph_variant(
            vid,
            {
                "default_groupby_field_ids": [],
                "default_measure_field_id": False,
                "default_scope_ids": [],
            },
        )
        settings2 = bp._effective_graph_settings()
        self.assertEqual(settings2["groupby"], "id")
        self.assertEqual(settings2["measure"], "__count")
        variant.invalidate_recordset()
        self.assertFalse(bp._default_include_scopes(variant).ids)

    def test_select_chart_model_sets_groupby_measure_include(self):
        """Gear Chart Model pick reseeds Group By / Measure / Data to Include."""
        bp = self._studio_blueprint()
        bp.write({"primary_action_xmlid": "base.action_partner_form"})
        scope_a = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": bp.id,
                "name": "Companies",
                "mode": "include",
                "domain": "[('is_company', '=', True)]",
                "default_on": True,
            }
        )
        scope_b = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": bp.id,
                "name": "People",
                "mode": "include",
                "domain": "[('is_company', '=', False)]",
                "default_on": False,
            }
        )
        parent = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "parent_id")], limit=1
        )
        child = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "color")], limit=1
        )
        first = bp.studio_create_graph_variant({})["created_graph_variant_id"]
        bp.studio_write_graph_variant(
            first,
            {
                "default_groupby_field_ids": [parent.id] if parent else [],
                "default_scope_ids": scope_a.ids,
            },
        )
        second_id = bp.studio_create_graph_variant(
            {
                "graph_model": "res.partner",
                "primary_button_label": "Second",
                "primary_action_xmlid": "base.action_partner_form",
                "graph_data_field": "parent_id",
            }
        )["created_graph_variant_id"]
        bp.studio_write_graph_variant(
            second_id,
            {
                "default_groupby_field_ids": [child.id] if child else [],
                "default_measure_field_id": False,
                "default_scope_ids": scope_b.ids,
            },
        )
        pref = self.env["dashboard.user.pref"].create(bp._default_pref_values())
        self.assertIn(scope_a.id, pref.scope_ids.ids)
        second = self.env["dashboard.blueprint.graph.variant"].browse(second_id)
        form_pref = pref.new(
            {
                "blueprint_id": bp.id,
                "user_id": pref.user_id.id,
                "company_id": pref.company_id.id,
                "preferred_graph_variant_id": pref.preferred_graph_variant_id.id,
                "preferred_graph_model": pref.preferred_graph_model,
                "scope_ids": [(6, 0, pref.scope_ids.ids)],
                "groupby_ids": [(6, 0, pref.groupby_ids.ids)],
                "measure_field_id": pref.measure_field_id.id or False,
            }
        )
        form_pref.preferred_graph_variant_id = second
        form_pref._onchange_preferred_graph_variant_id()
        if child:
            self.assertIn(child.id, form_pref.groupby_ids.ids)
        self.assertIn(scope_b.id, form_pref.scope_ids.ids)
        self.assertNotIn(scope_a.id, form_pref.scope_ids.ids)

    def test_chart_model_name_search_falls_back_when_label_is_invalid(self):
        """Gear dropdown must not stay empty when the typed label is unusable."""
        bp = self._studio_blueprint()
        # Keep blueprint link empty so the broken option stays invalid.
        bp.write({"primary_action_xmlid": "base.action_partner_form", "graph_data_field": False})
        broken = self.env["dashboard.blueprint.graph.variant"].create(
            {
                "blueprint_id": bp.id,
                "sequence": 5,
                "graph_model": "res.partner",
                "graph_data_field": False,
                "primary_button_label": "Sales Analysis",
                "primary_action_xmlid": "base.action_partner_form",
                "is_default": True,
            }
        )
        good = self.env["dashboard.blueprint.graph.variant"].create(
            {
                "blueprint_id": bp.id,
                "sequence": 10,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "primary_button_label": "Partners",
                "primary_action_xmlid": "base.action_partner_form",
            }
        )
        self.assertFalse(broken._is_valid_candidate())
        self.assertTrue(good._is_valid_candidate())
        Variant = self.env["dashboard.blueprint.graph.variant"]
        domain = [("blueprint_id", "=", bp.id)]
        rows = Variant.name_search("Sales Analysis", domain=domain, limit=20)
        self.assertEqual(rows, [(good.id, "Partners")])

    def test_onchange_chart_model_reseeds_scope_ids_on_cache(self):
        """Dialog onchange must update Include ticks + active graph_model."""
        bp = self._studio_blueprint()
        bp.write({"primary_action_xmlid": "base.action_partner_form"})
        scope_a = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": bp.id,
                "name": "Companies",
                "mode": "include",
                "domain": "[('is_company', '=', True)]",
            }
        )
        scope_b = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": bp.id,
                "name": "People",
                "mode": "include",
                "domain": "[('is_company', '=', False)]",
            }
        )
        first = bp.studio_create_graph_variant({})["created_graph_variant_id"]
        bp.studio_write_graph_variant(first, {"default_scope_ids": scope_a.ids})
        second_id = bp.studio_create_graph_variant(
            {
                "graph_model": "res.partner",
                "primary_button_label": "Second",
                "primary_action_xmlid": "base.action_partner_form",
            }
        )["created_graph_variant_id"]
        bp.studio_write_graph_variant(second_id, {"default_scope_ids": scope_b.ids})
        pref = self.env["dashboard.user.pref"].create(bp._default_pref_values())
        self.assertIn(scope_a, pref.scope_ids)
        second = self.env["dashboard.blueprint.graph.variant"].browse(second_id)
        # Form-dialog path: NewId cache + onchange (not write()).
        form_pref = pref.new(
            {
                "blueprint_id": bp.id,
                "user_id": pref.user_id.id,
                "company_id": pref.company_id.id,
                "preferred_graph_variant_id": pref.preferred_graph_variant_id.id,
                "preferred_graph_model": pref.preferred_graph_model,
                "scope_ids": [(6, 0, pref.scope_ids.ids)],
                "groupby_ids": [(6, 0, pref.groupby_ids.ids)],
            }
        )
        form_pref.preferred_graph_variant_id = second
        form_pref._onchange_preferred_graph_variant_id()
        form_pref.modified(["preferred_graph_variant_id"])
        self.assertIn(scope_b.id, form_pref.scope_ids.ids)
        self.assertNotIn(scope_a.id, form_pref.scope_ids.ids)
        self.assertEqual(form_pref.graph_model, "res.partner")

    def test_switch_chart_model_reseeds_pref_for_gear_and_chart(self):
        """Gear + chart follow each option's Group By / Measure / Include."""
        bp = self._studio_blueprint()
        bp.write(
            {
                "primary_action_xmlid": "base.action_partner_form",
                "graph_data_field": "parent_id",
            }
        )
        Field = self.env["ir.model.fields"]
        country = Field.search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")], limit=1
        )
        state = Field.search(
            [("model", "=", "res.partner"), ("name", "=", "state_id")], limit=1
        )
        if not country or not state:
            self.skipTest("country_id/state_id missing on res.partner")
        scope_a = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": bp.id,
                "name": "Companies",
                "mode": "include",
                "domain": "[('is_company', '=', True)]",
                "default_on": False,
            }
        )
        scope_b = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": bp.id,
                "name": "People",
                "mode": "include",
                "domain": "[('is_company', '=', False)]",
                "default_on": False,
            }
        )
        first = bp.studio_create_graph_variant({})["created_graph_variant_id"]
        bp.studio_write_graph_variant(
            first,
            {
                "default_groupby_field_ids": country.ids,
                "default_scope_ids": scope_a.ids,
                "primary_button_label": "First",
            },
        )
        second = bp.studio_create_graph_variant(
            {
                "graph_model": "res.partner",
                "primary_button_label": "Second",
                "primary_action_xmlid": "base.action_partner_form",
            }
        )["created_graph_variant_id"]
        bp.studio_write_graph_variant(
            second,
            {
                "default_groupby_field_ids": state.ids,
                "default_scope_ids": scope_b.ids,
            },
        )

        pref = self.env["dashboard.user.pref"].create(bp._default_pref_values())
        self.assertEqual(pref.preferred_graph_variant_id.id, first)
        self.assertEqual(pref.groupby_ids, country)
        self.assertEqual(pref.scope_ids & scope_a, scope_a)
        self.assertEqual(pref.graph_model, "res.partner")
        self.assertIn(scope_a, pref.applicable_include_scope_ids)

        settings = bp._effective_graph_settings()
        self.assertEqual(settings["groupby"], "country_id")

        pref.preferred_graph_variant_id = second
        pref.invalidate_recordset()
        self.assertEqual(pref.groupby_ids, state)
        self.assertEqual(pref.scope_ids & scope_b, scope_b)
        self.assertFalse(pref.scope_ids & scope_a)
        settings2 = bp._effective_graph_settings()
        self.assertEqual(settings2["groupby"], "state_id")
        # Pref domain must use the active option's include ticks.
        domain = pref._pref_domain()
        self.assertTrue(domain)

    def test_studio_payload_groupby_and_measure_ids(self):
        bp = self._make_bp_with_graph()
        Field = self.env["ir.model.fields"]
        f1 = Field.search(
            [
                ("model", "=", bp.graph_model),
                ("name", "in", ["country_id", "user_id", "create_date"]),
            ],
            limit=1,
        )
        if not f1:
            self.skipTest("No suitable group-by field on res.partner")
        bp.write(
            {
                "graph_groupby_ids": [(6, 0, f1.ids)],
                "ordered_graph_groupby_ids": str(f1.id),
                "graph_measure_field_id": False,
                "graph_measure": "__count",
            }
        )
        payload = bp.get_studio_payload()
        self.assertIn("graph_groupby_field_ids", payload)
        self.assertEqual(payload["graph_groupby_field_ids"], f1.ids)
        self.assertIn("graph_measure_field_id", payload)
        self.assertFalse(payload["graph_measure_field_id"])

    def test_studio_write_groupby_ids_and_measure_field(self):
        bp = self._make_bp_with_graph()
        Field = self.env["ir.model.fields"]
        measure = Field.search(
            [
                ("model", "=", bp.graph_model),
                ("ttype", "in", ["integer", "float", "monetary"]),
                ("store", "=", True),
            ],
            limit=1,
        )
        group = Field.search(
            [
                ("model", "=", bp.graph_model),
                ("name", "in", ["country_id", "user_id", "create_date"]),
            ],
            limit=1,
        )
        if not measure or not group:
            self.skipTest("Need stored numeric + group-by fields on res.partner")
        bp.studio_write_blueprint(
            {
                "graph_groupby_field_ids": group.ids,
                "graph_measure_field_id": measure.id,
                "graph_measure_aggregator": "sum",
            }
        )
        self.assertIn(group.id, bp.graph_groupby_ids.ids)
        self.assertEqual(bp.graph_measure_field_id.id, measure.id)
        self.assertEqual(bp.graph_measure_aggregator, "sum")

    def test_studio_header_payload_has_alignment(self):
        bp = self._studio_blueprint()
        item = bp.header_line_ids[:1]
        if not item:
            item = self.env["dashboard.blueprint.header.item"].create(
                {
                    "blueprint_id": bp.id,
                    "kind": "inline",
                    "alignment": "center",
                    "field_names": "email",
                }
            )
        else:
            item.write({"kind": "inline", "alignment": "center"})
        row = next(h for h in bp.get_studio_payload()["headers"] if h["id"] == item.id)
        self.assertEqual(row["alignment"], "center")
        bp.studio_write_header_item(
            item.id, {"alignment": "right", "kind": "subtitle"}
        )
        self.assertEqual(item.alignment, "right")
        self.assertEqual(item.kind, "subtitle")

    def test_studio_search_groups_returns_xmlid(self):
        hits = self.env["dashboard.blueprint"].studio_search_groups(
            term="Admin", limit=10
        )
        self.assertTrue(hits)
        self.assertTrue(all(h.get("xmlid") for h in hits))

    def test_studio_condition_catalog_filters_by_model(self):
        bp = self._studio_blueprint()
        Cond = self.env["dashboard.condition"]
        partner_cond = Cond.create(
            {
                "name": "Studio Partner Cond",
                "model": "res.partner",
                "domain": "[('is_company', '=', True)]",
            }
        )
        user_cond = Cond.create(
            {
                "name": "Studio User Cond",
                "model": "res.users",
                "domain": "[]",
            }
        )
        self.assertEqual(bp.studio_condition_catalog(), [])
        partner_rows = bp.studio_condition_catalog(model="res.partner")
        ids = {r["id"] for r in partner_rows}
        self.assertIn(partner_cond.id, ids)
        self.assertNotIn(user_cond.id, ids)
        self.assertTrue(all(r.get("model") == "res.partner" for r in partner_rows))

    def test_studio_write_slot_condition_ids_link_and_unlink(self):
        bp = self._studio_blueprint()
        slot = bp.slot_ids.filtered(lambda s: s.key == "child_count")
        cond = self.env["dashboard.condition"].create(
            {
                "name": "Studio Link Cond",
                "model": "res.partner",
                "domain": "[('active', '=', True)]",
            }
        )
        bp.studio_write_slot(slot.id, {"condition_ids": [cond.id]})
        self.assertIn(cond, slot.condition_ids)
        bp.studio_write_slot(slot.id, {"condition_ids": []})
        self.assertFalse(slot.condition_ids)

    def test_studio_group_labels_resolve_xmlids(self):
        labels = self.env["dashboard.blueprint"].studio_group_labels(
            xmlids=["base.group_system", "base.group_user", "no.such.group"]
        )
        self.assertIn("base.group_system", labels)
        self.assertNotEqual(labels["base.group_system"], "base.group_system")
        self.assertEqual(labels.get("no.such.group"), "no.such.group")

    def test_studio_write_action_context_tokens(self):
        import json

        bp = self._studio_blueprint()
        token_ctx = {
            "default_type": {
                "__de__": "group_value",
                "default": "opportunity",
                "map": [
                    {"groups": ["base.group_system"], "value": "company"},
                    {"groups": ["base.group_user"], "value": "user"},
                ],
            }
        }
        raw = json.dumps(token_ctx)
        bp.studio_write_blueprint({"primary_action_context": raw})
        self.assertIn("group_value", bp.primary_action_context)
        payload = bp.get_studio_payload()
        self.assertIn("group_value", payload.get("primary_action_context") or "")
        slot = bp.slot_ids[:1]
        bp.studio_write_slot(slot.id, {"action_context": raw})
        self.assertIn("group_value", slot.action_context)
        partner = self.env["res.partner"].create({"name": "Ctx Studio"})
        resolved = bp._eval_context_with_record(slot.action_context, partner)
        # First matching group wins (Settings / Admin → company)
        self.assertEqual(resolved.get("default_type"), "company")
        parsed = json.loads(slot.action_context)
        self.assertEqual(len(parsed["default_type"]["map"]), 2)