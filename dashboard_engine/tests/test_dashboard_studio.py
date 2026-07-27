# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Dashboard Studio — payload, CRUD, catalogs."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDashboardStudio(TransactionCase):
    def _host_model(self):
        return self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

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
        self.assertTrue(isinstance(actions, list))

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
