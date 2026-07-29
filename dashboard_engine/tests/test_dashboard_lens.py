# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDashboardKanbanLens(TransactionCase):
    def _partner_model(self):
        return self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def test_lens_my_requires_label(self):
        with self.assertRaises(ValidationError):
            self.env["dashboard.blueprint"].create(
                {
                    "name": "Lens My No Label",
                    "key": "lens_my_no_label",
                    "host_model_id": self._partner_model().id,
                    "lens_my_enabled": True,
                    "lens_my_label": False,
                }
            )

    def test_lens_kpis_requires_label(self):
        with self.assertRaises(ValidationError):
            self.env["dashboard.blueprint"].create(
                {
                    "name": "Lens KPIs No Label",
                    "key": "lens_kpis_no_label",
                    "host_model_id": self._partner_model().id,
                    "lens_kpis_enabled": True,
                    "lens_kpis_label": False,
                }
            )

    def _product_template_model(self):
        return self.env["ir.model"].search(
            [("model", "=", "product.template")], limit=1
        )

    def _country_model(self):
        return self.env["ir.model"].search([("model", "=", "res.country")], limit=1)

    def test_lens_my_domain_on_partner_host(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Lens Users",
                "key": "lens_users_my",
                "host_model_id": self._partner_model().id,
                "lens_my_enabled": True,
                "lens_my_label": "My Users",
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
            }
        )
        self.assertTrue(bp._lens_can_resolve_my())
        self.assertEqual(bp._lens_my_domain(), [("user_id", "=", self.env.uid)])

    def test_lens_my_domain_indirect_via_graph(self):
        country = self.env["res.country"].search([], limit=1)
        self.env["res.partner"].create(
            {
                "name": "Lens My Partner",
                "user_id": self.env.uid,
                "country_id": country.id,
            }
        )
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Lens Indirect My",
                "key": "lens_my_indirect",
                "host_model_id": self._country_model().id,
                "lens_my_enabled": True,
                "lens_my_label": "My Countries",
                "graph_model": "res.partner",
                "graph_data_field": "country_id",
            }
        )
        self.assertTrue(bp._lens_can_resolve_my())
        self.assertEqual(
            bp._lens_my_domain(), [("id", "in", [country.id])]
        )
        bp_empty = self.env["dashboard.blueprint"].create(
            {
                "name": "Lens Indirect My Empty",
                "key": "lens_my_indirect_empty",
                "host_model_id": self._country_model().id,
                "lens_my_enabled": True,
                "lens_my_label": "My Countries",
                "graph_model": "res.partner",
                "graph_data_field": "country_id",
                "graph_domain": "[('id', '=', 0)]",
            }
        )
        self.assertEqual(bp_empty._lens_my_domain(), [("id", "=", False)])

    def test_lens_my_health_when_unresolvable(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Lens My Bad",
                "key": "lens_my_unresolvable",
                "host_model_id": self._product_template_model().id,
                "lens_my_enabled": True,
                "lens_my_label": "My",
            }
        )
        self.assertFalse(bp._lens_can_resolve_my())
        self.assertIn(
            "My filter cannot resolve for this host/graph.",
            bp._health_issues(),
        )

    def test_lens_kpis_host_ids_from_graph(self):
        parent = self.env["res.partner"].create({"name": "Lens Parent"})
        child = self.env["res.partner"].create(
            {"name": "Lens Child", "parent_id": parent.id}
        )
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Lens KPI Graph",
                "key": "lens_kpi_graph",
                "host_model_id": self._partner_model().id,
                "lens_kpis_enabled": True,
                "lens_kpis_label": "With KPIs",
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_domain": f"[('id', '=', {child.id})]",
            }
        )
        ids = bp._lens_kpis_host_ids()
        self.assertIn(parent.id, ids)

    def test_search_rewrites_lens_flags(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Lens Rewrite",
                "user_id": self.env.user.id,
            }
        )
        # Graph row must carry user_id so My ∩ With KPIs extra_domain matches.
        child = self.env["res.partner"].create(
            {
                "name": "Lens Rewrite Child",
                "parent_id": partner.id,
                "user_id": self.env.user.id,
            }
        )
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Lens Rewrite BP",
                "key": "lens_rewrite_bp",
                "host_model_id": self._partner_model().id,
                "lens_my_enabled": True,
                "lens_my_label": "My Partners",
                "lens_kpis_enabled": True,
                "lens_kpis_label": "With KPIs",
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_domain": f"[('id', '=', {child.id})]",
                "state": "published",
            }
        )
        Partner = self.env["res.partner"].with_context(
            dashboard_blueprint_key=bp.key,
            initializer=bp.key,
            dashboard_rendering=True,
        )
        found = Partner.search([("dashboard_my_data", "=", True)])
        self.assertIn(partner.id, found.ids)
        found2 = Partner.search(
            [("dashboard_with_kpis", "=", True), ("id", "=", partner.id)]
        )
        self.assertIn(partner.id, found2.ids)
        # Both flags: My ∩ With KPIs — still rewrites (no SQL on virtual cols)
        found3 = Partner.search(
            [
                ("dashboard_my_data", "=", True),
                ("dashboard_with_kpis", "=", True),
                ("id", "=", partner.id),
            ]
        )
        self.assertIn(partner.id, found3.ids)

    def test_search_without_dashboard_context_unchanged(self):
        partner = self.env["res.partner"].create(
            {"name": "Lens Plain Search Partner"}
        )
        found = self.env["res.partner"].search(
            [("name", "=", "Lens Plain Search Partner")]
        )
        self.assertIn(partner.id, found.ids)
        # Virtual lens fields must not be real SQL columns
        self.assertFalse(
            self.env["res.partner"]._fields["dashboard_my_data"].store
        )
        self.assertFalse(
            self.env["res.partner"]._fields["dashboard_with_kpis"].store
        )

    def test_publish_wires_lens_context_and_search(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Lens Publish",
                "key": "lens_publish_bp",
                "host_model_id": self._partner_model().id,
                "menu_name": "Lens Publish",
                "lens_my_enabled": True,
                "lens_my_default": True,
                "lens_my_label": "My Partners",
                "lens_kpis_enabled": True,
                "lens_kpis_default": True,
                "lens_kpis_label": "With KPIs",
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "state": "draft",
            }
        )
        bp.action_publish()
        action = bp.generated_action_id
        ctx = action.context
        if isinstance(ctx, str):
            from odoo.tools.safe_eval import safe_eval

            ctx = safe_eval(ctx)
        self.assertTrue(ctx.get("show_dashboard_my_filter"))
        self.assertTrue(ctx.get("show_dashboard_kpis_filter"))
        self.assertTrue(ctx.get("search_default_dashboard_my_data"))
        self.assertTrue(ctx.get("search_default_dashboard_with_kpis"))
        self.assertEqual(action.search_view_id, bp.generated_search_view_id)
        arch = bp.generated_search_view_id.arch_db or bp.generated_search_view_id.arch
        self.assertIn("My Partners", arch)
        self.assertIn("With KPIs", arch)
        self.assertIn("dashboard_my_data", arch)
        self.assertIn("dashboard_with_kpis", arch)
        self.assertIn("show_dashboard_my_filter", arch)
        self.assertIn("show_dashboard_kpis_filter", arch)

    def test_lens_attention_requires_label(self):
        with self.assertRaises(ValidationError):
            self.env["dashboard.blueprint"].create(
                {
                    "name": "Lens Attention No Label",
                    "key": "lens_attention_no_label",
                    "host_model_id": self._partner_model().id,
                    "lens_attention_enabled": True,
                    "lens_attention_label": False,
                }
            )

    def test_lens_attention_host_ids_from_slot(self):
        hot = self.env["res.partner"].create({"name": "Attention Hot"})
        cold = self.env["res.partner"].create({"name": "Attention Cold"})
        self.env["res.partner"].create(
            {"name": "Attention Hot Child", "parent_id": hot.id}
        )
        # Use child count via graph-like relate on partner.parent_id as
        # attention signal: hosts that have at least one child.
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Lens Attention BP",
                "key": "lens_attention_bp",
                "host_model_id": self._partner_model().id,
                "lens_attention_enabled": True,
                "lens_attention_label": "Needs attention",
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
            }
        )
        self.env["dashboard.blueprint.slot"].create(
            {
                "blueprint_id": bp.id,
                "key": "attention_children",
                "name": "Children",
                "section": "kpi",
                "label": "Child",
                "is_attention_signal": True,
                "compute_model": "res.partner",
                "relate_field": "parent_id",
                "compute_domain": "[]",
                "compute_aggregator": "__count",
            }
        )
        ids = bp._lens_attention_host_ids()
        self.assertIn(hot.id, ids)
        self.assertNotIn(cold.id, ids)

        Partner = self.env["res.partner"].with_context(
            dashboard_blueprint_key=bp.key,
            initializer=bp.key,
            dashboard_rendering=True,
        )
        found = Partner.search([("dashboard_needs_attention", "=", True)])
        self.assertIn(hot.id, found.ids)
        self.assertNotIn(cold.id, found.ids)

    def test_publish_wires_attention_lens(self):
        bp = self.env["dashboard.blueprint"].create(
            {
                "name": "Lens Attention Publish",
                "key": "lens_attention_publish",
                "host_model_id": self._partner_model().id,
                "menu_name": "Lens Attention Publish",
                "lens_attention_enabled": True,
                "lens_attention_default": True,
                "lens_attention_label": "Needs attention",
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "state": "draft",
            }
        )
        bp.action_publish()
        action = bp.generated_action_id
        ctx = action.context
        if isinstance(ctx, str):
            from odoo.tools.safe_eval import safe_eval

            ctx = safe_eval(ctx)
        self.assertTrue(ctx.get("show_dashboard_attention_filter"))
        self.assertTrue(ctx.get("search_default_dashboard_needs_attention"))
        arch = bp.generated_search_view_id.arch_db or bp.generated_search_view_id.arch
        self.assertIn("Needs attention", arch)
        self.assertIn("dashboard_needs_attention", arch)
