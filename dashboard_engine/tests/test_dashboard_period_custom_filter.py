# -*- coding: utf-8 -*-
"""Custom Filter from month/year picks: OR/AND, odd/even counts, both date rows."""
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval
from odoo import fields


def _polish_balance(domain):
    """Same counting rule as the OWL DomainSelector (normalizeDomainAST)."""
    expected = 1
    for item in domain:
        if item in ("&", "|"):
            expected += 1
        elif item == "!":
            continue
        elif isinstance(item, (list, tuple)) and len(item) == 3:
            expected -= 1
        else:
            return None
    return expected


@tagged("post_install", "-at_install", "dashboard_period_filter")
class TestDashboardPeriodCustomFilter(TransactionCase):
    def _host_model(self):
        return self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def _blueprint(self):
        return self.env["dashboard.blueprint"].create(
            {
                "name": "Period Custom Filter Cases",
                "key": "test_period_custom_filter_%s" % self.env.uid,
                "host_model_id": self._host_model().id,
                "graph_model": "res.partner",
                "graph_data_field": "parent_id",
                "graph_groupby": "create_date:month",
                "state": "published",
            }
        )

    def _assert_domain_char(self, char, fields_needed, label):
        self.assertTrue(char and char != "[]", "%s: Custom Filter is empty" % label)
        try:
            domain = list(safe_eval(char))
        except Exception as err:
            self.fail("%s: Custom Filter is not readable (%s): %s" % (label, err, char))
        self.assertTrue(domain, "%s: parsed domain is empty: %s" % (label, char))
        balance = _polish_balance(domain)
        self.assertEqual(
            balance,
            0,
            "%s: domain widget would reject this (balance=%s): %s"
            % (label, balance, char),
        )
        fields.Domain(domain)
        for fname in fields_needed:
            self.assertIn(fname, char, "%s: missing %s in %s" % (label, fname, char))

    def _payload_domain(self, payload):
        if isinstance(payload, dict):
            return payload.get("domain") or "[]"
        return payload or "[]"

    def test_custom_filter_or_and_all_period_combinations(self):
        Fields = self.env["ir.model.fields"]
        create_field = Fields.search(
            [("model", "=", "res.partner"), ("name", "=", "create_date")], limit=1
        )
        write_field = Fields.search(
            [("model", "=", "res.partner"), ("name", "=", "write_date")], limit=1
        )
        months = self.env["period.month.quarter"].search([])
        years = self.env["period.year"].search([])
        if not create_field or not write_field or len(months) < 3 or len(years) < 2:
            self.skipTest("Need create_date, write_date, 3 months, 2 years")

        bp = self._blueprint()
        bp.write(
            {
                "period_field_id": create_field.id,
                "closed_period_field_id": write_field.id,
            }
        )
        pref = bp._get_or_create_pref()
        pref.write(
            {
                "period_field_id": create_field.id,
                "period_closed_field_id": write_field.id,
            }
        )
        pref._sync_pref_period_lines()
        lines = pref.period_line_ids.sorted("sequence")
        self.assertGreaterEqual(len(lines), 2, "Need Created on and Closed Date rows")
        open_line, closed_line = lines[0], lines[1]

        cases = []
        for operator in ("any", "all"):
            for n_mq in (0, 1, 2, 3):
                for n_year in (0, 1, 2):
                    if not n_mq and not n_year:
                        continue
                    for both_fields in (False, True):
                        cases.append((operator, n_mq, n_year, both_fields))

        failures = []
        for operator, n_mq, n_year, both_fields in cases:
            mq_ids = months[:n_mq].ids
            year_ids = years[:n_year].ids
            open_name = open_line.field_name or "create_date"
            closed_name = closed_line.field_name or "write_date"
            picks = [
                {
                    "id": open_line.id,
                    "field_name": open_name,
                    "period_mq_ids": mq_ids,
                    "period_year_ids": year_ids,
                }
            ]
            needed = [open_name]
            if both_fields:
                picks.append(
                    {
                        "id": closed_line.id,
                        "field_name": closed_name,
                        "period_mq_ids": mq_ids,
                        "period_year_ids": year_ids,
                    }
                )
                needed.append(closed_name)
            label = "live op=%s months=%s years=%s fields=%s" % (
                operator,
                n_mq,
                n_year,
                "+".join(needed),
            )
            try:
                widget = pref.web_custom_filter_from_period_picks(picks, operator)
                self._assert_domain_char(self._payload_domain(widget), needed, label)
                self.assertTrue(
                    widget.get("ranges") if isinstance(widget, dict) else True,
                    "%s: missing range list for the gear widget" % label,
                )
            except AssertionError as err:
                failures.append(str(err))

        for operator, n_mq, n_year, both_fields in cases:
            mq_ids = months[:n_mq].ids
            year_ids = years[:n_year].ids
            open_line.with_context(skip_custom_filter_from_periods=True).write(
                {
                    "period_mq_ids": [(6, 0, mq_ids)],
                    "period_year_ids": [(6, 0, year_ids)],
                }
            )
            closed_vals = (
                {
                    "period_mq_ids": [(6, 0, mq_ids)],
                    "period_year_ids": [(6, 0, year_ids)],
                }
                if both_fields
                else {
                    "period_mq_ids": [(5, 0, 0)],
                    "period_year_ids": [(5, 0, 0)],
                }
            )
            closed_line.with_context(skip_custom_filter_from_periods=True).write(
                closed_vals
            )
            pref.with_context(skip_custom_filter_from_periods=True).write(
                {"period_operator": operator}
            )
            label = "saved op=%s months=%s years=%s both=%s" % (
                operator,
                n_mq,
                n_year,
                both_fields,
            )
            needed = [open_line.field_name or "create_date"]
            if both_fields:
                needed.append(closed_line.field_name or "write_date")
            try:
                domain = pref._period_domain()
                self.assertTrue(domain, "%s: query period domain is empty" % label)
                self.assertEqual(
                    _polish_balance(list(domain)),
                    0,
                    "%s: query domain is malformed: %s" % (label, domain),
                )
                fields.Domain(domain)
                widget = pref._custom_filter_char_from_periods()
                self._assert_domain_char(widget, needed, label)
            except AssertionError as err:
                failures.append(str(err))

        self.assertFalse(failures, "Failed cases:\n- " + "\n- ".join(failures))
