# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Smoke tests for dashboard.blueprint generator (no business-app depends)."""
import json

from odoo import fields, sql_db
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDashboardBlueprintEngine(TransactionCase):
    def _host_model(self):
        return self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def _child_count_slot(self):
        return {
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
        }

    def test_suggest_key_from_name_on_create(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "My Fancy Dashboard!!",
                "host_model_id": self._host_model().id,
                "state": "draft",
            }
        )
        self.assertEqual(bp.key, "my_fancy_dashboard")

    def test_publish_partner_blueprint_generates_artifacts(self):
        parent = self.env.ref("dashboard_engine.menu_dashboard_engine_root")
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Test Partners",
                "key": "test_partners_engine",
                "host_model_id": self._host_model().id,
                "menu_name": "Test Partners Dashboard",
                "menu_parent_id": parent.id,
                "primary_button_label": "Open",
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_measure": "__count",
                "graph_groupby": "id",
                "state": "draft",
            }
        )
        bp.action_publish()
        self.assertTrue(bp.generated_view_id)
        self.assertEqual(bp.generated_view_id.model, "res.partner")
        self.assertTrue(bp.generated_action_id)
        self.assertTrue(bp.generated_menu_id)
        self.assertTrue(bp.generated_menu_id.active)

    def test_gc_orphan_generated_menu(self):
        parent = self.env.ref("base.menu_administration")
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Orphan Menu Pack",
                "key": "test_gc_orphan_menu_%s" % self.env.uid,
                "host_model_id": self._host_model().id,
                "menu_name": "Orphan Customers Dashboard",
                "menu_parent_id": parent.id,
                "state": "published",
            }
        )
        bp.action_publish()
        menu = bp.generated_menu_id
        action = bp.generated_action_id
        view = bp.generated_view_id
        self.assertTrue(menu)
        menu_id, action_id, view_id = menu.id, action.id, view.id
        self.env.cr.execute(
            "UPDATE dashboard_blueprint SET generated_menu_id = NULL, "
            "generated_action_id = NULL, generated_view_id = NULL WHERE id = %s",
            (bp.id,),
        )
        bp.invalidate_recordset(
            ["generated_menu_id", "generated_action_id", "generated_view_id"]
        )
        bp.unlink()
        self.env["dashboard.blueprint"]._gc_orphan_generated_artifacts()
        self.assertFalse(self.env["ir.ui.menu"].browse(menu_id).exists())
        self.assertFalse(self.env["ir.actions.act_window"].browse(action_id).exists())
        self.assertFalse(self.env["ir.ui.view"].browse(view_id).exists())

    def test_purge_generated_menu_while_blueprint_exists(self):
        """Pack uninstall_hook runs before the blueprint XML is deleted."""
        from odoo.addons.dashboard_engine.hooks import (
            purge_generated_dashboard_artifacts,
        )

        parent = self.env.ref("base.menu_administration")
        key = "test_purge_live_%s" % self.env.uid
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Live Pack Menu",
                "key": key,
                "host_model_id": self._host_model().id,
                "menu_name": "Live Customers Dashboard",
                "menu_parent_id": parent.id,
                "state": "published",
            }
        )
        bp.action_publish()
        menu_id = bp.generated_menu_id.id
        action_id = bp.generated_action_id.id
        view_id = bp.generated_view_id.id
        purge_generated_dashboard_artifacts(self.env, keys=(key,))
        self.assertFalse(self.env["ir.ui.menu"].browse(menu_id).exists())
        self.assertFalse(self.env["ir.actions.act_window"].browse(action_id).exists())
        self.assertFalse(self.env["ir.ui.view"].browse(view_id).exists())

    def test_soft_module_depends_hides_inactive_blueprint(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Needs Fake App",
                "key": "test_soft_dep_engine",
                "host_model_id": self._host_model().id,
                "module_depends": "module_that_does_not_exist_xyz",
                "state": "published",
            }
        )
        self.assertFalse(bp._is_runtime_active())

    def test_primary_action_xmlid_prefers_existing_action(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Primary Xmlid",
                "key": "test_primary_xmlid",
                "host_model_id": self._host_model().id,
                "primary_button_label": "Open Partners",
                "primary_action_xmlid": "base.action_partner_form",
                "graph_data_field": "parent_id",
                "state": "published",
            }
        )
        partner = self.env["res.partner"].create({"name": "Primary Host"})
        action = self.env["dashboard.blueprint"].execute_primary_action(
            bp.key, "res.partner", partner.id
        )
        self.assertTrue(action)
        self.assertEqual(action.get("type"), "ir.actions.act_window")
        self.assertEqual(action.get("name"), "Open Partners")
        self.assertIn(("parent_id", "=", partner.id), action.get("domain") or [])

    def test_slot_payload_exposes_kpi(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Slot Partners",
                "key": "test_slot_partners",
                "host_model_id": self._host_model().id,
                "state": "published",
                "slot_ids": [(0, 0, self._child_count_slot())],
            }
        )
        partner = self.env["res.partner"].create({"name": "Engine Parent"})
        payload = self.env["dashboard.blueprint"].get_record_slots(
            bp.key, "res.partner", partner.id
        )
        self.assertTrue(payload["kpis"])
        kpi = payload["kpis"][0]
        self.assertEqual(kpi["key"], "child_count")
        # The click routes back through the generic object method.
        self.assertEqual(kpi["method"], "action_dashboard_engine_slot")
        self.assertEqual(kpi["context"]["dashboard_slot_key"], "child_count")
        self.assertEqual(kpi["context"]["dashboard_blueprint_key"], bp.key)

    def test_slot_field_matches_rpc_payload(self):
        """The field read and the RPC helper must agree, card for card."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Slot Parity",
                "key": "test_slot_parity",
                "host_model_id": self._host_model().id,
                "state": "published",
                "slot_ids": [(0, 0, self._child_count_slot())],
            }
        )
        parent = self.env["res.partner"].create({"name": "Parity Parent"})
        self.env["res.partner"].create(
            [{"name": "Parity Child %s" % i, "parent_id": parent.id} for i in range(3)]
        )
        via_field = parent.with_context(
            dashboard_blueprint_key=bp.key
        ).dashboard_slots
        via_rpc = self.env["dashboard.blueprint"].get_record_slots(
            bp.key, "res.partner", parent.id
        )
        self.assertEqual(via_field, via_rpc)
        self.assertEqual(via_field["kpis"][0]["count"], 3)
        self.assertEqual(via_field["kpis"][0]["label"], "Children")

    def test_slot_payload_query_count_does_not_grow_with_cards(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Slot Scaling",
                "key": "test_slot_scaling",
                "host_model_id": self._host_model().id,
                "state": "published",
                "slot_ids": [(0, 0, self._child_count_slot())],
            }
        )
        Partner = self.env["res.partner"]
        parents = Partner.create(
            [{"name": "Scaling Parent %s" % i} for i in range(25)]
        )
        Partner.create(
            [
                {"name": "Scaling Child %s" % parent.id, "parent_id": parent.id}
                for parent in parents
            ]
        )

        def count_queries(records):
            records = records.with_context(dashboard_blueprint_key=bp.key)
            records.invalidate_recordset()
            before = sql_db.sql_counter
            records.mapped("dashboard_slots")
            return sql_db.sql_counter - before

        few = count_queries(parents[:5])
        many = count_queries(parents)
        self.assertLessEqual(
            many,
            few,
            "Slot payload must cost the same whether the dashboard shows "
            "5 cards or 25; got %s queries for 5 and %s for 25." % (few, many),
        )

    def test_graph_drilldown_domain_is_searchable(self):
        """Clicking a bar must produce a domain the ORM accepts.

        A date group-by is emitted as ``create_date:month``, which is a
        read-group spec and not a field, so it must become a date range.
        """
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Drilldown",
                "key": "test_drilldown",
                "host_model_id": self._host_model().id,
                "state": "published",
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_measure": "__count",
                "graph_groupby": "create_date:month",
            }
        )
        parent = self.env["res.partner"].create({"name": "Drilldown Parent"})
        self.env["res.partner"].create(
            {"name": "Drilldown Child", "parent_id": parent.id}
        )
        payload = parent.with_context(
            dashboard_blueprint_key=bp.key
        ).dashboard_graph_data
        self.assertTrue(payload)

        point = json.loads(payload)[0]["values"][0]
        domain = point["domains"][0]
        self.assertNotIn(
            "create_date:month",
            str(domain),
            "The granularity spec must not leak into a searchable domain.",
        )
        # The real assertion: the ORM can run it, and it finds the record.
        found = self.env["res.partner"].search(domain)
        self.assertIn(parent.child_ids[0], found)

    def test_pickers_resolve_from_technical_names(self):
        """A blueprint written in technical names must show up in the pickers."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Mirror In",
                "key": "test_mirror_in",
                "host_model_id": self._host_model().id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_groupby": "create_date:month",
                "graph_measure": "color:avg",
                "module_depends": "base,web",
            }
        )
        self.assertEqual(bp.graph_model_id.model, "res.partner")
        self.assertEqual(bp.graph_data_field_id.name, "parent_id")
        self.assertEqual(bp.graph_groupby_field_id.name, "create_date")
        self.assertEqual(bp.graph_groupby_granularity, "month")
        self.assertTrue(bp.graph_groupby_is_date)
        self.assertEqual(bp.graph_measure_field_id.name, "color")
        self.assertEqual(bp.graph_measure_aggregator, "avg")
        self.assertEqual(sorted(bp.module_ids.mapped("name")), ["base", "web"])

    def test_pickers_write_back_technical_names(self):
        """Choosing records must produce the strings the runtime reads."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Mirror Out",
                "key": "test_mirror_out",
                "host_model_id": self._host_model().id,
            }
        )
        partner_model = self.env["ir.model"].search(
            [("model", "=", "res.partner")], limit=1
        )
        bp.write(
            {
                "graph_model_id": partner_model.id,
                "graph_data_field_id": self.env["ir.model.fields"]
                .search(
                    [("model", "=", "res.partner"), ("name", "=", "parent_id")],
                    limit=1,
                )
                .id,
                "graph_groupby_field_id": self.env["ir.model.fields"]
                .search(
                    [("model", "=", "res.partner"), ("name", "=", "create_date")],
                    limit=1,
                )
                .id,
                "graph_groupby_granularity": "year",
            }
        )
        self.assertEqual(bp.graph_model, "res.partner")
        self.assertEqual(bp.graph_data_field, "parent_id")
        self.assertEqual(bp.graph_groupby, "create_date:year")
        # No measure picked means counting records.
        self.assertEqual(bp.graph_measure, "__count")

    def test_granularity_is_dropped_for_non_date_group_by(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Mirror Granularity",
                "key": "test_mirror_gran",
                "host_model_id": self._host_model().id,
                "graph_model": "res.partner",
            }
        )
        bp.write(
            {
                "graph_groupby_field_id": self.env["ir.model.fields"]
                .search(
                    [("model", "=", "res.partner"), ("name", "=", "country_id")],
                    limit=1,
                )
                .id,
                "graph_groupby_granularity": "month",
            }
        )
        self.assertEqual(bp.graph_groupby, "country_id")
        self.assertFalse(bp.graph_groupby_is_date)

    def test_seeded_blueprints_expose_pickers(self):
        """The shipped blueprints must not look empty in the new UI."""
        seeded = self.env["dashboard.blueprint"].search(
            [("graph_model", "!=", False)]
        )
        self.assertTrue(seeded, "expected seeded blueprints to test against")
        for bp in seeded:
            if bp.graph_model in self.env:
                self.assertTrue(
                    bp.graph_model_id,
                    "%s has graph_model %s but an empty picker"
                    % (bp.key, bp.graph_model),
                )

    def test_slot_pickers_resolve_from_technical_names(self):
        """Slots written in data files must show up filled in the editor."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Slot Mirror In",
                "key": "test_slot_mirror_in",
                "host_model_id": self._host_model().id,
                "slot_ids": [
                    (
                        0,
                        0,
                        dict(
                            self._child_count_slot(),
                            amount_aggregator="credit_limit:sum",
                            groups_xmlids="base.group_user",
                            module_depends="base",
                        ),
                    )
                ],
            }
        )
        slot = bp.slot_ids
        self.assertEqual(slot.compute_model_id.model, "res.partner")
        self.assertEqual(slot.relate_field_id.name, "parent_id")
        self.assertEqual(slot.action_model_id.model, "res.partner")
        self.assertEqual(slot.amount_measure_field_id.name, "credit_limit")
        self.assertEqual(slot.amount_aggregator_type, "sum")
        self.assertEqual(slot.group_ids, self.env.ref("base.group_user"))
        self.assertEqual(slot.module_ids.mapped("name"), ["base"])
        # Plain record counting stays empty rather than showing a fake field.
        self.assertFalse(slot.count_measure_field_id)
        self.assertEqual(slot.value_mode, "count_amount")

    def test_section_o2ms_are_independent_filters(self):
        """Kanban Card / Manage Menu each bind their own O2M, not slot_ids."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Section O2Ms",
                "key": "test_section_o2ms",
                "host_model_id": self._host_model().id,
                "slot_ids": [
                    (0, 0, self._child_count_slot()),
                    (
                        0,
                        0,
                        {
                            "key": "due",
                            "name": "Due",
                            "section": "button_box",
                            "amount_field": "credit_limit",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "key": "meetings",
                            "name": "Meetings",
                            "section": "bottom",
                            "count_field": "meeting_count"
                            if "meeting_count" in self.env["res.partner"]._fields
                            else "color",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "key": "view_partners",
                            "name": "Partners",
                            "section": "menu_views",
                            "action_xmlid": "base.action_partner_form",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "key": "new_partner",
                            "name": "Partner",
                            "section": "menu_new",
                            "action_xmlid": "base.action_partner_form",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "key": "report_x",
                            "name": "Report",
                            "section": "menu_reports",
                            "action_xmlid": "base.action_partner_form",
                        },
                    ),
                ],
            }
        )
        self.assertEqual(bp.kpi_slot_ids.mapped("section"), ["kpi"])
        self.assertEqual(bp.button_box_slot_ids.mapped("section"), ["button_box"])
        self.assertEqual(bp.bottom_slot_ids.mapped("section"), ["bottom"])
        self.assertEqual(bp.menu_views_slot_ids.mapped("section"), ["menu_views"])
        self.assertEqual(bp.menu_new_slot_ids.mapped("section"), ["menu_new"])
        self.assertEqual(bp.menu_reports_slot_ids.mapped("section"), ["menu_reports"])
        self.assertEqual(len(bp.slot_ids), 6)
        # Creating through a section O2M must stamp the default section.
        bp.write(
            {
                "kpi_slot_ids": [
                    (
                        0,
                        0,
                        {
                            "key": "extra_kpi",
                            "name": "Extra",
                            "section": "kpi",
                            "compute_model": "res.partner",
                        },
                    )
                ]
            }
        )
        self.assertIn("extra_kpi", bp.kpi_slot_ids.mapped("key"))
        self.assertEqual(len(bp.slot_ids), 7)

    def test_slot_value_mode_drives_kpi_payload(self):
        """Shows selection controls whether count / amount reach the card."""
        Slot = self.env["dashboard.blueprint.slot"]
        parent = self.env["res.partner"].create({"name": "VM Parent"})
        self.env["res.partner"].create(
            {"name": "VM Child", "parent_id": parent.id, "credit_limit": 40.0}
        )
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Slot Value Mode",
                "key": "test_slot_value_mode",
                "host_model_id": self._host_model().id,
                "state": "published",
                "slot_ids": [
                    (0, 0, self._child_count_slot()),
                    (
                        0,
                        0,
                        dict(
                            self._child_count_slot(),
                            key="with_amount",
                            name="With Amount",
                            amount_aggregator="credit_limit:sum",
                        ),
                    ),
                    (
                        0,
                        0,
                        dict(
                            self._child_count_slot(),
                            key="amount_only",
                            name="Amount Only",
                            value_mode="amount",
                            amount_aggregator="credit_limit:sum",
                        ),
                    ),
                ],
            }
        )
        by_key = {s.key: s for s in bp.slot_ids}
        self.assertEqual(by_key["child_count"].value_mode, "count")
        self.assertEqual(by_key["with_amount"].value_mode, "count_amount")
        self.assertEqual(by_key["amount_only"].value_mode, "amount")
        self.assertIn(
            "Count + Amount",
            dict(Slot._fields["value_mode"].selection).values(),
        )

        count_item = by_key["child_count"]._to_slot_item(parent)
        both_item = by_key["with_amount"]._to_slot_item(parent)
        amount_item = by_key["amount_only"]._to_slot_item(parent)
        self.assertIn("count", count_item)
        self.assertNotIn("amount", count_item)
        self.assertIn("count", both_item)
        self.assertIn("amount", both_item)
        self.assertNotIn("count", amount_item)
        self.assertIn("amount", amount_item)

        # Switching Shows to Count only clears the amount aggregate.
        by_key["with_amount"].value_mode = "count"
        self.assertFalse(by_key["with_amount"].amount_aggregator)

    def test_slot_pickers_write_back_technical_names(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Slot Mirror Out",
                "key": "test_slot_mirror_out",
                "host_model_id": self._host_model().id,
                "slot_ids": [(0, 0, {"key": "k", "name": "K", "section": "kpi"})],
            }
        )
        slot = bp.slot_ids
        credit_limit = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "credit_limit")], limit=1
        )
        slot.write(
            {
                "compute_model_id": self._host_model().id,
                "relate_field_id": self.env["ir.model.fields"]
                .search(
                    [("model", "=", "res.partner"), ("name", "=", "parent_id")],
                    limit=1,
                )
                .id,
                "amount_measure_field_id": credit_limit.id,
                "amount_aggregator_type": "avg",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.assertEqual(slot.compute_model, "res.partner")
        self.assertEqual(slot.relate_field, "parent_id")
        self.assertEqual(slot.amount_aggregator, "credit_limit:avg")
        self.assertEqual(slot.groups_xmlids, "base.group_user")
        # Clearing a picker must clear the string the runtime reads.
        slot.group_ids = [(5, 0, 0)]
        self.assertFalse(slot.groups_xmlids)

    def test_slot_counts_a_measure_when_asked(self):
        """A KPI can total a field instead of counting rows."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Slot Measure",
                "key": "test_slot_measure",
                "host_model_id": self._host_model().id,
                "state": "published",
                "slot_ids": [(0, 0, self._child_count_slot())],
            }
        )
        slot = bp.slot_ids
        slot.count_measure_field_id = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "credit_limit")], limit=1
        )
        slot.count_aggregator_type = "sum"
        self.assertEqual(slot.compute_aggregator, "credit_limit:sum")

        parent = self.env["res.partner"].create({"name": "Measure Parent"})
        self.env["res.partner"].create(
            [
                {
                    "name": "Measure Child %s" % i,
                    "parent_id": parent.id,
                    "credit_limit": 100,
                }
                for i in range(3)
            ]
        )
        payload = parent.with_context(dashboard_blueprint_key=bp.key).dashboard_slots
        self.assertEqual(payload["kpis"][0]["count"], 300)

    def test_health_check_reports_missing_references(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Broken Refs",
                "key": "test_broken_refs",
                "host_model_id": self._host_model().id,
                "slot_ids": [(0, 0, self._child_count_slot())],
            }
        )
        self.assertEqual(bp.health_issue_count, 0, bp.health_message)

        # Mirrors pointing at something absent: what an uninstall leaves behind.
        bp.slot_ids.write(
            {
                "action_xmlid": "no_such_module.no_such_action",
                "groups_xmlids": "no_such_module.no_such_group",
            }
        )
        bp.invalidate_recordset()
        self.assertEqual(bp.health_issue_count, 2, bp.health_message)
        self.assertIn("no_such_module.no_such_action", bp.health_message)
        self.assertIn("no_such_module.no_such_group", bp.health_message)

        notification = bp.action_health_check()
        self.assertEqual(notification["params"]["type"], "warning")

    def test_seeded_blueprints_are_healthy(self):
        """Shipped blueprints must not greet the admin with a warning."""
        seeded = self.env["dashboard.blueprint"].search([])
        checked = 0
        for bp in seeded:
            # Blueprints for apps this database does not have are expected
            # to be broken; only judge the ones that should be running.
            if not bp._is_runtime_active():
                continue
            checked += 1
            self.assertEqual(
                bp.health_issue_count,
                0,
                "%s reports: %s" % (bp.key, bp.health_message),
            )
            self.assertEqual(bp.action_health_check()["params"]["type"], "success")
        self.assertTrue(checked, "expected at least one active seeded blueprint")

    def _header_blueprint(self, items):
        return self.env["dashboard.blueprint"].create(
            {
                "name": "Header",
                "key": "test_header_%s" % len(items),
                "host_model_id": self._host_model().id,
                "header_image_field": "image_128",
                "header_line_ids": [(0, 0, vals) for vals in items],
            }
        )

    def test_header_joins_two_fields_and_survives_either_being_empty(self):
        """One configured line must cover job only, company only, and both."""
        bp = self._header_blueprint(
            [
                {
                    "kind": "subtitle",
                    "field_names": "function,parent_id",
                    "separator": " at ",
                }
            ]
        )
        arch = bp._kanban_arch()
        # Line hidden only when both fields are empty.
        self.assertIn(
            't-if="record.function.raw_value or record.parent_id.raw_value"', arch
        )
        # Separator appears only when there is something on both sides of it.
        self.assertIn(
            't-if="(record.function.raw_value) and record.parent_id.raw_value"> at <',
            arch,
        )
        self.assertIn('<field name="function"/>', arch)
        self.assertIn('<field name="parent_id"/>', arch)

    def test_header_kind_inline_alignment_migration_mapping(self):
        Item = self.env["dashboard.blueprint.header.item"]
        mapped = Item._map_legacy_header_kind("left")
        self.assertEqual(mapped, {"kind": "inline", "alignment": "left"})
        mapped = Item._map_legacy_header_kind("right")
        self.assertEqual(mapped, {"kind": "inline", "alignment": "right"})
        mapped = Item._map_legacy_header_kind("subtitle")
        self.assertEqual(mapped, {"kind": "subtitle", "alignment": "left"})

    def test_header_arch_inline_center_and_subtitle_align(self):
        bp = self._header_blueprint(
            [
                {"kind": "subtitle", "alignment": "center", "field_names": "email"},
                {
                    "kind": "inline",
                    "alignment": "center",
                    "icon": "fa-phone",
                    "field_names": "phone",
                },
                {"kind": "inline", "alignment": "right", "field_names": "category_id"},
                {
                    "kind": "inline",
                    "alignment": "left",
                    "icon": "fa-envelope",
                    "field_names": "email",
                },
            ]
        )
        arch = bp._header_arch()
        self.assertIn("dashboard_header_line_inner", arch)
        self.assertIn("dashboard_header_align_center", arch)
        self.assertIn("justify-content-center", arch)
        self.assertIn("dashboard_header_right", arch)
        self.assertIn("fa-envelope", arch)
        # Centered inline keeps its icon (alignment is justify only).
        self.assertIn("fa-phone", arch)
        self.assertRegex(
            arch,
            r'dashboard_header_align_center[^>]*>[\s\S]*?dashboard_header_line_inner',
        )

    def test_header_inline_right_text_stays_under_title(self):
        """Right on Email is text justify, not the tags-column error."""
        bp = self._header_blueprint(
            [
                {
                    "kind": "inline",
                    "alignment": "right",
                    "icon": "fa-envelope",
                    "field_names": "email",
                }
            ]
        )
        arch = bp._header_arch()
        self.assertIn("justify-content-end", arch)
        self.assertIn("fa-envelope", arch)
        self.assertNotIn("dashboard_header_right", arch)
        self.assertIn("dashboard_header_inline_stack", arch)

    def test_header_declares_the_fields_it_reads(self):
        """Undeclared fields are simply not loaded by the kanban."""
        bp = self._header_blueprint(
            [
                {
                    "kind": "inline",
                    "alignment": "left",
                    "icon": "fa-map-marker",
                    "field_names": "city,country_id",
                },
                {"kind": "inline", "alignment": "right", "field_names": "category_id"},
            ]
        )
        arch = bp._kanban_arch()
        for name in ("image_128", "display_name", "city", "country_id", "category_id"):
            self.assertIn('<field name="%s"/>' % name, arch)
        # Partners have a colour, so the ribbon should be wired up.
        self.assertIn('highlight_color="color"', arch)
        # ⋮ menu footer: color picker + Configuration (v1 card chrome).
        self.assertIn('widget="kanban_color_picker"', arch)
        self.assertIn(">Configuration</a>", arch)

    def test_header_icon_is_named_for_screen_readers(self):
        bp = self._header_blueprint(
            [
                {
                    "kind": "inline",
                    "alignment": "left",
                    "icon": "fa-envelope",
                    "field_names": "email",
                }
            ]
        )
        arch = bp._kanban_arch()
        self.assertIn('class="fa fa-envelope me-1" title="Email"', arch)
        self.assertIn('aria-label="Email"', arch)

    def test_header_tags_use_colour_only_when_the_target_has_one(self):
        with_colour = self._header_blueprint(
            [{"kind": "inline", "alignment": "right", "field_names": "category_id"}]
        )
        self.assertIn("'color_field': 'color'", with_colour._kanban_arch())

        # Asking for a colour the target does not have breaks the tag widget
        # at render time, so which fields exist decides the generated options.
        colourless = next(
            (
                name
                for name, field in sorted(self.env["res.partner"]._fields.items())
                if field.type in ("many2many", "one2many")
                and field.comodel_name in self.env
                and "color" not in self.env[field.comodel_name]._fields
            ),
            None,
        )
        if not colourless:
            self.skipTest("every partner relation carries a colour here")
        without_colour = self._header_blueprint(
            [
                {"kind": "inline", "alignment": "right", "field_names": colourless},
                {"kind": "subtitle", "field_names": "ref"},
            ]
        )
        arch = without_colour._kanban_arch()
        self.assertIn('<field name="%s" widget="many2many_tags"' % colourless, arch)
        self.assertNotIn("color_field", arch)

    def test_header_left_tags_render_under_the_title(self):
        """Left + tags must stay in the title column, not the far-right pin."""
        bp = self._header_blueprint(
            [{"kind": "inline", "alignment": "left", "field_names": "category_id"}]
        )
        arch = bp._kanban_arch()
        self.assertIn("dashboard_header_left_tags", arch)
        self.assertIn('widget="many2many_tags"', arch)
        self.assertNotIn("dashboard_header_right", arch)

    def test_header_kind_change_republishes_kanban(self):
        """Editing Left/Right on a published blueprint must refresh the card."""
        bp = self._header_blueprint(
            [{"kind": "inline", "alignment": "right", "field_names": "category_id"}]
        )
        bp.action_publish()
        self.assertIn("dashboard_header_right", bp.generated_view_id.arch_db)
        bp.header_line_ids.write({"kind": "inline", "alignment": "left"})
        arch = bp.generated_view_id.arch_db
        self.assertIn("dashboard_header_left_tags", arch)
        self.assertNotIn("dashboard_header_right", arch)

    def test_header_allows_text_field_on_right_alignment(self):
        """Right alignment on Email is allowed (justify); tags column is for M2M."""
        bp = self._header_blueprint(
            [{"kind": "inline", "alignment": "right", "field_names": "email"}]
        )
        self.assertEqual(bp.header_line_ids.alignment, "right")
        self.assertNotIn("dashboard_header_right", bp._header_arch())

    def test_generated_header_is_valid_arch(self):
        """The generated view has to survive Odoo's own validation."""
        bp = self._header_blueprint(
            [
                {
                    "kind": "subtitle",
                    "field_names": "function,parent_id",
                    "separator": " at ",
                },
                {
                    "kind": "inline",
                    "alignment": "left",
                    "icon": "fa-map-marker",
                    "field_names": "city,country_id",
                    "separator": ", ",
                },
                {"kind": "inline", "alignment": "right", "field_names": "category_id"},
            ]
        )
        bp.action_publish()
        view = bp.generated_view_id
        self.assertTrue(view)
        view._check_xml()

    def test_seeded_partner_header_matches_the_hand_written_card(self):
        bp = self.env["dashboard.blueprint"].search(
            [("key", "=", "crm_customers")], limit=1
        )
        if not bp:
            self.skipTest("CRM seed not present")
        self.assertEqual(bp.header_image_field, "image_128")
        effective = [
            line._effective_kind_alignment()
            for line in bp.header_line_ids.sorted("sequence")
        ]
        self.assertEqual(
            [e["kind"] for e in effective[:3]], ["subtitle", "inline", "inline"]
        )
        self.assertIn(effective[-1]["alignment"], ("left", "right"))
        tags_line = bp.header_line_ids.filtered(
            lambda h: "category_id" in (h.field_names or "")
        )
        self.assertTrue(tags_line, "CRM seed must include Contact Tags")
        arch = bp._kanban_arch()
        for marker in (
            "dashboard_kanban_image_container",
            "dashboard_kanban_title",
            "dashboard_contact_info",
            "dashboard_tag_container",
        ):
            self.assertIn(marker, arch, "%s is load-bearing in the v1 stylesheet" % marker)
        if tags_line._effective_kind_alignment()["alignment"] == "right":
            self.assertIn("dashboard_header_right", arch)
        else:
            self.assertIn("dashboard_header_left_tags", arch)
            self.assertNotIn("dashboard_header_right", arch)

    def _scoped_blueprint(self):
        return self.env["dashboard.blueprint"].create(
            {
                "name": "Scoped",
                "key": "test_scoped",
                "host_model_id": self._host_model().id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_groupby": "create_date:month",
                "state": "published",
                "scope_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Companies",
                            "mode": "include",
                            "domain": "[('is_company', '=', True)]",
                            "default_on": True,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Contacts",
                            "mode": "include",
                            "domain": "[('is_company', '=', False)]",
                            "default_on": False,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Only mine",
                            "mode": "restrict",
                            "domain": "[('user_id', '=', uid)]",
                            "default_on": False,
                        },
                    ),
                ],
            }
        )

    def test_default_scopes_apply_before_anyone_opens_the_popup(self):
        bp = self._scoped_blueprint()
        self.assertFalse(bp._current_pref())
        self.assertEqual(
            bp._effective_graph_settings()["domain"], [("is_company", "=", True)]
        )

    def test_scope_domain_for_wrong_model_is_skipped(self):
        """sale.order-style include must not poison a crm.lead / partner graph."""
        bp = self._scoped_blueprint()
        bp.write(
            {
                "scope_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Sales Orders",
                            "mode": "include",
                            "domain": "[('state', 'in', ('sale', 'done'))]",
                            "default_on": True,
                        },
                    ),
                ],
            }
        )
        # Companies (valid) stays; Sales Orders (invalid on res.partner) drops.
        domain = bp._effective_graph_settings()["domain"]
        self.assertEqual(domain, [("is_company", "=", True)])
        self.env["res.partner"].search(domain)

    def test_ticking_a_second_scope_widens_the_graph(self):
        bp = self._scoped_blueprint()
        pref = bp._get_or_create_pref()
        self.assertEqual(pref.scope_ids.mapped("name"), ["Companies"])
        pref.scope_ids = bp.scope_ids.filtered(lambda s: s.mode == "include")
        domain = bp._effective_graph_settings()["domain"]
        self.assertEqual(
            domain,
            ["|", ("is_company", "=", True), ("is_company", "=", False)],
        )
        # Whatever the combination, it still has to be a usable domain.
        self.env["res.partner"].search(domain)

    def test_restricting_scope_resolves_uid_to_the_reader(self):
        bp = self._scoped_blueprint()
        pref = bp._get_or_create_pref()
        pref.scope_ids |= bp.scope_ids.filtered(lambda s: s.mode == "restrict")
        domain = bp._effective_graph_settings()["domain"]
        self.assertIn(("user_id", "=", self.env.uid), domain)

    def test_preference_overrides_measure_and_group_by(self):
        bp = self._scoped_blueprint()
        pref = bp._get_or_create_pref()
        pref.write(
            {
                "measure_field_id": self.env["ir.model.fields"]
                .search(
                    [("model", "=", "res.partner"), ("name", "=", "credit_limit")],
                    limit=1,
                )
                .id,
                "measure_aggregator": "avg",
                "groupby_field_id": self.env["ir.model.fields"]
                .search(
                    [("model", "=", "res.partner"), ("name", "=", "country_id")],
                    limit=1,
                )
                .id,
            }
        )
        settings = bp._effective_graph_settings()
        self.assertEqual(settings["measure"], "credit_limit:avg")
        self.assertEqual(settings["groupby"], "country_id")

    def test_preference_group_by_on_a_date_keeps_a_granularity(self):
        """V1-style: pick virtual x_create_date_year (no separate Per field)."""
        bp = self._scoped_blueprint()
        Fields = self.env["ir.model.fields"]
        Fields.ensure_date_period_fields("res.partner")
        year_tag = Fields.period_field_for("res.partner", "create_date", "year")
        self.assertTrue(year_tag, "expected virtual create_date > Year tag")
        pref = bp._get_or_create_pref()
        pref.write(
            {
                "groupby_ids": [(6, 0, year_tag.ids)],
                "ordered_groupby_ids": str(year_tag.id),
            }
        )
        self.assertEqual(bp._effective_graph_settings()["groupby"], "create_date:year")

    def test_ordered_extra_groupby_widens_the_graph_levels(self):
        """H3: extra group-by levels ride after the primary one, in order."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Multi Groupby",
                "key": "test_multi_groupby",
                "host_model_id": self._host_model().id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_groupby": "is_company",
                "state": "published",
            }
        )
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")], limit=1
        )
        bp.graph_groupby_extra_ids = [(6, 0, country_field.ids)]
        self.assertEqual(
            bp._effective_graph_settings()["groupbys"],
            ["is_company", "country_id"],
        )

        india = self.env["res.country"].search([("code", "=", "IN")], limit=1)
        parent = self.env["res.partner"].create({"name": "Multi Groupby Parent"})
        self.env["res.partner"].create(
            {
                "name": "Multi Groupby Child",
                "parent_id": parent.id,
                "is_company": True,
                "country_id": india.id if india else False,
            }
        )
        payload = bp._build_graph_payloads(parent)
        chart = json.loads(payload[parent.id]["json"])[0]
        points = chart["values"]
        self.assertEqual(len(points), 1)
        point = points[0]
        # Primary group-by is the X label; secondary becomes a legend series.
        self.assertIn(point["label"], ("True", "true", "1"))
        self.assertTrue(point.get("group_color_keys"), point)
        if india:
            self.assertIn(india.display_name, point["group_color_keys"])
        else:
            self.assertTrue(any(point["group_color_keys"]))
        domain = point["domains"][0]
        # Round-tripped through JSON, so leaves come back as lists.
        self.assertIn(["is_company", "=", True], domain)
        if india:
            self.assertIn(["country_id", "=", india.id], domain)
        # Single-series measure legend must not expose the raw "__count" key.
        bp_single = self.env["dashboard.blueprint"].create(
            {
                "name": "Single Groupby Legend",
                "key": "test_single_groupby_legend",
                "host_model_id": self._host_model().id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_groupby": "is_company",
                "graph_measure": "__count",
                "state": "published",
            }
        )
        single_payload = bp_single._build_graph_payloads(parent)
        single_chart = json.loads(single_payload[parent.id]["json"])[0]
        self.assertNotEqual(single_chart["key"], "__count")

    def test_preference_extra_groupby_overrides_blueprint_default(self):
        """A user's own ordered extra levels win over the blueprint default."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Multi Groupby Pref",
                "key": "test_multi_groupby_pref",
                "host_model_id": self._host_model().id,
                "graph_model": "res.partner",
                "graph_groupby": "is_company",
                "state": "published",
            }
        )
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")], limit=1
        )
        lang_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "lang")], limit=1
        )
        bp.graph_groupby_extra_ids = [(6, 0, country_field.ids)]
        pref = bp._get_or_create_pref()
        # Untouched pref inherits the blueprint's default extra level.
        self.assertEqual(
            bp._effective_graph_settings()["groupbys"], ["is_company", "country_id"]
        )
        pref.groupby_extra_ids = [(6, 0, lang_field.ids)]
        self.assertEqual(
            bp._effective_graph_settings()["groupbys"], ["is_company", "lang"]
        )

    def test_dual_date_rows_are_pooled_under_one_match_operator(self):
        """H4: Creation Date and Closed Date rows combine like v1."""
        bp = self._scoped_blueprint()
        pref = bp._get_or_create_pref()
        Fields = self.env["ir.model.fields"]
        create_field = Fields.search(
            [("model", "=", "res.partner"), ("name", "=", "create_date")], limit=1
        )
        write_field = Fields.search(
            [("model", "=", "res.partner"), ("name", "=", "write_date")], limit=1
        )
        year = self.env["period.year"].search([], limit=1)
        if not year:
            self.skipTest("No period.year seed available")
        pref.write(
            {
                "period_field_id": create_field.id,
                "period_year_ids": [(6, 0, year.ids)],
                "period_closed_field_id": write_field.id,
                "period_closed_year_ids": [(6, 0, year.ids)],
                "period_operator": "any",
            }
        )
        domain = pref._period_domain()
        # Pooled "any" match: leaves from both date rows show up OR'd.
        self.assertTrue(
            any(leaf[0] == "create_date" for leaf in domain if isinstance(leaf, tuple))
        )
        self.assertTrue(
            any(leaf[0] == "write_date" for leaf in domain if isinstance(leaf, tuple))
        )

    def test_period_line_months_fill_current_year_and_clear_with_year(self):
        """v1: months imply current year; clearing years also clears months."""
        bp = self._scoped_blueprint()
        pref = bp._get_or_create_pref()
        create_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "create_date")], limit=1
        )
        mq = self.env["period.month.quarter"].search([], limit=1)
        current_year = self.env["period.year"].search([("name", "=", "year")], limit=1)
        if not create_field or not mq or not current_year:
            self.skipTest("Date field or period catalog missing")
        pref.write({"period_field_id": create_field.id})
        pref._sync_pref_period_lines()
        line = pref.period_line_ids[:1]
        if not line:
            self.skipTest("No period line on pref")
        line.write({"period_mq_ids": [(6, 0, mq.ids)], "period_year_ids": [(5, 0, 0)]})
        self.assertEqual(line.period_year_ids, current_year)
        # v1: month/year picks rewrite Custom Filter from those date ranges.
        pref.invalidate_recordset(["custom_filter"])
        custom = pref.custom_filter or "[]"
        self.assertIn("create_date", custom)
        line.write({"period_year_ids": [(5, 0, 0)]})
        self.assertFalse(line.period_year_ids)
        self.assertFalse(line.period_mq_ids)
        pref.invalidate_recordset(["custom_filter"])
        self.assertEqual(pref.custom_filter or "[]", "[]")

    def test_web_custom_filter_from_live_period_picks(self):
        """Gear month tags rewrite Custom Filter before Apply (v1 onchange)."""
        bp = self._scoped_blueprint()
        pref = bp._get_or_create_pref()
        create_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "create_date")], limit=1
        )
        mq = self.env["period.month.quarter"].search([], limit=1)
        if not create_field or not mq:
            self.skipTest("Date field or period catalog missing")
        pref.write({"period_field_id": create_field.id})
        pref._sync_pref_period_lines()
        line = pref.period_line_ids[:1]
        if not line:
            self.skipTest("No period line on pref")
        value = pref.web_custom_filter_from_period_picks(
            [
                {
                    "id": line.id,
                    "field_name": "create_date",
                    "period_mq_ids": mq.ids,
                    "period_year_ids": [],
                }
            ],
            "any",
        )
        domain = value.get("domain") if isinstance(value, dict) else value
        self.assertIn("create_date", domain)
        mqs = self.env["period.month.quarter"].search([], limit=2)
        if len(mqs) < 2:
            return
        many = pref.web_custom_filter_from_period_picks(
            [
                {
                    "id": line.id,
                    "field_name": "create_date",
                    "period_mq_ids": mqs.ids,
                    "period_year_ids": [],
                }
            ],
            "any",
        )
        many_domain = many.get("domain") if isinstance(many, dict) else many
        self.assertIn("create_date", many_domain)
        self.assertIn("|", many_domain)
        self.assertGreaterEqual(len(many.get("ranges") or []), 2)

    def test_preferences_are_private_to_their_owner(self):
        bp = self._scoped_blueprint()
        mine = bp._get_or_create_pref()
        other = self.env["res.users"].create(
            {
                "name": "Other Viewer",
                "login": "dashboard_other_viewer",
                "group_ids": [
                    (4, self.env.ref("dashboard_engine.group_dashboard_engine_user").id)
                ],
            }
        )
        visible = self.env["dashboard.user.pref"].with_user(other).search([])
        self.assertNotIn(mine.id, visible.ids)

    def test_gear_opens_the_settings_of_the_dashboard_being_viewed(self):
        bp = self._scoped_blueprint()
        Blueprint = self.env["dashboard.blueprint"]
        action = Blueprint.action_open_settings_for_key(bp.key)
        self.assertEqual(action["res_model"], "dashboard.user.pref")
        self.assertEqual(action["target"], "new")
        # Reopening must land on the same row rather than pile up new ones.
        again = Blueprint.action_open_settings_for_key(bp.key)
        self.assertEqual(action["res_id"], again["res_id"])
        self.assertEqual(len(bp.pref_ids), 1)

    def test_gear_falls_back_to_the_builder_without_a_blueprint(self):
        action = self.env["dashboard.blueprint"].action_open_settings_for_key(
            "no_such_dashboard"
        )
        self.assertEqual(action["res_model"], "dashboard.blueprint")

    def test_graph_honours_the_saved_scope(self):
        bp = self._scoped_blueprint()
        parent = self.env["res.partner"].create(
            {"name": "Scoped Parent", "is_company": True}
        )
        self.env["res.partner"].create(
            [
                {"name": "Scoped Co", "parent_id": parent.id, "is_company": True},
                {"name": "Scoped Person", "parent_id": parent.id, "is_company": False},
            ]
        )
        payload = bp._build_graph_payloads(parent)
        companies_only = sum(
            point["value"][0] for point in json.loads(payload[parent.id]["json"])[0]["values"]
        )
        self.assertEqual(companies_only, 1)

        pref = bp._get_or_create_pref()
        pref.scope_ids = bp.scope_ids.filtered(lambda s: s.mode == "include")
        parent.invalidate_recordset()
        payload = bp._build_graph_payloads(parent)
        both = sum(
            point["value"][0] for point in json.loads(payload[parent.id]["json"])[0]["values"]
        )
        self.assertEqual(both, 2)

    def _country_model(self):
        return self.env["ir.model"].search([("model", "=", "res.country")], limit=1)

    def _field(self, model, name):
        return self.env["ir.model.fields"].search(
            [("model", "=", model), ("name", "=", name)], limit=1
        )

    def _partner_to_country_via_parent_path(self):
        """Partners → parent company → country: a two-hop path using only base."""
        partner_model = self._host_model()
        country_model = self._country_model()
        path = self.env["dashboard.relation.path"].create(
            {
                "name": "Partner via parent country",
                "source_model_id": partner_model.id,
                "target_model_id": country_model.id,
            }
        )
        self.env["dashboard.relation.hop"].create(
            [
                {
                    "path_id": path.id,
                    "sequence": 10,
                    "field_id": self._field("res.partner", "parent_id").id,
                },
                {
                    "path_id": path.id,
                    "sequence": 20,
                    "field_id": self._field("res.partner", "country_id").id,
                },
            ]
        )
        path.invalidate_recordset()
        self.assertEqual(path.domain_field, "parent_id.country_id")
        self.assertEqual(path.first_hop_field, "parent_id")
        self.assertFalse(path.is_direct)
        return path

    def test_relation_path_compiles_dotted_domain_field(self):
        path = self._partner_to_country_via_parent_path()
        leaf = path.domain_leaf([1, 2])
        self.assertEqual(leaf, ("parent_id.country_id", "in", [1, 2]))
        self.assertEqual(
            path.domain_leaf([7]), ("parent_id.country_id", "=", 7)
        )

    def test_char_relation_path_validates_and_compiles(self):
        """Inline Char multi-hop is the canonical store after A+."""
        from odoo.addons.dashboard_engine.tools.relation_path import (
            domain_leaf,
            validate_path,
        )
        from odoo.exceptions import ValidationError

        validate_path(
            self.env, "res.partner", "parent_id.country_id", "res.country"
        )
        self.assertEqual(
            domain_leaf("parent_id.country_id", [1, 2]),
            ("parent_id.country_id", "in", [1, 2]),
        )
        with self.assertRaises(ValidationError):
            validate_path(
                self.env, "res.partner", "parent_id", "res.country"
            )
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Char path",
                "key": "test_char_path_ok",
                "host_model_id": self._country_model().id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id.country_id",
            }
        )
        info = bp._graph_link_path()
        self.assertTrue(info)
        self.assertEqual(info.domain_field, "parent_id.country_id")

    def test_soft_dep_slot_skips_unknown_source_model(self):
        """Slots whose compute model is not installed must still seed."""
        Slot = self.env["dashboard.blueprint.slot"]
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Soft stock slot",
                "key": "test_soft_stock_slot",
                "host_model_id": self._host_model().id,
            }
        )
        slot = Slot.create(
            {
                "blueprint_id": bp.id,
                "key": "bottom_deliveries",
                "name": "Deliveries",
                "section": "bottom",
                "compute_model": "stock.picking",
                "relate_field": "partner_id",
                "module_depends": "sale,stock",
            }
        )
        self.assertTrue(slot.id)
        if "stock.picking" not in self.env:
            self.assertEqual(slot.compute_model, "stock.picking")
        self.assertEqual(info.first_hop_field, "parent_id")
        self.assertFalse(info.is_direct)

    def test_relation_path_rejects_a_chain_that_misses_the_card(self):
        from odoo.exceptions import ValidationError

        path = self.env["dashboard.relation.path"].create(
            {
                "name": "Broken",
                "source_model_id": self._host_model().id,
                "target_model_id": self._country_model().id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["dashboard.relation.hop"].create(
                {
                    "path_id": path.id,
                    "sequence": 10,
                    "field_id": self._field("res.partner", "parent_id").id,
                }
            )

    def test_multi_hop_graph_folds_first_hop_onto_cards(self):
        """Category-style: group by the first hop, fold onto the host card."""
        france, germany = self.env["res.country"].create(
            [{"name": "Dash France", "code": "DF"}, {"name": "Dash Germany", "code": "DG"}]
        )
        acme = self.env["res.partner"].create(
            {"name": "Acme FR", "is_company": True, "country_id": france.id}
        )
        berlin = self.env["res.partner"].create(
            {"name": "Berlin Co", "is_company": True, "country_id": germany.id}
        )
        self.env["res.partner"].create(
            [
                {"name": "Child A", "parent_id": acme.id},
                {"name": "Child B", "parent_id": acme.id},
                {"name": "Child C", "parent_id": berlin.id},
            ]
        )
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Countries",
                "key": "test_country_multihop",
                "host_model_id": self._country_model().id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id.country_id",
                "graph_groupby": "id",
                "graph_measure": "__count",
                "state": "published",
            }
        )
        payloads = bp._build_graph_payloads(france | germany)
        france_total = sum(
            point["value"][0]
            for point in json.loads(payloads[france.id]["json"])[0]["values"]
        )
        germany_total = sum(
            point["value"][0]
            for point in json.loads(payloads[germany.id]["json"])[0]["values"]
        )
        self.assertEqual(france_total, 2)
        self.assertEqual(germany_total, 1)
        # Drill-down must use the dotted path, not the first hop alone.
        point_domain = json.loads(payloads[france.id]["json"])[0]["values"][0][
            "domains"
        ][0]
        # JSON round-trip turns domain tuples into lists.
        self.assertIn(["parent_id.country_id", "=", france.id], point_domain)

    def test_multi_hop_slot_folds_with_flat_query_cost(self):
        countries = self.env["res.country"].create(
            [{"name": "Dash C%s" % i, "code": "C%s" % i} for i in range(8)]
        )
        parents = self.env["res.partner"].create(
            [
                {
                    "name": "Parent %s" % country.id,
                    "is_company": True,
                    "country_id": country.id,
                }
                for country in countries
            ]
        )
        self.env["res.partner"].create(
            [
                {"name": "Kid %s" % parent.id, "parent_id": parent.id}
                for parent in parents
            ]
        )
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Country Slots",
                "key": "test_country_slot_multihop",
                "host_model_id": self._country_model().id,
                "state": "published",
                "slot_ids": [
                    (
                        0,
                        0,
                        {
                            "key": "kids",
                            "name": "Children",
                            "section": "kpi",
                            "label": "Child",
                            "label_plural": "Children",
                            "compute_model": "res.partner",
                            "relate_field": "parent_id.country_id",
                            "show_if_zero": True,
                        },
                    )
                ],
            }
        )

        def count_queries(recordset):
            recordset = recordset.with_context(dashboard_blueprint_key=bp.key)
            recordset.invalidate_recordset()
            before = sql_db.sql_counter
            payloads = recordset.mapped("dashboard_slots")
            return sql_db.sql_counter - before, payloads

        few_q, few_payloads = count_queries(countries[:2])
        many_q, many_payloads = count_queries(countries)
        self.assertLessEqual(
            many_q,
            few_q + 2,
            "Multi-hop slots must stay flat; got %s for 2 and %s for 8"
            % (few_q, many_q),
        )
        self.assertEqual(few_payloads[0]["kpis"][0]["count"], 1)
        self.assertEqual(many_payloads[0]["kpis"][0]["count"], 1)

    def test_direct_link_still_works_without_a_path(self):
        """Single-hop blueprints must not regress when paths exist."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Direct",
                "key": "test_direct_still",
                "host_model_id": self._host_model().id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_groupby": "id",
                "state": "published",
            }
        )
        parent = self.env["res.partner"].create({"name": "Direct Parent"})
        self.env["res.partner"].create(
            [{"name": "Direct Child", "parent_id": parent.id}]
        )
        payloads = bp._build_graph_payloads(parent)
        total = sum(
            point["value"][0]
            for point in json.loads(payloads[parent.id]["json"])[0]["values"]
        )
        self.assertEqual(total, 1)

    def test_condition_relative_date_compiles_to_today(self):
        condition = self.env["dashboard.condition"].create(
            {
                "name": "Created before today",
                "model": "res.partner",
                "match": "all",
                "rule_ids": [
                    (
                        0,
                        0,
                        {
                            "sequence": 10,
                            "field_name": "create_date",
                            "operator": "<",
                            "value_type": "relative_date",
                            "relative_when": "today",
                        },
                    )
                ],
            }
        )
        domain = condition.to_domain()
        self.assertEqual(len(domain), 1)
        self.assertEqual(domain[0][:2], ("create_date", "<"))
        today = fields.Date.context_today(self.env.user)
        # Datetime field + "today" resolves to the start of today as a datetime string.
        self.assertTrue(str(domain[0][2]).startswith(fields.Date.to_string(today)))
        # Rules editor syncs a portable domain tree with an unresolved token.
        self.assertTrue(condition.domain_tree)
        self.assertEqual(condition.domain_tree[0][0], "create_date")
        self.assertEqual(
            condition.domain_tree[0][2].get("__de__"), "relative_date"
        )

    def test_condition_domain_tree_supports_nested_or_and_tokens(self):
        """Complex trees compile without going through the rules O2M."""
        condition = self.env["dashboard.condition"].create(
            {
                "name": "Nested token tree",
                "model": "res.partner",
                "domain_tree": [
                    "&",
                    ["is_company", "=", True],
                    "|",
                    ["user_id", "=", {"__de__": "uid"}],
                    [
                        "create_date",
                        "<",
                        {"__de__": "relative_date", "when": "today"},
                    ],
                ],
            }
        )
        domain = condition.to_domain()
        self.assertIn("&", domain)
        self.assertIn("|", domain)
        self.assertIn(("is_company", "=", True), domain)
        self.assertIn(("user_id", "=", self.env.uid), domain)
        create_leaf = next(
            leaf for leaf in domain if isinstance(leaf, tuple) and leaf[0] == "create_date"
        )
        today = fields.Date.context_today(self.env.user)
        self.assertTrue(str(create_leaf[2]).startswith(fields.Date.to_string(today)))
        # Domain builder Char mirrors the tree with expressions / smart dates.
        self.assertIn("uid", condition.domain)
        self.assertIn('"today"', condition.domain)

    def test_condition_domain_builder_round_trips_expressions(self):
        """widget=domain Char with expressions becomes portable tokens."""
        condition = self.env["dashboard.condition"].create(
            {
                "name": "Domain builder",
                "model": "res.partner",
                "domain": (
                    "['&', ('is_company', '=', True), "
                    "'|', ('user_id', '=', uid), "
                    "('create_date', '<', context_today().strftime(\"%Y-%m-%d\"))]"
                ),
            }
        )
        tree = condition.domain_tree
        self.assertEqual(tree[0], "&")
        self.assertEqual(tree[1], ["is_company", "=", True])
        self.assertEqual(tree[2], "|")
        self.assertEqual(tree[3][2].get("__de__"), "uid")
        self.assertEqual(tree[4][2].get("__de__"), "relative_date")
        domain = condition.to_domain()
        self.assertIn(("user_id", "=", self.env.uid), domain)
        self.assertIn(("is_company", "=", True), domain)

    def test_condition_overdue_uses_odoo_standard_virtual_today(self):
        """Overdue open: date_closed = False; deadline before today (token)."""
        today = fields.Date.context_today(self.env.user)
        today_s = fields.Date.to_string(today)
        condition = self.env["dashboard.condition"].create(
            {
                "name": "Overdue open",
                "model": "res.partner",
                "domain_tree": [
                    "&",
                    ["date_closed", "=", False],
                    [
                        "date_deadline",
                        "<",
                        {"__de__": "relative_date", "when": "today"},
                    ],
                ],
            }
        )
        # Domain Char shows smart-date text for before/after presets.
        self.assertIn('"today"', condition.domain)
        self.assertNotIn("context_today()", condition.domain)
        # Saving that Char must keep the relative_date token.
        condition.write({"domain": condition.domain})
        self.assertEqual(condition.domain_tree[2][2].get("__de__"), "relative_date")
        domain = condition.to_domain()
        self.assertIn(("date_closed", "=", False), domain)
        deadline = next(
            leaf for leaf in domain if isinstance(leaf, tuple) and leaf[0] == "date_deadline"
        )
        self.assertEqual(deadline[1], "<")
        self.assertTrue(str(deadline[2]).startswith(today_s))

    def test_condition_domain_char_round_trips_smart_date_before(self):
        """before + today / today -7d from the domain builder become tokens."""
        condition = self.env["dashboard.condition"].create(
            {
                "name": "Smart date before",
                "model": "res.partner",
                "domain": "[('create_date', '<', 'today -7d')]",
            }
        )
        self.assertEqual(condition.domain_tree[0][2].get("__de__"), "relative_date")
        self.assertEqual(condition.domain_tree[0][2].get("when"), "days_ago")
        self.assertEqual(condition.domain_tree[0][2].get("days"), 7)
        # Recompute Char from tokens (create-via-domain keeps the typed Char).
        condition.domain_tree = condition.domain_tree
        self.assertIn('"today -7d"', condition.domain)

    def test_condition_group_value_domain_char_is_valid_expression(self):
        """group_value tokens must not serialize as raw dicts (Invalid domain)."""
        condition = self.env["dashboard.condition"].create(
            {
                "name": "Group value domain",
                "model": "res.partner",
                "domain_tree": [
                    [
                        "type",
                        "=",
                        {
                            "__de__": "group_value",
                            "default": "opportunity",
                            "map": [
                                {
                                    "groups": ["base.group_user"],
                                    "value": "lead",
                                }
                            ],
                        },
                    ]
                ],
            }
        )
        # Domain builder shows the default literal (valid for DomainSelector).
        self.assertEqual(condition.domain, '[("type", "=", "opportunity")]')
        # Saving that Char must keep the group_value token in domain_tree.
        condition.write({"domain": condition.domain})
        self.assertEqual(condition.domain_tree[0][2].get("__de__"), "group_value")
        self.assertEqual(condition.domain_tree[0][2].get("default"), "opportunity")
        self.assertEqual(
            condition.domain_tree[0][2]["map"][0]["value"], "lead"
        )

    def test_condition_record_token_skipped_without_card(self):
        condition = self.env["dashboard.condition"].create(
            {
                "name": "Scoped to card",
                "model": "res.partner",
                "domain_tree": [
                    ["parent_id", "=", {"__de__": "record"}],
                    ["is_company", "=", True],
                ],
            }
        )
        self.assertEqual(condition.to_domain(), [("is_company", "=", True)])
        partner = self.env["res.partner"].create({"name": "Tree Card"})
        self.assertEqual(
            condition.to_domain(partner),
            [("parent_id", "=", partner.id), ("is_company", "=", True)],
        )

    def test_slot_merges_reusable_condition_into_count_and_action(self):
        condition = self.env["dashboard.condition"].create(
            {
                "name": "Companies only",
                "model": "res.partner",
                "rule_ids": [
                    (
                        0,
                        0,
                        {
                            "field_name": "is_company",
                            "operator": "=",
                            "value_type": "true",
                        },
                    )
                ],
            }
        )
        parent = self.env["res.partner"].create({"name": "Cond Parent"})
        self.env["res.partner"].create(
            [
                {"name": "Co", "parent_id": parent.id, "is_company": True},
                {"name": "Person", "parent_id": parent.id, "is_company": False},
            ]
        )
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Cond Slot",
                "key": "test_condition_slot",
                "host_model_id": self._host_model().id,
                "state": "published",
                "slot_ids": [
                    (
                        0,
                        0,
                        {
                            "key": "companies",
                            "name": "Companies",
                            "section": "kpi",
                            "compute_model": "res.partner",
                            "relate_field": "parent_id",
                            "condition_ids": [(6, 0, condition.ids)],
                            "action_model": "res.partner",
                            "action_domain": "[('parent_id', '=', '{{id}}')]",
                            "show_if_zero": True,
                        },
                    )
                ],
            }
        )
        payload = parent.with_context(
            dashboard_blueprint_key=bp.key
        ).dashboard_slots
        self.assertEqual(payload["kpis"][0]["count"], 1)
        action = bp.slot_ids._prepare_action(parent)
        leaves = [
            tuple(leaf) if isinstance(leaf, list) else leaf
            for leaf in action["domain"]
            if isinstance(leaf, (list, tuple))
        ]
        self.assertIn(("is_company", "=", True), leaves)
        self.assertIn(("parent_id", "=", parent.id), leaves)

    def test_condition_group_value_picks_by_viewer_group(self):
        condition = self.env["dashboard.condition"].create(
            {
                "name": "Type by group",
                "model": "res.partner",
                "rule_ids": [
                    (
                        0,
                        0,
                        {
                            "field_name": "company_type",
                            "operator": "=",
                            "value_type": "static",
                            "value_char": "person",
                            "group_value_ids": [
                                (
                                    0,
                                    0,
                                    {
                                        "groups_xmlids": "base.group_system",
                                        "value_char": "company",
                                    },
                                )
                            ],
                        },
                    )
                ],
            }
        )
        rule = condition.rule_ids
        # Admin is in Settings → company.
        self.assertTrue(self.env.user.has_group("base.group_system"))
        self.assertEqual(rule._resolve_static_value(), "company")
        # A plain user keeps the default.
        plain = self.env["res.users"].create(
            {
                "name": "Plain Cond",
                "login": "plain_cond_viewer",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.assertEqual(
            rule.with_user(plain)._resolve_static_value(), "person"
        )

    def test_action_context_resolves_group_value_token(self):
        """Any blueprint can put __de__ tokens in action_context (generic)."""
        from odoo.addons.dashboard_engine.tools.condition_domain import (
            compile_context_value,
        )

        token_ctx = {
            "default_type": {
                "__de__": "group_value",
                "default": "person",
                "map": [
                    {
                        "groups": ["base.group_system"],
                        "value": "company",
                    }
                ],
            }
        }
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Context Tokens",
                "key": "test_context_tokens_%s" % self.env.uid,
                "host_model_id": self._host_model().id,
                "graph_model": "res.partner",
                "slot_ids": [
                    (
                        0,
                        0,
                        {
                            "key": "kids",
                            "name": "Kids",
                            "section": "kpi",
                            "compute_model": "res.partner",
                            "relate_field": "parent_id",
                            "compute_domain": "[]",
                            "action_model": "res.partner",
                            "action_context": json.dumps(token_ctx),
                        },
                    )
                ],
            }
        )
        slot = bp.slot_ids
        partner = self.env["res.partner"].create({"name": "Token Host"})
        action = slot._prepare_action(partner)
        self.assertEqual(action["context"]["default_type"], "company")
        plain = self.env["res.users"].create(
            {
                "name": "Plain Ctx",
                "login": "plain_ctx_viewer_%s" % self.env.uid,
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        plain_ctx = compile_context_value(
            token_ctx, self.env(user=plain), record=partner
        )
        self.assertEqual(plain_ctx["default_type"], "person")

    def test_action_context_resolves_rule_value_record_domain(self):
        """rule_value can pick a value from a domain on the clicked card."""
        from odoo.addons.dashboard_engine.tools.condition_domain import (
            compile_context_value,
        )

        token_ctx = {
            "x_kind": {
                "__de__": "rule_value",
                "default": "person",
                "map": [
                    {
                        "when": {
                            "type": "record",
                            "domain": "[('is_company', '=', True)]",
                        },
                        "value": "company",
                    }
                ],
            }
        }
        company = self.env["res.partner"].create(
            {"name": "Rule Co", "is_company": True}
        )
        person = self.env["res.partner"].create(
            {"name": "Rule Person", "is_company": False}
        )
        self.assertEqual(
            compile_context_value(token_ctx, self.env, record=company)["x_kind"],
            "company",
        )
        self.assertEqual(
            compile_context_value(token_ctx, self.env, record=person)["x_kind"],
            "person",
        )
        # No card → skip record rules and use default.
        self.assertEqual(
            compile_context_value(token_ctx, self.env, record=None)["x_kind"],
            "person",
        )

    def test_action_context_rule_value_empty_domain_never_matches(self):
        from odoo.addons.dashboard_engine.tools.condition_domain import (
            compile_context_value,
        )

        token_ctx = {
            "x_kind": {
                "__de__": "rule_value",
                "default": "fallback",
                "map": [
                    {
                        "when": {"type": "record", "domain": "[]"},
                        "value": "matched",
                    }
                ],
            }
        }
        partner = self.env["res.partner"].create({"name": "Empty Domain Host"})
        self.assertEqual(
            compile_context_value(token_ctx, self.env, record=partner)["x_kind"],
            "fallback",
        )


    def test_condition_skipped_when_required_app_missing(self):
        condition = self.env["dashboard.condition"].create(
            {
                "name": "Needs ghost app",
                "model": "res.partner",
                "module_depends": "no_such_dashboard_app_xyz",
                "rule_ids": [
                    (
                        0,
                        0,
                        {
                            "field_name": "is_company",
                            "operator": "=",
                            "value_type": "true",
                        },
                    )
                ],
            }
        )
        self.assertEqual(condition.to_domain(), [])

    def test_action_variant_wins_when_module_installed(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Variants",
                "key": "test_action_variants",
                "host_model_id": self._host_model().id,
                "slot_ids": [
                    (
                        0,
                        0,
                        {
                            "key": "open",
                            "name": "Open",
                            "section": "menu_views",
                            "action_xmlid": "base.action_partner_form",
                            "show_if_zero": True,
                            "action_variant_ids": [
                                (
                                    0,
                                    0,
                                    {
                                        "sequence": 10,
                                        "module_depends": "base",
                                        "action_xmlid": "base.action_partner_customer_form",
                                    },
                                )
                            ],
                        },
                    )
                ],
            }
        )
        self.assertEqual(
            bp.slot_ids._resolved_action_xmlid(),
            "base.action_partner_customer_form",
        )

    def test_seeded_overdue_condition_has_relative_deadline(self):
        condition = self.env.ref(
            "crm_customer_dashboard.condition_crm_overdue_opportunity",
            raise_if_not_found=False,
        )
        if not condition:
            self.skipTest("overdue condition seed missing")
        whens = condition.rule_ids.filtered(
            lambda r: r.value_type == "relative_date"
        ).mapped("relative_when")
        self.assertEqual(whens, ["today"])
        slot = self.env.ref(
            "crm_customer_dashboard.slot_crm_overdue_opportunities",
            raise_if_not_found=False,
        )
        if slot and condition._is_applicable():
            self.assertIn(condition, slot.condition_ids)

    def test_seeded_crm_parity_slots_exist(self):
        """CRM-core seed fill: unassigned, menus, meetings, primary defaults."""
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False
        )
        if not bp:
            self.skipTest("CRM customers blueprint seed missing")
        self.assertEqual(bp.primary_button_label, "Pipeline Analysis")
        self.assertEqual(bp.graph_groupby, "stage_id")
        owned = set(bp.slot_ids.mapped("key"))
        for key in (
            "unassigned",
            "view_leads",
            "new_lead",
            "new_opportunity",
            "report_leads",
            "report_opportunities",
            "report_activities",
            "bottom_meetings",
        ):
            self.assertIn(key, owned, f"missing CRM-owned parity slot {key}")
        meetings = bp.slot_ids.filtered(lambda s: s.key == "bottom_meetings")
        self.assertEqual(meetings.count_field, "meeting_count")
        report_opp = bp.slot_ids.filtered(lambda s: s.key == "report_opportunities")
        self.assertTrue(report_opp.action_variant_ids)
        unassigned = bp.slot_ids.filtered(lambda s: s.key == "unassigned")
        self.assertEqual(unassigned.label, "Unassigned Opportunity")
        self.assertEqual(unassigned.label_alt, "Unassigned Lead")
        self.assertEqual(unassigned.label_alt_groups_xmlids, "crm.group_use_lead")
        # Commercial sale slots are owned by Sales and pooled via share.
        if not bp.share_link_ids.filtered(lambda b: b.key == "sales_customers"):
            return
        effective = set(bp._effective_slots().mapped("key"))
        owned = set(bp.slot_ids.mapped("key"))
        for key in (
            "box_total_due",
            "box_total_overdue",
            "bottom_sales",
            "bottom_deliveries",
            "bottom_invoiced",
            "view_quotations",
            "view_orders",
            "view_transfers",
            "view_invoices",
            "new_quotation",
            "report_sales",
            "report_quotation",
            "report_transfers",
            "report_invoices",
        ):
            self.assertIn(key, effective, f"missing shared commercial slot {key}")
            self.assertNotIn(key, owned, f"CRM must not own shared commercial {key}")
        due = bp._effective_slots().filtered(lambda s: s.key == "box_total_due")
        self.assertEqual(due.section, "button_box")
        self.assertEqual(due.amount_field, "total_due")
        invoiced = bp._effective_slots().filtered(lambda s: s.key == "bottom_invoiced")
        self.assertEqual(invoiced.amount_field, "total_invoiced")

    def test_unassigned_label_flips_with_group_use_lead(self):
        """KPI wording matches v1: Lead(s) when Uses Leads, else Opportunity(ies)."""
        slot = self.env.ref(
            "crm_customer_dashboard.slot_crm_unassigned", raise_if_not_found=False
        )
        group = self.env.ref("crm.group_use_lead", raise_if_not_found=False)
        if not slot or not group:
            self.skipTest("CRM unassigned slot / group_use_lead missing")
        partner = self.env["res.partner"].create({"name": "Label Flip Co"})
        # Fresh user without Uses Leads → Opportunity wording.
        user = self.env["res.users"].create(
            {
                "name": "Label Flip User",
                "login": "label_flip_unassigned",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref(
                                "dashboard_engine.group_dashboard_engine_user"
                            ).id,
                        ],
                    )
                ],
            }
        )
        self.assertFalse(user.has_group("crm.group_use_lead"))
        singular, plural = slot.with_user(user)._resolved_labels()
        self.assertEqual(singular, "Unassigned Opportunity")
        self.assertEqual(plural, "Unassigned Opportunities")
        item = slot.with_user(user)._to_slot_item(partner, values=(2, None))
        self.assertEqual(item["label"], "Unassigned Opportunities")
        # With Uses Leads → Lead wording.
        user.write({"group_ids": [(4, group.id)]})
        singular, plural = slot.with_user(user)._resolved_labels()
        self.assertEqual(singular, "Unassigned Lead")
        self.assertEqual(plural, "Unassigned Leads")
        item = slot.with_user(user)._to_slot_item(partner, values=(1, None))
        self.assertEqual(item["label"], "Unassigned Lead")

    def test_slot_action_strips_inherited_search_defaults(self):
        """Base action search defaults must not override the slot domain."""
        slot = self.env.ref(
            "crm_customer_dashboard.slot_crm_open_opportunities", raise_if_not_found=False
        )
        action = self.env.ref("crm.crm_lead_action_pipeline", raise_if_not_found=False)
        if not slot or not action:
            self.skipTest("CRM open opportunities slot / pipeline action missing")
        partner = self.env["res.partner"].create({"name": "Search Default Co"})
        result = slot._prepare_action(partner)
        self.assertTrue(result)
        ctx = result.get("context") or {}
        self.assertNotIn("search_default_assigned_to_me", ctx)
        self.assertEqual(ctx.get("default_type"), "opportunity")
        domain = result.get("domain") or []
        self.assertTrue(
            any(
                isinstance(leaf, (list, tuple))
                and len(leaf) == 3
                and leaf[0] == "partner_id"
                and leaf[1] == "child_of"
                and leaf[2] == partner.id
                for leaf in domain
            ),
            domain,
        )

    def test_slot_item_hides_zero_amount_when_show_if_zero_false(self):
        """Amount-only metrics honor show_if_zero (Total Overdue pattern)."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Amount Hide Host",
                "key": "test_amount_hide_host",
                "host_model_id": self._host_model().id,
                "state": "draft",
            }
        )
        slot = self.env["dashboard.blueprint.slot"].create(
            {
                "blueprint_id": bp.id,
                "key": "overdue",
                "name": "Overdue",
                "section": "button_box",
                "label": "Total Overdue",
                "show_if_zero": False,
                "amount_field": "credit",
            }
        )
        partner = self.env["res.partner"].create({"name": "Amount Hide Co"})
        self.assertFalse(slot._to_slot_item(partner, values=(None, 0)))
        item = slot._to_slot_item(partner, values=(None, 12.5))
        self.assertEqual(item["amount"], 12.5)
        self.assertEqual(item["label"], "Total Overdue")
        slot.show_if_zero = True
        self.assertTrue(slot._to_slot_item(partner, values=(None, 0)))

    def test_crm_primary_action_hierarchy_leaf_uses_child_of(self):
        """Primary action links back to a company's own child contacts too."""
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False
        )
        if not bp:
            self.skipTest("CRM customers blueprint seed missing")
        self.assertTrue(bp.include_child_records)
        partner = self.env["res.partner"].create({"name": "Hierarchy Co"})
        leaf = bp._primary_host_leaf(partner)
        self.assertEqual(leaf, ("partner_id", "child_of", partner.id))

    def test_crm_view_menus_and_kpis_all_use_child_of(self):
        """Every CRM slot's click-through widens to child_of, matching the
        badge count, which is folded up in Python by _apply_aggregate."""
        for xmlid in (
            "crm_customer_dashboard.slot_crm_menu_opportunities",
            "crm_customer_dashboard.slot_crm_menu_view_leads",
            "crm_customer_dashboard.slot_crm_unassigned",
            "crm_customer_dashboard.slot_crm_open_opportunities",
            "crm_customer_dashboard.slot_crm_overdue_opportunities",
            "crm_customer_dashboard.slot_crm_bottom_opportunities",
        ):
            slot = self.env.ref(xmlid, raise_if_not_found=False)
            if not slot:
                self.skipTest("%s seed missing" % xmlid)
            self.assertIn("child_of", slot.action_domain, slot.action_domain)

    def test_hierarchy_fold_map_walks_parent_id_in_memory(self):
        """A grandchild folds all the way up to whichever ancestor is
        actually a visible card, using two queries regardless of depth."""
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False
        )
        if not bp:
            self.skipTest("CRM customers blueprint seed missing")
        Partner = self.env["res.partner"]
        grandparent = Partner.create({"name": "GP Co"})
        parent = Partner.create({"name": "P Co", "parent_id": grandparent.id})
        child = Partner.create({"name": "C Co", "parent_id": parent.id})
        fold = bp._hierarchy_fold_map([grandparent.id])
        self.assertEqual(sorted(fold.get(child.id, [])), [grandparent.id])
        self.assertEqual(sorted(fold.get(parent.id, [])), [grandparent.id])
        self.assertEqual(sorted(fold.get(grandparent.id, [])), [grandparent.id])

    def test_hierarchy_fold_map_flat_when_include_child_records_off(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Flat Hierarchy",
                "key": "test_flat_hierarchy",
                "host_model_id": self._host_model().id,
                "include_child_records": False,
            }
        )
        partner = self.env["res.partner"].create({"name": "Solo Co"})
        self.assertEqual(bp._hierarchy_fold_map([partner.id]), {partner.id: [partner.id]})

    def test_crm_kpi_count_folds_child_company_leads_into_parent_card(self):
        """A lead on a child contact counts on the parent company's badge
        once include_child_records is on, with a query cost that doesn't grow
        with the number of cards on the page."""
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False
        )
        slot = self.env.ref(
            "crm_customer_dashboard.slot_crm_bottom_opportunities", raise_if_not_found=False
        )
        if not bp or not slot or "crm.lead" not in self.env:
            self.skipTest("CRM customers blueprint/slot seed missing")
        Partner = self.env["res.partner"]
        parent = Partner.create({"name": "Fold Parent Co"})
        child = Partner.create({"name": "Fold Child Co", "parent_id": parent.id})
        other = Partner.create({"name": "Unrelated Co"})
        self.env["crm.lead"].create(
            {
                "name": "Child opp",
                "type": "opportunity",
                "partner_id": child.id,
            }
        )
        records = parent + other
        values = slot._compute_values_batch(records)
        count, _amount = values.get(parent.id, (0, None))
        self.assertEqual(count, 1)
        other_count, _ = values.get(other.id, (0, None))
        self.assertEqual(other_count, 0)

    def test_primary_action_variant_wins_when_module_installed(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Variant Primary",
                "key": "test_variant_primary",
                "host_model_id": self._host_model().id,
                "primary_action_xmlid": "base.action_partner_form",
                "alternate_action_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Always on",
                            "module_depends": "base",
                            "action_xmlid": "base.action_partner_customer_form",
                        },
                    )
                ],
            }
        )
        self.assertEqual(
            bp._resolved_primary_action_xmlid(),
            "base.action_partner_customer_form",
        )

    def test_primary_label_flips_with_the_reference_scope(self):
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False
        )
        scope = self.env.ref(
            "crm_customer_dashboard.scope_crm_pipeline", raise_if_not_found=False
        )
        if not bp or not scope:
            self.skipTest("CRM customers blueprint seed missing")
        self.assertEqual(bp._resolved_primary_label(), "Pipeline Analysis")
        pref = bp._get_or_create_pref()
        pref.scope_ids = [(6, 0, [])]
        self.assertEqual(bp._resolved_primary_label(), "Leads Analysis")
        pref.scope_ids = [(6, 0, [scope.id])]
        self.assertEqual(bp._resolved_primary_label(), "Pipeline Analysis")

    def test_primary_action_domain_matches_card_graph(self):
        """Pipeline Analysis opens the same slice the mini-chart counts."""
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False
        )
        pipeline = self.env.ref(
            "crm_customer_dashboard.scope_crm_pipeline", raise_if_not_found=False
        )
        if not bp or not pipeline or "crm.lead" not in self.env:
            self.skipTest("CRM customers blueprint seed missing")
        partner = self.env["res.partner"].create({"name": "Primary Graph Co"})
        pref = bp._get_or_create_pref()
        pref.scope_ids = [(6, 0, [pipeline.id])]
        settings = bp._effective_graph_settings()
        action = self.env["dashboard.blueprint"].execute_primary_action(
            bp.key, "res.partner", partner.id
        )
        self.assertTrue(action)
        domain = action.get("domain") or []
        self.assertIn(("type", "=", "opportunity"), domain)
        self.assertIn(("partner_id", "child_of", partner.id), domain)
        for leaf in settings["domain"]:
            self.assertIn(leaf, domain, domain)
        ctx = action.get("context") or {}
        # Enterprise (and similar) search defaults must not hide rows the
        # card already counted.
        self.assertFalse(
            any(
                isinstance(key, str) and key.startswith("search_default_")
                for key in ctx
            ),
            ctx,
        )
        self.assertEqual(
            ctx.get("graph_groupbys"),
            settings.get("groupbys") or [settings["groupby"]],
        )
        self.assertEqual(
            ctx.get("graph_measure"),
            self.env["dashboard.blueprint"]._odoo_view_measure_name(
                settings["measure"]
            ),
        )

    def test_primary_action_ignores_stale_measure_from_other_chart_model(self):
        """Stale Sales Orders measure must not crash Pipeline Analysis GraphView."""
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False
        )
        if not bp or "crm.lead" not in self.env or "sale.order" not in self.env:
            self.skipTest("CRM customers / Sales models missing")
        partner = self.env["res.partner"].create({"name": "Stale Measure Co"})
        pipe = bp.graph_variant_ids.filtered(lambda v: v.graph_model == "crm.lead")[:1]
        so_amt = self.env["ir.model.fields"].search(
            [("model", "=", "sale.order"), ("name", "=", "amount_untaxed")], limit=1
        )
        if not pipe or not so_amt:
            self.skipTest("CRM Pipeline option or amount_untaxed missing")
        pref = bp._get_or_create_pref()
        pref.with_context(skip_variant_graph_defaults=True).write(
            {
                "preferred_graph_variant_id": pipe.id,
                "preferred_graph_model": "crm.lead",
                "measure_field_id": so_amt.id,
                "measure_aggregator": "sum",
            }
        )
        settings = bp._effective_graph_settings()
        self.assertNotEqual(
            self.env["dashboard.blueprint"]._odoo_view_measure_name(
                settings.get("measure")
            ),
            "amount_untaxed",
            settings,
        )
        action = self.env["dashboard.blueprint"].execute_primary_action(
            bp.key, "res.partner", partner.id
        )
        ctx = action.get("context") or {}
        self.assertNotEqual(ctx.get("graph_measure"), "amount_untaxed", ctx)

    def test_primary_action_uses_active_chart_model_for_graph_ctx(self):
        """Sales Orders pick must pass sale.order measure into the primary graph."""
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False
        )
        if not bp or "sale.order" not in self.env:
            self.skipTest("CRM customers / Sales models missing")
        partner = self.env["res.partner"].create({"name": "SO Primary Co"})
        so = bp.graph_variant_ids.filtered(lambda v: v.graph_model == "sale.order")[:1]
        if not so:
            self.skipTest("Sales Orders chart option missing")
        bp._ensure_option_graph_defaults()
        pref = bp._get_or_create_pref()
        pref.write({"preferred_graph_variant_id": so.id})
        action = self.env["dashboard.blueprint"].execute_primary_action(
            bp.key, "res.partner", partner.id
        )
        self.assertEqual(action.get("res_model"), "sale.order")
        ctx = action.get("context") or {}
        self.assertEqual(ctx.get("graph_measure"), "amount_untaxed", ctx)
        self.assertTrue(ctx.get("graph_groupbys"), ctx)

    def test_primary_action_skips_graph_ctx_when_model_mismatch(self):
        """Graph groupbys must not be pushed when action model != graph model."""
        if (
            "product.product" not in self.env
            or "sale.report" not in self.env
            or "sale.order" not in self.env
        ):
            self.skipTest("Sales models missing")
        product = self.env["product.product"].search([], limit=1)
        if not product:
            self.skipTest("No product.product available")
        # Synthetic mismatch: mini-chart on sale.report, primary opens sale.order.
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Primary Mismatch",
                "key": "primary_mismatch_%s" % self.env.uid,
                "host_model_id": self.env.ref("product.model_product_product").id,
                "graph_model": "sale.report",
                "graph_data_field": "product_id",
                "graph_measure": "price_subtotal",
                "graph_groupby": "date:month",
                "primary_action_xmlid": "sale.action_orders",
                "state": "published",
            }
        )
        action = self.env["dashboard.blueprint"].execute_primary_action(
            bp.key, "product.product", product.id
        )
        self.assertTrue(action)
        self.assertEqual(action.get("res_model"), "sale.order")
        ctx = action.get("context") or {}
        self.assertNotIn("graph_groupbys", ctx, ctx)
        self.assertNotIn("graph_measure", ctx, ctx)
        self.assertEqual(ctx.get("dashboard_blueprint_key"), bp.key)

    def test_primary_action_opens_sales_report_graph(self):
        """Sales Analysis opens sale.report graph filtered by product_id."""
        bp = self.env.ref(
            "sales_product_dashboard.blueprint_sales_products",
            raise_if_not_found=False,
        )
        if not bp or "product.product" not in self.env or "sale.report" not in self.env:
            self.skipTest("Sales products blueprint seed missing")
        product = self.env["product.product"].search([], limit=1)
        if not product:
            self.skipTest("No product.product available")
        action = self.env["dashboard.blueprint"].execute_primary_action(
            bp.key, "product.product", product.id
        )
        self.assertTrue(action)
        self.assertEqual(action.get("res_model"), "sale.report")
        view_mode = action.get("view_mode") or ""
        self.assertTrue(
            view_mode.startswith("graph")
            or (action.get("views") and action["views"][0][1] == "graph"),
            action.get("views") or view_mode,
        )
        domain = action.get("domain") or []
        self.assertIn(("product_id", "=", product.id), domain)
        ctx = action.get("context") or {}
        self.assertIn("graph_groupbys", ctx)
        self.assertEqual(ctx.get("graph_measure"), "price_subtotal")
        self.assertEqual(ctx.get("pivot_measures"), ["price_subtotal"])
        self.assertIn(ctx.get("graph_mode"), ("bar", "line"))
        self.env["sale.report"].search(domain, limit=1)

    def test_restrict_scope_domain_empty_until_ticked(self):
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False
        )
        mine = self.env.ref(
            "crm_customer_dashboard.scope_crm_mine", raise_if_not_found=False
        )
        if not bp or not mine:
            self.skipTest("CRM customers blueprint seed missing")
        self.assertFalse(bp._restrict_scope_domain())
        pref = bp._get_or_create_pref()
        pref.scope_ids = [(4, mine.id)]
        self.assertEqual(bp._restrict_scope_domain(), [("user_id", "=", self.env.uid)])

    def test_unified_groupby_tags_drive_multi_level_specs(self):
        """One ordered Group By list is the source of truth for graph levels."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Unified GroupBy Host",
                "key": "unified_groupby_%s" % self.env.uid,
                "host_model_id": self.env.ref("base.model_res_partner").id,
                "graph_model": "res.partner",
                "graph_groupby": "country_id",
                "state": "draft",
            }
        )
        Fields = self.env["ir.model.fields"]
        Fields.ensure_date_period_fields("res.partner")
        country = Fields.search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")], limit=1
        )
        day_tag = Fields.period_field_for("res.partner", "create_date", "day")
        self.assertTrue(country and day_tag)
        pref = bp._get_or_create_pref()
        pref.write(
            {
                "groupby_ids": [(6, 0, [day_tag.id, country.id])],
                "ordered_groupby_ids": "%s,%s" % (day_tag.id, country.id),
            }
        )
        settings = bp._effective_graph_settings()
        self.assertEqual(settings["groupbys"], ["create_date:day", "country_id"])
        # Legacy columns are one-way mirrors of the unified list.
        self.assertEqual(pref.groupby_field_id, day_tag)
        self.assertEqual(pref.groupby_extra_ids, country)

    def test_legacy_groupby_write_lifts_into_unified_list(self):
        """Old primary/extra writes still work but land in groupby_ids."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Legacy Lift Host",
                "key": "legacy_lift_%s" % self.env.uid,
                "host_model_id": self.env.ref("base.model_res_partner").id,
                "graph_model": "res.partner",
                "graph_groupby": "is_company",
                "state": "draft",
            }
        )
        Fields = self.env["ir.model.fields"]
        Fields.ensure_date_period_fields("res.partner")
        country = Fields.search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")], limit=1
        )
        week_tag = Fields.period_field_for("res.partner", "create_date", "week")
        self.assertTrue(country and week_tag)
        pref = bp._get_or_create_pref()
        # Legacy write of a raw date + Per still lifts, then heal/normalize
        # can swap to the virtual week tag — assert the graph spec either way.
        created = Fields.search(
            [("model", "=", "res.partner"), ("name", "=", "create_date")], limit=1
        )
        pref.write(
            {
                "groupby_field_id": created.id,
                "groupby_extra_ids": [(6, 0, country.ids)],
                "groupby_granularity": "week",
            }
        )
        self.assertEqual(
            set(pref.groupby_ids.ids),
            {created.id, country.id},
        )
        self.assertEqual(
            bp._effective_graph_settings()["groupbys"],
            ["create_date:week", "country_id"],
        )
        # Explicit v1-style virtual tag write.
        pref.write(
            {
                "groupby_ids": [(6, 0, [week_tag.id, country.id])],
                "ordered_groupby_ids": "%s,%s" % (week_tag.id, country.id),
            }
        )
        self.assertEqual(
            bp._effective_graph_settings()["groupbys"],
            ["create_date:week", "country_id"],
        )

    def test_heal_unified_groupby_from_legacy_only_row(self):
        """Registry heal lifts prefs that still only have legacy columns."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Heal GroupBy Host",
                "key": "heal_groupby_%s" % self.env.uid,
                "host_model_id": self.env.ref("base.model_res_partner").id,
                "graph_model": "res.partner",
                "state": "draft",
            }
        )
        Fields = self.env["ir.model.fields"]
        country = Fields.search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")], limit=1
        )
        self.assertTrue(country)
        Pref = self.env["dashboard.user.pref"]
        pref = Pref.create(
            {
                "blueprint_id": bp.id,
                "user_id": self.env.uid,
            }
        )
        # Simulate a pre-unification row: legacy filled, unified empty.
        Pref.browse(pref.id).invalidate_recordset()
        self.env.cr.execute(
            """
            UPDATE dashboard_user_pref
               SET groupby_field_id = %s
             WHERE id = %s
            """,
            (country.id, pref.id),
        )
        self.env.cr.execute(
            """
            DELETE FROM dashboard_user_pref_groupby_rel WHERE pref_id = %s
            """,
            (pref.id,),
        )
        pref.invalidate_recordset()
        self.assertFalse(pref.groupby_ids)
        self.assertEqual(pref.groupby_field_id, country)
        Pref._heal_unified_groupby_prefs()
        pref.invalidate_recordset()
        self.assertEqual(pref.groupby_ids, country)
        self.assertEqual(pref.ordered_groupby_ids, str(country.id))

    def test_scope_presentation_uses_module_aware_label_variants(self):
        """Gear labels/help come from scope data + label variants, not the form."""
        Scope = self.env["dashboard.blueprint.scope"]
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Presentation Host",
                "key": "presentation_host_%s" % self.env.uid,
                "host_model_id": self.env.ref("base.model_res_partner").id,
                "graph_model": "res.partner",
                "state": "draft",
            }
        )
        scope = Scope.create(
            {
                "blueprint_id": bp.id,
                "name": "Base Label",
                "description": "Base help",
                "mode": "restrict",
                "domain": "[('user_id', '=', uid)]",
            }
        )
        presented = scope._presentation()
        self.assertEqual(presented["name"], "Base Label")
        self.assertEqual(presented["description"], "Base help")

        # Empty module_depends always matches; more modules beats fewer.
        self.env["dashboard.blueprint.scope.label"].create(
            {
                "scope_id": scope.id,
                "sequence": 10,
                "module_depends": "base",
                "name": "With Base",
                "description": "Help when base is installed",
            }
        )
        presented = scope._presentation()
        self.assertEqual(presented["name"], "With Base")
        self.assertEqual(presented["description"], "Help when base is installed")
        self.assertEqual(scope.display_label, "With Base")

    def _crm_only_mine_fixture(self):
        """Partner with one mine + one teammate opportunity; CRM My scope."""
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False
        )
        mine = self.env.ref(
            "crm_customer_dashboard.scope_crm_mine", raise_if_not_found=False
        )
        if not bp or not mine or "crm.lead" not in self.env:
            self.skipTest("CRM customers blueprint seed missing")
        other_user = self.env["res.users"].create(
            {
                "name": "Other Salesperson",
                "login": "other_salesperson_fold_%s" % self.env.uid,
            }
        )
        partner = self.env["res.partner"].create({"name": "Only Mine Co"})
        self.env["crm.lead"].create(
            {
                "name": "Mine",
                "type": "opportunity",
                "partner_id": partner.id,
                "user_id": self.env.uid,
            }
        )
        self.env["crm.lead"].create(
            {
                "name": "Not mine",
                "type": "opportunity",
                "partner_id": partner.id,
                "user_id": other_user.id,
            }
        )
        return bp, mine, partner

    def test_only_mine_scope_narrows_crm_kpi_count_and_action(self):
        """Ticking My Pipeline narrows right KPI count + click domain."""
        bp, mine, partner = self._crm_only_mine_fixture()
        slot = self.env.ref(
            "crm_customer_dashboard.slot_crm_open_opportunities",
            raise_if_not_found=False,
        )
        if not slot:
            self.skipTest("CRM open opportunities KPI slot missing")
        records = partner
        before = slot._compute_values_batch(records).get(partner.id, (0, None))[0]
        self.assertEqual(before, 2)

        pref = bp._get_or_create_pref()
        pref.scope_ids = [(4, mine.id)]
        after = slot._compute_values_batch(records).get(partner.id, (0, None))[0]
        self.assertEqual(after, 1)

        action = slot._prepare_action(partner)
        self.assertIn(("user_id", "=", self.env.uid), action["domain"])

    def test_only_mine_scope_narrows_commercial_bottoms_and_views(self):
        """Product B′: My narrows same-model commercial bottoms / views / reports.

        New menus stay defaults-only (no My domain). Spec superseded for
        commercial surfaces by 2026-08-03-panel-filters-linked-my design.
        """
        bp, mine, partner = self._crm_only_mine_fixture()
        bottom = self.env.ref(
            "crm_customer_dashboard.slot_crm_bottom_opportunities",
            raise_if_not_found=False,
        )
        report = self.env.ref(
            "crm_customer_dashboard.slot_crm_menu_report_opportunities",
            raise_if_not_found=False,
        )
        views = self.env.ref(
            "crm_customer_dashboard.slot_crm_menu_opportunities",
            raise_if_not_found=False,
        )
        if not bottom:
            self.skipTest("CRM bottom opportunities slot missing")

        pref = bp._get_or_create_pref()
        pref.scope_ids = [(4, mine.id)]

        bottom_count = bottom.with_context(
            dashboard_blueprint_key=bp.key
        )._compute_values_batch(partner).get(partner.id, (0, None))[0]
        self.assertEqual(bottom_count, 1)
        bottom_action = bottom.with_context(
            dashboard_blueprint_key=bp.key
        )._prepare_action(partner)
        self.assertIn(
            ("user_id", "=", self.env.uid), bottom_action.get("domain") or []
        )

        # Views (list/action) inherit My when they target the graph model.
        if views:
            action = views.with_context(
                dashboard_blueprint_key=bp.key
            )._prepare_action(partner)
            if action and (views.compute_model or views.action_model) == bp.graph_model:
                self.assertIn(
                    ("user_id", "=", self.env.uid),
                    action.get("domain") or [],
                    "slot %s should inherit My on commercial surfaces" % views.key,
                )
        # Report slots may open a report action without a domain — only assert
        # when the prepared action carries a domain list.
        if report:
            action = report.with_context(
                dashboard_blueprint_key=bp.key
            )._prepare_action(partner)
            if action and action.get("domain"):
                self.assertIn(
                    ("user_id", "=", self.env.uid),
                    action.get("domain") or [],
                    "slot %s should inherit My on commercial surfaces" % report.key,
                )

    def test_dashboard_fields_are_inert_without_a_blueprint(self):
        """Models that are not hosting a dashboard must pay nothing."""
        partners = self.env["res.partner"].search([], limit=10)
        partners.invalidate_recordset()
        before = sql_db.sql_counter
        self.assertFalse(any(partners.mapped("dashboard_slots")))
        self.assertFalse(any(partners.mapped("dashboard_graph_data")))
        self.assertFalse(any(partners.mapped("dashboard_primary_label")))
        self.assertEqual(sql_db.sql_counter - before, 0)

    def test_seeded_sales_parity_slots_exist(self):
        bp = self.env.ref(
            "sales_customer_dashboard.blueprint_sales_customers", raise_if_not_found=False
        )
        if not bp:
            self.skipTest("Sales customers blueprint seed missing")
        keys = set(bp.slot_ids.mapped("key"))
        for key in (
            "quotations",
            "to_deliver",
            "to_invoice",
            "to_upsell",
            "bottom_sales",
            "bottom_deliveries",
            "bottom_invoiced",
            "box_total_due",
            "box_total_overdue",
            "view_quotations",
            "view_orders",
            "new_quotation",
            "report_sales",
            "report_quotation",
            "report_transfers",
            "report_invoices",
        ):
            self.assertIn(key, keys, f"missing sales parity slot {key}")
        share_keys = set(bp.share_link_ids.mapped("key"))
        # Phase A: customer packs share CRM↔Sales only (POS↔Website stay engine-side).
        if "crm_customers" not in share_keys:
            return
        self.assertIn("crm_customers", share_keys)
        effective = set(bp._effective_slots().mapped("key"))
        self.assertIn("bottom_meetings", effective)

    def test_seeded_pos_parity_slots_exist(self):
        bp = self.env.ref(
            "pos_sales_customer_dashboard.blueprint_pos_customers", raise_if_not_found=False
        )
        if not bp:
            self.skipTest("POS customers blueprint seed missing")
        keys = set(bp.slot_ids.mapped("key"))
        self.assertIn("pos_orders", keys)
        self.assertIn("pos_to_invoice", keys)
        self.assertIn("view_pos_orders", keys)
        self.assertTrue(bp.scope_ids)
        hub = self.env.ref(
            "customer_360_dashboard.blueprint_customer_360",
            raise_if_not_found=False,
        )
        if hub:
            self.assertTrue(
                bp.share_link_ids.filtered(lambda b: b.key == "customer_360")
            )
        self.assertFalse(
            bp.share_link_ids.filtered(lambda b: b.key == "website_customers")
        )

    def test_modules_installed_is_memoized_per_request(self):
        Blueprint = self.env["dashboard.blueprint"]
        self.env.cr.cache.pop("dashboard_engine.modules_installed", None)
        before = sql_db.sql_counter
        Blueprint._modules_installed_static("base")
        mid = sql_db.sql_counter
        Blueprint._modules_installed_static("base")
        after = sql_db.sql_counter
        self.assertGreater(mid - before, 0)
        self.assertEqual(after - mid, 0)

    def test_internal_user_can_render_published_blueprint_without_engine_acl(self):
        """Salespeople must see card payloads without the engine User group."""
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers", raise_if_not_found=False
        )
        if not bp:
            self.skipTest("CRM customers blueprint seed missing")
        partner = self.env["res.partner"].create({"name": "Internal Render Co"})
        user = self.env["res.users"].create(
            {
                "name": "Plain Internal",
                "login": "plain_internal_dashboard",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.assertFalse(
            user.has_group("dashboard_engine.group_dashboard_engine_user")
        )
        records = partner.with_user(user).with_context(
            dashboard_blueprint_key=bp.key
        )
        # Must not raise AccessError; payload may be empty of KPIs but present.
        slots = records.dashboard_slots
        self.assertTrue(slots)


@tagged("post_install", "-at_install")
class TestDashboardBlueprint(TransactionCase):
    def test_slot_ui_number_source_inference(self):
        Slot = self.env["dashboard.blueprint.slot"]
        bp = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers",
            raise_if_not_found=False,
        )
        if not bp:
            self.skipTest("crm_customer_dashboard not installed")
        related = Slot.new(
            {
                "blueprint_id": bp.id,
                "section": "bottom",
                "label": "Opps",
                "compute_model": "crm.lead",
            }
        )
        self.assertTrue(related.ui_number_from_related)
        self.assertFalse(related.ui_number_from_host)
        host = Slot.new(
            {
                "blueprint_id": bp.id,
                "section": "bottom",
                "label": "Meetings",
                "count_field": "meeting_count",
            }
        )
        self.assertFalse(host.ui_number_from_related)
        self.assertTrue(host.ui_number_from_host)

    def test_slot_style_when_positive_resolves_danger_only_if_count(self):
        Slot = self.env["dashboard.blueprint.slot"]
        # Prefer a seeded CRM overdue slot if present; else create minimal slot on a test blueprint.
        slot = self.env.ref(
            "crm_customer_dashboard.slot_crm_overdue_opportunities",
            raise_if_not_found=False,
        )
        if not slot:
            self.skipTest("CRM customer preset not installed")
        slot.write({"style": "danger", "style_mode": "when_positive", "show_if_zero": True})
        partner = self.env["res.partner"].create({"name": "Health Style Partner"})
        zero = slot._to_slot_item(partner, values=(0, None))
        self.assertTrue(zero)
        self.assertEqual(zero["style"], "default")
        positive = slot._to_slot_item(partner, values=(2, None))
        self.assertEqual(positive["style"], "danger")

    def test_slot_style_when_positive_warning_for_amount(self):
        bp = self.env["dashboard.blueprint"].search(
            [("key", "=", "sales_customers")], limit=1
        )
        if not bp:
            self.skipTest("Sales customers blueprint missing")
        slot = self.env["dashboard.blueprint.slot"].create({
            "blueprint_id": bp.id,
            "key": "test_health_amount",
            "name": "Test Health Amount",
            "section": "button_box",
            "style": "warning",
            "style_mode": "when_positive",
            "show_if_zero": True,
            "value_mode": "amount",
            "amount_field": "total_due",
        })
        partner = self.env["res.partner"].create({"name": "Amt Health"})
        self.assertEqual(
            slot._to_slot_item(partner, values=(None, 0))["style"],
            "default",
        )
        self.assertEqual(
            slot._to_slot_item(partner, values=(None, 12.5))["style"],
            "warning",
        )


@tagged("post_install", "-at_install")
class TestDashboardBlueprintTemplate(TransactionCase):
    """Phase 12: export/import a blueprint as a portable JSON template."""

    def _host_model(self):
        return self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def _full_blueprint(self):
        """A blueprint exercising every exportable child: scope, header
        item, slot with a condition, and a primary action variant."""
        condition = self.env["dashboard.condition"].create(
            {
                "name": "Test Template Condition",
                "model": "res.partner",
                "match": "all",
                "rule_ids": [
                    (
                        0,
                        0,
                        {
                            "field_name": "is_company",
                            "operator": "=",
                            "value_type": "true",
                        },
                    )
                ],
            }
        )
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Template Source",
                "key": "test_template_source",
                "host_model_id": self._host_model().id,
                "menu_name": "Template Source Dashboard",
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_groupby": "is_company",
                "graph_measure": "__count",
                "state": "draft",
                "header_line_ids": [
                    (
                        0,
                        0,
                        {
                            "kind": "subtitle",
                            "field_names": "email",
                        },
                    )
                ],
                "scope_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Companies only",
                            "mode": "include",
                            "domain": "[('is_company', '=', True)]",
                            "default_on": True,
                        },
                    )
                ],
                "alternate_action_ids": [
                    (0, 0, {"name": "Fallback", "action_xmlid": "base.action_partner_form"})
                ],
                "slot_ids": [
                    (
                        0,
                        0,
                        {
                            "key": "companies",
                            "name": "Companies",
                            "section": "kpi",
                            "label": "Company",
                            "label_plural": "Companies",
                            "compute_model": "res.partner",
                            "relate_field": "parent_id",
                            "compute_domain": "[]",
                            "condition_ids": [(6, 0, condition.ids)],
                        },
                    )
                ],
            }
        )
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")], limit=1
        )
        bp.graph_groupby_extra_ids = [(6, 0, country_field.ids)]
        bp.closed_period_field_id = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "write_date")], limit=1
        ).id
        return bp

    def test_export_then_import_round_trips_every_child(self):
        bp = self._full_blueprint()
        data = bp._export_template()
        # Must survive an actual JSON round trip, not just a Python dict copy.
        data = json.loads(json.dumps(data))

        imported = self.env["dashboard.blueprint"]._import_template(data)
        self.addCleanup(imported.unlink)

        self.assertEqual(imported.state, "draft")
        self.assertNotEqual(imported.key, bp.key)
        self.assertEqual(imported.host_model_id, bp.host_model_id)
        self.assertEqual(imported.graph_groupby, bp.graph_groupby)
        self.assertEqual(
            imported._effective_graph_settings()["groupbys"],
            bp._effective_graph_settings()["groupbys"],
        )
        self.assertEqual(
            imported.closed_period_field_id.name, bp.closed_period_field_id.name
        )
        self.assertEqual(len(imported.scope_ids), len(bp.scope_ids))
        self.assertEqual(imported.scope_ids.name, bp.scope_ids.name)
        self.assertEqual(len(imported.header_line_ids), len(bp.header_line_ids))
        self.assertEqual(
            imported.header_line_ids.field_names, bp.header_line_ids.field_names
        )
        self.assertEqual(
            len(imported.alternate_action_ids),
            len(bp.alternate_action_ids),
        )
        self.assertEqual(len(imported.slot_ids), len(bp.slot_ids))
        imported_slot = imported.slot_ids[0]
        source_slot = bp.slot_ids[0]
        self.assertEqual(imported_slot.key, source_slot.key)
        self.assertEqual(len(imported_slot.condition_ids), 1)
        self.assertEqual(
            imported_slot.condition_ids.name, source_slot.condition_ids.name
        )
        # The dedup-by-name lookup must not duplicate the shared condition.
        self.assertEqual(imported_slot.condition_ids, source_slot.condition_ids)

    def test_importing_twice_gets_a_unique_key(self):
        bp = self._full_blueprint()
        data = json.loads(json.dumps(bp._export_template()))
        first = self.env["dashboard.blueprint"]._import_template(data)
        second = self.env["dashboard.blueprint"]._import_template(data)
        self.addCleanup(first.unlink)
        self.addCleanup(second.unlink)
        self.assertNotEqual(first.key, second.key)

    def test_import_rejects_a_non_template_file(self):
        with self.assertRaises(UserError):
            self.env["dashboard.blueprint"]._import_template({"not": "a template"})

    def test_import_requires_the_host_model_to_exist(self):
        bp = self._full_blueprint()
        data = json.loads(json.dumps(bp._export_template()))
        data["blueprint"]["host_model_name"] = "no.such.model"
        with self.assertRaises(UserError):
            self.env["dashboard.blueprint"]._import_template(data)

    def test_export_button_downloads_an_attachment(self):
        bp = self._full_blueprint()
        action = bp.action_export_template()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertIn("/web/content/", action["url"])

    def test_compose_hub_merges_same_restrict_kind(self):
        host = self._host_model()
        suffix = self.env.uid
        hub = self.env["dashboard.blueprint"].create(
            {
                "name": "Merge Hub",
                "key": "test_merge_restrict_hub_%s" % suffix,
                "host_model_id": host.id,
                "is_compose_hub": True,
                "state": "draft",
                "graph_model": "res.partner",
            }
        )
        pack_a = self.env["dashboard.blueprint"].create(
            {
                "name": "Pack A",
                "key": "test_merge_pack_a_%s" % suffix,
                "host_model_id": host.id,
                "state": "draft",
                "graph_model": "res.partner",
            }
        )
        pack_b = self.env["dashboard.blueprint"].create(
            {
                "name": "Pack B",
                "key": "test_merge_pack_b_%s" % suffix,
                "host_model_id": host.id,
                "state": "draft",
                "graph_model": "res.partner",
            }
        )
        hub.write({"share_link_ids": [(6, 0, (pack_a | pack_b).ids)]})
        a_mine = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": pack_a.id,
                "name": "My Pipeline",
                "description": "Only show opportunities assigned to you.",
                "mode": "restrict",
                "restrict_kind": "mine",
                "merge_noun": "opportunities",
                "domain": "[('user_id', '=', uid)]",
                "sequence": 10,
                "default_on": False,
            }
        )
        b_mine = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": pack_b.id,
                "name": "Only mine",
                "description": "Show only sales orders you are responsible for.",
                "mode": "restrict",
                "restrict_kind": "mine",
                "merge_noun": "sales orders",
                "domain": "[('user_id', '=', uid)]",
                "sequence": 30,
                "default_on": False,
            }
        )
        unique = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": pack_a.id,
                "name": "Unassigned leads",
                "mode": "restrict",
                "domain": "[('user_id', '=', False)]",
                "sequence": 40,
                "default_on": False,
            }
        )
        self.assertTrue(hub.is_compose_hub)
        self.assertEqual(set(hub.share_link_ids.ids), {pack_a.id, pack_b.id})
        mine_scopes = hub._runtime_scopes().filtered(
            lambda s: s.restrict_kind == "mine"
        )
        self.assertEqual(set(mine_scopes.ids), {a_mine.id, b_mine.id})
        pref = self.env["dashboard.user.pref"].create(
            {
                "blueprint_id": hub.id,
                "user_id": self.env.user.id,
            }
        )
        pref.invalidate_recordset(["applicable_restrict_scope_ids"])
        reps = pref.applicable_restrict_scope_ids
        self.assertIn(a_mine, reps)
        self.assertNotIn(b_mine, reps)
        self.assertIn(unique, reps)
        merged = a_mine.with_context(
            dashboard_scope_viewer_id=hub.id
        )._presentation()
        self.assertEqual(merged["name"], "My Records")
        self.assertIn("opportunities", merged["description"])
        self.assertIn("sales orders", merged["description"])
        self.assertIn("assigned to you", merged["description"])
        pack_label = a_mine.with_context(
            dashboard_scope_viewer_id=pack_a.id
        )._presentation()
        self.assertEqual(pack_label["name"], "My Pipeline")
        rows = (
            self.env["dashboard.blueprint.scope"]
            .with_context(dashboard_scope_viewer_id={"id": hub.id})
            .search_read([("id", "=", a_mine.id)], ["display_label"])
        )
        self.assertEqual(rows[0]["display_label"], "My Records")
        pref.write({"scope_ids": [(6, 0, [a_mine.id])]})
        self.assertIn(a_mine, pref.scope_ids)
        self.assertIn(b_mine, pref.scope_ids)
        pref.write({"scope_ids": [(6, 0, [])]})
        self.assertNotIn(a_mine, pref.scope_ids)
        self.assertNotIn(b_mine, pref.scope_ids)

    def test_single_restrict_kind_keeps_pack_title_on_hub(self):
        host = self._host_model()
        suffix = self.env.uid
        hub = self.env["dashboard.blueprint"].create(
            {
                "name": "Single Kind Hub",
                "key": "test_single_restrict_hub_%s" % suffix,
                "host_model_id": host.id,
                "is_compose_hub": True,
                "state": "draft",
                "graph_model": "res.partner",
            }
        )
        pack = self.env["dashboard.blueprint"].create(
            {
                "name": "Pack Only",
                "key": "test_single_restrict_pack_%s" % suffix,
                "host_model_id": host.id,
                "state": "draft",
                "graph_model": "res.partner",
            }
        )
        hub.write({"share_link_ids": [(6, 0, pack.ids)]})
        mine = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": pack.id,
                "name": "My Pipeline",
                "mode": "restrict",
                "restrict_kind": "mine",
                "merge_noun": "opportunities",
                "sequence": 10,
                "default_on": False,
            }
        )
        pref = self.env["dashboard.user.pref"].create(
            {
                "blueprint_id": hub.id,
                "user_id": self.env.user.id,
            }
        )
        pref.invalidate_recordset(["applicable_restrict_scope_ids"])
        self.assertEqual(pref.applicable_restrict_scope_ids, mine)
        presented = mine.with_context(
            dashboard_scope_viewer_id=hub.id
        )._presentation()
        self.assertEqual(presented["name"], "My Pipeline")


@tagged("post_install", "-at_install")
class TestDashboardBlueprintMultiCompany(TransactionCase):
    """Phase 10 leftover: company-scoped blueprint *configuration*.

    Runtime dashboard data safety is untouched by this — it already comes
    from the host/graph model's own multi-company record rules (ORM-only
    aggregation, see the module's architecture docstring). This only
    covers who can see/edit a company-restricted blueprint record.
    """

    def _host_model(self):
        return self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def _manager_in(self, company, login):
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "company_id": company.id,
                "company_ids": [(6, 0, company.ids)],
                "group_ids": [
                    (
                        4,
                        self.env.ref(
                            "dashboard_engine.group_dashboard_engine_manager"
                        ).id,
                    )
                ],
            }
        )

    def test_company_scoped_blueprint_hidden_from_other_companies(self):
        other_company = self.env["res.company"].create({"name": "Other Co"})
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Other Co only",
                "key": "test_other_co_only",
                "host_model_id": self._host_model().id,
                "company_id": other_company.id,
                "state": "draft",
            }
        )
        main_company = self.env.ref("base.main_company")
        manager_main = self._manager_in(main_company, "test_manager_main_co")
        manager_other = self._manager_in(other_company, "test_manager_other_co")

        self.assertFalse(
            self.env["dashboard.blueprint"]
            .with_user(manager_main)
            .search([("id", "=", bp.id)])
        )
        self.assertTrue(
            self.env["dashboard.blueprint"]
            .with_user(manager_other)
            .search([("id", "=", bp.id)])
        )

    def test_blueprint_without_a_company_is_shared(self):
        other_company = self.env["res.company"].create({"name": "Shared Co"})
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Shared blueprint",
                "key": "test_shared_blueprint",
                "host_model_id": self._host_model().id,
                "state": "draft",
            }
        )
        self.assertFalse(bp.company_id)
        manager_other = self._manager_in(other_company, "test_manager_shared_co")
        self.assertTrue(
            self.env["dashboard.blueprint"]
            .with_user(manager_other)
            .search([("id", "=", bp.id)])
        )

    def test_share_blueprints_union_slots_bidirectional(self):
        """A↔B: each sees the other's kpi/menu/bottom slots."""
        host = self._host_model()
        a = self.env["dashboard.blueprint"].create(
            {
                "name": "Share A",
                "key": "test_share_a_%s" % self.env.uid,
                "host_model_id": host.id,
                "state": "draft",
            }
        )
        b = self.env["dashboard.blueprint"].create(
            {
                "name": "Share B",
                "key": "test_share_b_%s" % self.env.uid,
                "host_model_id": host.id,
                "state": "draft",
            }
        )
        self.env["dashboard.blueprint.slot"].create(
            [
                {
                    "blueprint_id": a.id,
                    "key": "kpi_a",
                    "name": "KPI A",
                    "section": "kpi",
                    "label": "A",
                    "show_if_zero": True,
                    "compute_model": "res.partner",
                    "relate_field": "parent_id",
                },
                {
                    "blueprint_id": b.id,
                    "key": "kpi_b",
                    "name": "KPI B",
                    "section": "kpi",
                    "label": "B",
                    "show_if_zero": True,
                    "compute_model": "res.partner",
                    "relate_field": "parent_id",
                },
            ]
        )
        a.share_link_ids = [(4, b.id)]
        self.assertIn(a, b.share_link_ids)
        self.assertEqual(
            set(a._effective_slots().mapped("key")), {"kpi_a", "kpi_b"}
        )
        self.assertEqual(
            set(b._effective_slots().mapped("key")), {"kpi_a", "kpi_b"}
        )

    def test_share_dedupe_prefers_current_blueprint_key(self):
        host = self._host_model()
        a = self.env["dashboard.blueprint"].create(
            {
                "name": "Dedupe A",
                "key": "test_dedupe_a_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 10,
            }
        )
        b = self.env["dashboard.blueprint"].create(
            {
                "name": "Dedupe B",
                "key": "test_dedupe_b_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 20,
            }
        )
        slot_a, slot_b = self.env["dashboard.blueprint.slot"].create(
            [
                {
                    "blueprint_id": a.id,
                    "key": "same",
                    "name": "From A",
                    "section": "kpi",
                    "label": "A wins",
                    "show_if_zero": True,
                    "compute_model": "res.partner",
                    "relate_field": "parent_id",
                },
                {
                    "blueprint_id": b.id,
                    "key": "same",
                    "name": "From B",
                    "section": "kpi",
                    "label": "B copy",
                    "show_if_zero": True,
                    "compute_model": "res.partner",
                    "relate_field": "parent_id",
                },
            ]
        )
        a.share_link_ids = [(4, b.id)]
        eff_a = a._effective_slots().filtered(lambda s: s.key == "same")
        self.assertEqual(eff_a, slot_a)
        eff_b = b._effective_slots().filtered(lambda s: s.key == "same")
        self.assertEqual(eff_b, slot_b)

    def test_share_rejects_different_host_model(self):
        partner = self._host_model()
        user_model = self.env["ir.model"].search(
            [("model", "=", "res.users")], limit=1
        )
        a = self.env["dashboard.blueprint"].create(
            {
                "name": "Host Partner",
                "key": "test_share_host_a_%s" % self.env.uid,
                "host_model_id": partner.id,
            }
        )
        b = self.env["dashboard.blueprint"].create(
            {
                "name": "Host Users",
                "key": "test_share_host_b_%s" % self.env.uid,
                "host_model_id": user_model.id,
            }
        )
        with self.assertRaises(ValidationError):
            a.share_link_ids = [(4, b.id)]

    def test_share_transitive_three_blueprints(self):
        host = self._host_model()
        a, b, c = self.env["dashboard.blueprint"].create(
            [
                {
                    "name": "T A",
                    "key": "test_share_t_a_%s" % self.env.uid,
                    "host_model_id": host.id,
                },
                {
                    "name": "T B",
                    "key": "test_share_t_b_%s" % self.env.uid,
                    "host_model_id": host.id,
                },
                {
                    "name": "T C",
                    "key": "test_share_t_c_%s" % self.env.uid,
                    "host_model_id": host.id,
                },
            ]
        )
        self.env["dashboard.blueprint.slot"].create(
            {
                "blueprint_id": c.id,
                "key": "kpi_c",
                "name": "KPI C",
                "section": "menu_views",
                "label": "C",
                "show_if_zero": True,
                "action_model": "res.partner",
            }
        )
        a.share_link_ids = [(4, b.id)]
        b.share_link_ids = [(4, c.id)]
        self.assertIn("kpi_c", a._effective_slots().mapped("key"))
        self.assertIn(c, a._share_component())

    def test_share_pools_graph_variants_always(self):
        """Share Links always pool Chart Model Options into the gear picker."""
        host = self._host_model()
        a = self.env["dashboard.blueprint"].create(
            {
                "name": "Graph Share A",
                "key": "test_graph_share_a_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 10,
            }
        )
        b = self.env["dashboard.blueprint"].create(
            {
                "name": "Graph Share B",
                "key": "test_graph_share_b_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 20,
            }
        )
        Variant = self.env["dashboard.blueprint.graph.variant"]
        va = Variant.create(
            {
                "blueprint_id": a.id,
                "sequence": 10,
                "graph_model": "res.users",
                "graph_data_field": "partner_id",
                "primary_button_label": "Users",
                "primary_action_xmlid": "base.action_res_users",
                "is_default": True,
            }
        )
        vb = Variant.create(
            {
                "blueprint_id": b.id,
                "sequence": 10,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "primary_button_label": "Contacts",
                "primary_action_xmlid": "base.action_partner_form",
                "is_default": True,
            }
        )
        self.assertTrue(va._is_valid_candidate())
        self.assertTrue(vb._is_valid_candidate())
        a.share_link_ids = [(4, b.id)]
        eff_a = a._effective_graph_variants()
        eff_b = b._effective_graph_variants()
        self.assertEqual(set(eff_a.ids), {va.id, vb.id})
        self.assertEqual(set(eff_b.ids), {va.id, vb.id})
        # Local first, then peers — A sees its Users option before Contacts.
        self.assertEqual(eff_a[0], va)
        self.assertEqual(eff_b[0], vb)
        models_a = {row["graph_model"] for row in a._graph_model_candidates()}
        self.assertEqual(models_a, {"res.users", "res.partner"})
        # Default stays local even after pooling.
        self.assertEqual(a._default_graph_variant(), va)
        self.assertEqual(b._default_graph_variant(), vb)
        # Gear preference may pick a peer option; effective chart follows.
        pref = a._get_or_create_pref()
        pref.write({"preferred_graph_variant_id": vb.id})
        self.assertEqual(a._effective_graph_variant(), vb)
        # Studio edit list stays local-only.
        local_only = a.with_context(
            dashboard_studio_local_only=True
        )._effective_graph_variants()
        self.assertEqual(local_only, va)

    def test_share_graph_hub_loses_dedupe_to_pack(self):
        """*360 hubs lose same-model dedupe to pack dashboards."""
        host = self._host_model()
        pack = self.env["dashboard.blueprint"].create(
            {
                "name": "Pack Customers",
                "key": "test_pack_customers_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 20,
            }
        )
        hub = self.env["dashboard.blueprint"].create(
            {
                "name": "Hub 360",
                "key": "test_hub_360_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 5,
            }
        )
        Variant = self.env["dashboard.blueprint.graph.variant"]
        pack_v = Variant.create(
            {
                "blueprint_id": pack.id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "primary_button_label": "From Pack",
                "primary_action_xmlid": "base.action_partner_form",
                "is_default": True,
            }
        )
        Variant.create(
            {
                "blueprint_id": hub.id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "primary_button_label": "From Hub",
                "primary_action_xmlid": "base.action_partner_form",
                "is_default": True,
            }
        )
        pack.share_link_ids = [(4, hub.id)]
        # Viewer on a third linked blueprint with no local option.
        viewer = self.env["dashboard.blueprint"].create(
            {
                "name": "Viewer",
                "key": "test_viewer_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 30,
            }
        )
        viewer.share_link_ids = [(4, pack.id)]
        eff = viewer._effective_graph_variants()
        self.assertEqual(eff, pack_v)
        self.assertEqual(eff.blueprint_id, pack)

    def test_hub_pooled_default_shared_option(self):
        """360 hub can set Default on a Share Links peer without touching the pack."""
        host = self._host_model()
        pack_a = self.env["dashboard.blueprint"].create(
            {
                "name": "Pack A CRM",
                "key": "test_pack_a_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 10,
            }
        )
        pack_b = self.env["dashboard.blueprint"].create(
            {
                "name": "Pack B Sales",
                "key": "test_pack_b_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 20,
            }
        )
        hub = self.env["dashboard.blueprint"].create(
            {
                "name": "Customer 360",
                "key": "test_customer_360_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 5,
            }
        )
        Variant = self.env["dashboard.blueprint.graph.variant"]
        va = Variant.create(
            {
                "blueprint_id": pack_a.id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "primary_button_label": "Contacts",
                "primary_action_xmlid": "base.action_partner_form",
                "is_default": True,
            }
        )
        vb = Variant.create(
            {
                "blueprint_id": pack_b.id,
                "graph_model": "res.users",
                "graph_data_field": "partner_id",
                "primary_button_label": "Users",
                "primary_action_xmlid": "base.action_res_users",
                "is_default": True,
            }
        )
        hub.share_link_ids = [(4, pack_a.id), (4, pack_b.id)]
        # No hub pick yet → first valid pooled peer.
        self.assertEqual(hub._default_graph_variant(), va)
        # Hub Default on shared Sales option — pack Defaults unchanged.
        payload = hub.studio_set_default_graph_variant(vb.id)
        self.assertEqual(hub.pooled_default_graph_variant_id, vb)
        self.assertEqual(hub._default_graph_variant(), vb)
        self.assertTrue(va.is_default)
        self.assertTrue(vb.is_default)
        self.assertEqual(pack_a._default_graph_variant(), va)
        self.assertEqual(pack_b._default_graph_variant(), vb)
        default_rows = [r for r in payload["graph_variants"] if r["is_default"]]
        self.assertEqual(len(default_rows), 1)
        self.assertEqual(default_rows[0]["id"], vb.id)
        self.assertFalse(default_rows[0]["owned"])

    def test_share_graph_variant_dedupe_prefers_current(self):
        """Same graph_model across Share Links: current blueprint wins."""
        host = self._host_model()
        a = self.env["dashboard.blueprint"].create(
            {
                "name": "Graph Dedupe A",
                "key": "test_graph_dedupe_a_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 10,
            }
        )
        b = self.env["dashboard.blueprint"].create(
            {
                "name": "Graph Dedupe B",
                "key": "test_graph_dedupe_b_%s" % self.env.uid,
                "host_model_id": host.id,
                "sequence": 20,
            }
        )
        Variant = self.env["dashboard.blueprint.graph.variant"]
        va = Variant.create(
            {
                "blueprint_id": a.id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "primary_button_label": "From A",
                "primary_action_xmlid": "base.action_partner_form",
                "is_default": True,
            }
        )
        vb = Variant.create(
            {
                "blueprint_id": b.id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "primary_button_label": "From B",
                "primary_action_xmlid": "base.action_partner_form",
                "is_default": True,
            }
        )
        a.share_link_ids = [(4, b.id)]
        self.assertEqual(a._effective_graph_variants(), va)
        self.assertEqual(b._effective_graph_variants(), vb)

    def test_seeded_invoice_customers_slots_exist(self):
        if not self.env["ir.module.module"].search(
            [
                ("name", "=", "invoice_customer_dashboard"),
                ("state", "=", "installed"),
            ]
        ):
            self.skipTest("invoice_customer_dashboard not installed")
        bp = self.env.ref(
            "invoice_customer_dashboard.blueprint_invoice_customers"
        )
        keys = set(bp.slot_ids.mapped("key"))
        for key in (
            "open_invoices",
            "overdue_invoices",
            "box_total_due",
            "view_invoices",
            "new_invoice",
        ):
            self.assertIn(key, keys)
        overdue = bp.slot_ids.filtered(lambda s: s.key == "overdue_invoices")
        self.assertEqual(overdue.style, "danger")
        self.assertEqual(overdue.style_mode, "when_positive")

    def test_compose_hub_star_keeps_packs_standalone(self):
        host = self._host_model()
        pack_a, pack_b, hub = self.env["dashboard.blueprint"].create(
            [
                {
                    "name": "Pack A",
                    "key": "test_star_pack_a_%s" % self.env.uid,
                    "host_model_id": host.id,
                    "sequence": 10,
                },
                {
                    "name": "Pack B",
                    "key": "test_star_pack_b_%s" % self.env.uid,
                    "host_model_id": host.id,
                    "sequence": 20,
                },
                {
                    "name": "Hub 360",
                    "key": "test_star_hub_360_%s" % self.env.uid,
                    "host_model_id": host.id,
                    "sequence": 5,
                    "is_compose_hub": True,
                },
            ]
        )
        self.env["dashboard.blueprint.slot"].create(
            {
                "blueprint_id": pack_b.id,
                "key": "kpi_from_b",
                "name": "From B",
                "section": "kpi",
                "label": "From B",
                "show_if_zero": True,
                "action_model": "res.partner",
            }
        )
        hub.share_link_ids = [(6, 0, [pack_a.id, pack_b.id])]
        self.assertIn("kpi_from_b", hub._effective_slots().mapped("key"))
        self.assertNotIn("kpi_from_b", pack_a._effective_slots().mapped("key"))
        self.assertNotIn(pack_b, pack_a._share_pool_members())

    def test_invoice_customers_joins_share_triangle(self):
        crm = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers",
            raise_if_not_found=False,
        )
        sale = self.env.ref(
            "sales_customer_dashboard.blueprint_sales_customers",
            raise_if_not_found=False,
        )
        inv = self.env.ref(
            "invoice_customer_dashboard.blueprint_invoice_customers",
            raise_if_not_found=False,
        )
        if not all((crm, sale, inv)):
            self.skipTest("partner customer packs incomplete")
        from odoo.addons.dashboard_engine.share_pools import (
            link_partner_customer_share_pool,
        )

        link_partner_customer_share_pool(self.env)
        self.assertNotIn(inv, crm.share_link_ids)
        self.assertNotIn(sale, crm.share_link_ids)
        self.assertNotIn("open_invoices", crm._effective_slots().mapped("key"))
        hub = self.env.ref(
            "customer_360_dashboard.blueprint_customer_360",
            raise_if_not_found=False,
        )
        if hub:
            self.assertIn(inv, hub.share_link_ids)
            self.assertIn("open_invoices", hub._effective_slots().mapped("key"))

    def test_seeded_customer_360_attention_and_share(self):
        if not self.env["ir.module.module"].search(
            [
                ("name", "=", "customer_360_dashboard"),
                ("state", "=", "installed"),
            ]
        ):
            self.skipTest("customer_360_dashboard not installed")
        bp = self.env.ref("customer_360_dashboard.blueprint_customer_360")
        self.env["dashboard.blueprint"]._attach_compose_hubs_to_360_app()
        bp.invalidate_recordset(["is_compose_hub", "group_id", "hub_id"])
        self.assertTrue(bp.lens_attention_enabled)
        self.assertTrue(bp.is_compose_hub)
        self.assertFalse(bp.group_id)
        self.assertEqual(
            bp.hub_id,
            self.env.ref("dashboard_engine.dashboard_hub_default"),
        )
        self.assertTrue(bp.lens_attention_default)
        self.assertEqual(bp.lens_attention_label, "Needs attention")
        crm = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers",
            raise_if_not_found=False,
        )
        if not crm:
            self.skipTest("crm_customer_dashboard not installed")
        self.assertIn(bp, crm.share_link_ids)
        self.assertIn(crm, bp.share_link_ids)
        overdue = crm.slot_ids.filtered(lambda s: s.key == "overdue_opportunities")
        self.assertTrue(overdue.is_attention_signal)
        self.assertIn(
            "overdue_opportunities", bp._effective_slots().mapped("key")
        )
        self.assertFalse(
            bp.scope_ids.filtered(
                lambda s: s.name in ("Pipeline", "Leads", "My Pipeline")
            )
        )
        names = set(bp._runtime_scopes().mapped("name"))
        self.assertIn("Pipeline", names)
        self.assertIn("Leads", names)
        self.assertIn("My Pipeline", names)
        self.assertIn(
            self.env.ref("crm_customer_dashboard.scope_crm_pipeline"),
            bp._runtime_scopes(),
        )
