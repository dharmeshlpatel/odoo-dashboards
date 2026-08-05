# -*- coding: utf-8 -*-
"""Phase 0–2: viewer My, lens parity, scope targets, panel pack."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPanelFiltersLinkedMy(TransactionCase):
    def _partner_model(self):
        return self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def test_lens_kpis_uses_full_effective_domain(self):
        """With KPIs must honour pref include/period/custom, not bare graph_domain."""
        parent = self.env["res.partner"].create({"name": "Lens Full Parent"})
        matching = self.env["res.partner"].create(
            {
                "name": "Lens Full Match",
                "parent_id": parent.id,
                "user_id": self.env.uid,
            }
        )
        other = self.env["res.partner"].create(
            {
                "name": "Lens Full Other",
                "parent_id": parent.id,
            }
        )
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Lens Full Domain",
                "key": "lens_full_domain_%s" % self.env.uid,
                "host_model_id": self._partner_model().id,
                "lens_kpis_enabled": True,
                "lens_kpis_label": "With KPIs",
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_domain": "[('id', 'in', (%s, %s))]"
                % (matching.id, other.id),
                "state": "draft",
            }
        )
        scope = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": bp.id,
                "name": "My",
                "mode": "restrict",
                "domain": "[('user_id', '=', uid)]",
                "default_on": False,
            }
        )
        # Without pref / My: both children → parent shows.
        self.assertIn(parent.id, bp._lens_kpis_host_ids())
        pref = bp._get_or_create_pref()
        pref.scope_ids = [(6, 0, [scope.id])]
        # With My: only matching child keeps parent in the lens set.
        ids = bp._lens_kpis_host_ids()
        self.assertIn(parent.id, ids)
        # Domain parity with chart settings.
        settings_domain = bp._effective_graph_settings()["domain"]
        self.assertTrue(
            any(
                isinstance(leaf, (list, tuple)) and leaf[0] == "user_id"
                for leaf in settings_domain
            )
        )

    def test_sale_label_requires_share_and_map(self):
        crm = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers",
            raise_if_not_found=False,
        )
        mine = self.env.ref(
            "crm_customer_dashboard.scope_crm_mine", raise_if_not_found=False
        )
        if not crm or not mine:
            self.skipTest("CRM Customers blueprint missing")
        # Ensure a sale map row exists (seed or heal).
        self.env["dashboard.blueprint"]._seed_crm_scope_target_defaults()
        sales = self.env.ref(
            "sales_customer_dashboard.blueprint_sales_customers",
            raise_if_not_found=False,
        )
        if not sales or "sale.order" not in self.env:
            self.skipTest("Sales Customers / sale.order missing")
        # Detach share links → label must stay plain My Pipeline.
        crm.write({"share_link_ids": [(5, 0, 0)]})
        self.env.cr.cache.pop("dashboard_scope_targets_all", None)
        presented = mine._presentation()
        self.assertNotIn("Sales", presented["name"])
        # Re-link → Sales wording allowed when map + peer exist.
        crm.write({"share_link_ids": [(6, 0, [sales.id])]})
        crm._auto_accept_scope_targets_for_share()
        self.env.cr.cache.pop("dashboard_scope_targets_all", None)
        self.assertTrue(
            crm._has_active_commercial_map("sale.order"),
            "expected sale.order map + Sales share peer after link",
        )
        presented = mine._presentation()
        self.assertIn("Sales", presented["name"])

    def test_viewer_my_on_borrowed_sales_kpi(self):
        """CRM My tick must narrow a shared Sales KPI via viewer prefs."""
        if "sale.order" not in self.env or "crm.lead" not in self.env:
            self.skipTest("crm/sale not installed")
        crm = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers",
            raise_if_not_found=False,
        )
        sales = self.env.ref(
            "sales_customer_dashboard.blueprint_sales_customers",
            raise_if_not_found=False,
        )
        mine = self.env.ref(
            "crm_customer_dashboard.scope_crm_mine", raise_if_not_found=False
        )
        if not crm or not sales or not mine:
            self.skipTest("CRM/Sales blueprints missing")
        crm.write({"share_link_ids": [(4, sales.id)]})
        crm._auto_accept_scope_targets_for_share()

        partner = self.env["res.partner"].create({"name": "Viewer My Partner"})
        other_user = self.env["res.users"].search(
            [("id", "!=", self.env.uid), ("share", "=", False)], limit=1
        )
        if not other_user:
            self.skipTest("Need a second internal user")
        Order = self.env["sale.order"]
        Order.create(
            {
                "partner_id": partner.id,
                "user_id": self.env.uid,
            }
        )
        Order.create(
            {
                "partner_id": partner.id,
                "user_id": other_user.id,
            }
        )
        sales_kpi = sales.slot_ids.filtered(
            lambda s: s.section == "kpi" and s.compute_model == "sale.order"
        )[:1]
        if not sales_kpi:
            self.skipTest("No Sales KPI slot on sale.order")

        pref = crm._get_or_create_pref()
        pref.scope_ids = [(6, 0, [mine.id])]
        slot = sales_kpi.with_context(dashboard_blueprint_key=crm.key)
        before_off = sales_kpi.with_context(
            dashboard_blueprint_key=crm.key
        )
        # With My on CRM: only current user's orders.
        count_mine = slot._compute_values_batch(partner).get(
            partner.id, (0, None)
        )[0]
        self.assertEqual(count_mine, 1)
        # Clear My → both orders.
        pref.scope_ids = [(5, 0, 0)]
        # Bust request cache for resolved targets.
        self.env.cr.cache.pop("dashboard_scope_targets", None)
        count_all = before_off._compute_values_batch(partner).get(
            partner.id, (0, None)
        )[0]
        self.assertEqual(count_all, 2)

    def test_unmapped_meetings_ignore_my(self):
        """Odd bottoms without map / panel_follow stay untouched by My."""
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Meetings Host",
                "key": "meetings_host_%s" % self.env.uid,
                "host_model_id": self._partner_model().id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "state": "draft",
            }
        )
        scope = self.env["dashboard.blueprint.scope"].create(
            {
                "blueprint_id": bp.id,
                "name": "My",
                "mode": "restrict",
                "domain": "[('user_id', '=', uid)]",
            }
        )
        # Fake "meetings" bottom on a model with user_id but no map.
        slot = self.env["dashboard.blueprint.slot"].create(
            {
                "blueprint_id": bp.id,
                "section": "bottom",
                "key": "fake_meetings",
                "name": "Meetings",
                "compute_model": "res.users",
                "relate_field": "partner_id",
                "compute_domain": "[]",
            }
        )
        pref = bp._get_or_create_pref()
        pref.scope_ids = [(6, 0, [scope.id])]
        self.assertFalse(slot.with_context(dashboard_blueprint_key=bp.key)._slot_follows_my())
        self.assertFalse(
            bp._restrict_scope_domain_for_model("res.users", section="bottom")
        )

    def test_mapped_period_uses_date_order(self):
        if "sale.order" not in self.env:
            self.skipTest("sale not installed")
        crm = self.env.ref(
            "crm_customer_dashboard.blueprint_crm_customers",
            raise_if_not_found=False,
        )
        mine = self.env.ref(
            "crm_customer_dashboard.scope_crm_mine", raise_if_not_found=False
        )
        if not crm or not mine:
            self.skipTest("CRM blueprint missing")
        self.env["dashboard.blueprint"]._seed_crm_scope_target_defaults()
        sales = self.env.ref(
            "sales_customer_dashboard.blueprint_sales_customers",
            raise_if_not_found=False,
        )
        if sales:
            crm.write({"share_link_ids": [(4, sales.id)]})
        pref = crm._get_or_create_pref()
        Year = self.env["period.year"]
        year = Year.search([], limit=1)
        if not year:
            self.skipTest("No period.year rows")
        pref.period_year_ids = [(6, 0, year.ids)]
        domain = pref._panel_period_domain_for_model("sale.order")
        self.assertTrue(
            any(
                isinstance(leaf, (list, tuple)) and leaf[0] == "date_order"
                for leaf in domain
            ),
            domain,
        )
