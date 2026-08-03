# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "dashboard_engine")
class TestDashboardPrefCompany(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Hub Pref Co B"})
        cls.user = cls.env.ref("base.user_admin")
        cls.user.write({
            "company_ids": [(4, cls.company_b.id)],
            "company_id": cls.company_a.id,
        })
        Partner = cls.env["ir.model"]._get("res.partner")
        cls.bp = cls.env["dashboard.blueprint"].create({
            "name": "Pref Co Test",
            "key": "pref_co_test",
            "host_model_id": Partner.id,
            "state": "published",
        })

    def test_prefs_are_split_by_company(self):
        bp_a = self.bp.with_user(self.user).with_company(self.company_a)
        pref_a = bp_a._get_or_create_pref()
        self.assertEqual(pref_a.company_id, self.company_a)
        measure = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "credit_limit")], limit=1
        )
        pref_a.write({"measure_field_id": measure.id, "measure_aggregator": "avg"})

        bp_b = self.bp.with_user(self.user).with_company(self.company_b)
        self.assertFalse(bp_b._current_pref())
        pref_b = bp_b._get_or_create_pref()
        self.assertEqual(pref_b.company_id, self.company_b)
        self.assertNotEqual(pref_a.id, pref_b.id)
        self.assertFalse(pref_b.measure_field_id)

    def test_legacy_row_without_company_is_not_matched(self):
        """Rows with company_id=False must not satisfy _current_pref after the change."""
        Pref = self.env["dashboard.user.pref"].sudo()
        cr = self.env.cr
        cr.execute(
            "ALTER TABLE dashboard_user_pref ALTER COLUMN company_id DROP NOT NULL"
        )
        try:
            cr.execute(
                """
                INSERT INTO dashboard_user_pref
                    (user_id, blueprint_id, company_id, create_uid, write_uid,
                     create_date, write_date, custom_filter, period_operator)
                VALUES (%s, %s, NULL, %s, %s, NOW() AT TIME ZONE 'UTC',
                        NOW() AT TIME ZONE 'UTC', '[]', 'any')
                RETURNING id
                """,
                (self.user.id, self.bp.id, self.env.uid, self.env.uid),
            )
            orphan = Pref.browse(cr.fetchone()[0])
            bp_a = self.bp.with_user(self.user).with_company(self.company_a)
            self.assertFalse(bp_a._current_pref())
            self.assertTrue(orphan.exists())
        finally:
            cr.execute(
                "DELETE FROM dashboard_user_pref WHERE company_id IS NULL"
            )
            cr.execute(
                "ALTER TABLE dashboard_user_pref "
                "ALTER COLUMN company_id SET NOT NULL"
            )
