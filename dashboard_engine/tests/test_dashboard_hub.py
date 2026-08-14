# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "dashboard_engine")
class TestDashboardHubGroups(TransactionCase):
    def test_group_model_and_link(self):
        hub = self.env.ref("dashboard_engine.dashboard_hub_default")
        group = self.env["dashboard.blueprint.group"].create({
            "name": "SALES",
            "sequence": 10,
            "hub_menu_id": hub.id,
        })
        Partner = self.env["ir.model"]._get("res.partner")
        bp = self.env["dashboard.blueprint"].create({
            "name": "Customer 360",
            "key": "hub_customer_360",
            "host_model_id": Partner.id,
            "state": "published",
            "group_id": group.id,
            "menu_sequence": 5,
        })
        self.assertEqual(group.dashboard_ids, bp)
        self.assertEqual(bp.group_id, group)
        self.assertEqual(group.hub_menu_id, hub)


@tagged("post_install", "-at_install", "dashboard_engine")
class TestDashboardHubApi(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Hub = cls.env["dashboard.blueprint.hub"]
        parent = cls.env.ref("dashboard_engine.menu_dashboard_engine_root")
        # Dedicated hubs so existing DB groups on the default hub cannot pollute asserts.
        cls.hub_sales = Hub.create({
            "name": "Test Sales Hub Menu",
            "menu_parent_id": parent.id,
            "menu_sequence": 90,
        })
        cls.hub_other = Hub.create({
            "name": "Test Other Hub Menu",
            "menu_parent_id": parent.id,
            "menu_sequence": 91,
        })
        Group = cls.env["dashboard.blueprint.group"]
        cls.g_sales = Group.create({
            "name": "TEST-SALES",
            "sequence": 10,
            "hub_menu_id": cls.hub_sales.id,
        })
        cls.g_crm = Group.create({
            "name": "TEST-CRM",
            "sequence": 20,
            "hub_menu_id": cls.hub_sales.id,
        })
        cls.g_other = Group.create({
            "name": "TEST-OTHER",
            "sequence": 5,
            "hub_menu_id": cls.hub_other.id,
        })
        partner_model = cls.env["ir.model"]._get("res.partner")
        vals = {
            "host_model_id": partner_model.id,
            "state": "published",
        }
        Blueprint = cls.env["dashboard.blueprint"]
        cls.bp_c360 = Blueprint.create({
            **vals,
            "name": "Customer 360",
            "key": "hub_c360",
            "group_id": cls.g_sales.id,
            "menu_sequence": 10,
        })
        cls.bp_p360 = Blueprint.create({
            **vals,
            "name": "Product 360",
            "key": "hub_p360",
            "group_id": cls.g_sales.id,
            "menu_sequence": 20,
        })
        cls.bp_crm = Blueprint.create({
            **vals,
            "name": "Customer",
            "key": "hub_crm_customer",
            "group_id": cls.g_crm.id,
            "menu_sequence": 10,
        })
        cls.bp_other = Blueprint.create({
            **vals,
            "name": "Other Dash",
            "key": "hub_other",
            "group_id": cls.g_other.id,
            "menu_sequence": 10,
        })
        cls.bp_orphan = Blueprint.create({
            **vals,
            "name": "Orphan",
            "key": "hub_orphan",
            "menu_sequence": 1,
        })
        cls.bp_draft = Blueprint.create({
            "host_model_id": partner_model.id,
            "state": "draft",
            "name": "Draft Hub",
            "key": "hub_draft",
            "group_id": cls.g_sales.id,
        })

    def _tree_pairs(self, tree):
        return [
            (group["name"], [dashboard["name"] for dashboard in group["dashboards"]])
            for group in tree
        ]

    def test_hub_tree_skips_ungrouped_and_draft(self):
        tree = self.env["dashboard.blueprint"].get_hub_tree(
            hub_menu_id=self.hub_sales.id
        )
        names = [
            dashboard["name"] for group in tree for dashboard in group["dashboards"]
        ]
        self.assertEqual(
            self._tree_pairs(tree),
            [
                ("TEST-SALES", ["Customer 360", "Product 360"]),
                ("TEST-CRM", ["Customer"]),
            ],
        )
        self.assertNotIn("Orphan", names)
        self.assertNotIn("Draft Hub", names)
        self.assertNotIn("Other Dash", names)

    def test_hub_tree_filters_by_shared_hub_menu(self):
        tree = self.env["dashboard.blueprint"].get_hub_tree(
            hub_menu_id=self.hub_sales.id
        )
        self.assertEqual(
            self._tree_pairs(tree),
            [
                ("TEST-SALES", ["Customer 360", "Product 360"]),
                ("TEST-CRM", ["Customer"]),
            ],
        )
        other_tree = self.env["dashboard.blueprint"].get_hub_tree(
            hub_menu_id=self.hub_other.id
        )
        self.assertEqual(
            self._tree_pairs(other_tree),
            [("TEST-OTHER", ["Other Dash"])],
        )

    def test_hub_tree_includes_action_id(self):
        self.bp_c360.action_publish()
        tree = self.env["dashboard.blueprint"].get_hub_tree(
            hub_menu_id=self.hub_sales.id
        )
        first = tree[0]["dashboards"][0]
        self.assertTrue(first["action_id"])
        self.assertEqual(first["id"], self.bp_c360.id)
        # Hub-only dashboards (group, no parent menu) do not get a standalone menu.
        self.assertTrue(
            not self.bp_c360.generated_menu_id or not self.bp_c360.generated_menu_id.active
        )

    def test_installed_crm_pack_stays_off_dashboards_360_list(self):
        crm = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers",
            raise_if_not_found=False,
        )
        if not crm:
            self.skipTest("crm_customer_dashboard not installed")
        from odoo.addons.dashboard_engine.share_pools import (
            link_partner_customer_share_pool,
        )

        link_partner_customer_share_pool(self.env)
        hub_menu = self.env.ref("dashboard_engine.dashboard_hub_default")
        self.assertFalse(crm.group_id)
        tree = self.env["dashboard.blueprint"].get_hub_tree(
            hub_menu_id=hub_menu.id
        )
        names = [
            dash["name"] for grp in tree for dash in grp["dashboards"]
        ]
        self.assertNotIn(crm.menu_name or crm.name, names)
        c360 = self.env.ref(
            "customer_360_dashboard.blueprint_customer_360",
            raise_if_not_found=False,
        )
        if c360:
            self.assertFalse(c360.group_id)
            self.assertEqual(c360.hub_id, hub_menu)
            self.assertIn(c360.menu_name or c360.name, names)
            self.assertTrue(
                not c360.generated_menu_id or not c360.generated_menu_id.active
            )
            self.assertIn(crm, c360.share_link_ids)
            self.assertIn(c360, crm.share_link_ids)
            sale = self.env.ref(
                "sales_customer_dashboard.blueprint_sales_customers",
                raise_if_not_found=False,
            )
            if sale:
                self.assertNotIn(sale, crm.share_link_ids)
        crm.action_publish()
        self.assertTrue(crm.generated_menu_id)
        self.assertTrue(crm.generated_menu_id.active)

    def test_standalone_menu_only_with_parent_and_no_group(self):
        parent = self.env.ref("dashboard_engine.menu_dashboard_engine_root")
        self.bp_orphan.write({"menu_parent_id": parent.id, "menu_name": "Orphan Menu"})
        self.bp_orphan.action_publish()
        self.assertTrue(self.bp_orphan.generated_menu_id)
        self.assertTrue(self.bp_orphan.generated_menu_id.active)
        self.assertEqual(self.bp_orphan.generated_menu_id.parent_id, parent)

    def test_neither_group_nor_parent_means_no_menu(self):
        self.bp_orphan.action_publish()
        self.assertTrue(self.bp_orphan.generated_action_id)
        self.assertTrue(
            not self.bp_orphan.generated_menu_id or not self.bp_orphan.generated_menu_id.active
        )

    def test_last_opened_session_roundtrip(self):
        Blueprint = self.env["dashboard.blueprint"]
        session = {}
        Blueprint._hub_session_set_last_opened(
            session, self.env.company.id, self.bp_crm.id, hub_menu_id=self.hub_sales.id
        )
        self.assertEqual(
            Blueprint._hub_session_get_last_opened(
                session, self.env.company.id, hub_menu_id=self.hub_sales.id
            ),
            self.bp_crm.id,
        )
        gone = self.bp_crm.id
        self.bp_crm.unlink()
        resolved = Blueprint._hub_resolve_initial_blueprint_id(
            session, self.env.company.id, hub_menu_id=self.hub_sales.id
        )
        self.assertEqual(resolved, self.bp_c360.id)
        self.assertNotEqual(resolved, gone)

    def test_hub_generates_client_action_with_context(self):
        self.assertTrue(self.hub_sales.generated_action_id)
        self.assertEqual(self.hub_sales.generated_action_id.tag, "dashboard_engine.hub")
        self.assertIn(
            "hub_menu_id",
            self.hub_sales.generated_action_id.context or "",
        )
        self.assertTrue(self.hub_sales.generated_menu_id)
        self.assertEqual(
            self.hub_sales.generated_menu_id.parent_id,
            self.env.ref("dashboard_engine.menu_dashboard_engine_root"),
        )

    def test_compose_hub_does_not_create_standalone_menu(self):
        hub = self.env.ref("dashboard_engine.dashboard_hub_default")
        group = self.env.ref("dashboard_engine.dashboard_group_360")
        parent = hub.generated_menu_id
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "No Menu 360",
                "key": "test_no_menu_360_%s" % self.env.uid,
                "host_model_id": self.env["ir.model"]._get("res.partner").id,
                "state": "published",
                "is_compose_hub": True,
                "group_id": group.id,
                "menu_parent_id": parent.id if parent else False,
                "menu_name": "No Menu 360",
            }
        )
        bp.action_publish()
        self.assertTrue(
            not bp.generated_menu_id or not bp.generated_menu_id.active
        )
        self.assertFalse(bp.menu_parent_id)

    def test_default_hub_xml_menu(self):
        hub = self.env.ref("dashboard_engine.dashboard_hub_default")
        menu = self.env.ref("dashboard_engine.menu_dashboards_360")
        self.assertEqual(hub.generated_menu_id, menu)
        self.assertTrue(menu.active)
        self.assertFalse(menu.parent_id)
        self.assertEqual(menu.name, "Dashboards 360")
        group = self.env.ref("dashboard_engine.dashboard_group_360")
        self.assertEqual(group.hub_menu_id, hub)
