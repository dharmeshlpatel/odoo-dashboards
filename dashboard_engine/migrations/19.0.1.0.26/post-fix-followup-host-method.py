# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Switch due/overdue slots from the obsolete follow-up client tag to the host method.

``account_followup.action_account_followup`` still uses tag
``account_report_followup``, which is not registered in Odoo 19 (reports use
``account_report``). Calling ``res.partner.open_follow_up_report`` opens the
correct report with partner params — same as v1.
"""
from odoo import api, SUPERUSER_ID


SLOT_KEYS = ("box_total_due", "box_total_overdue")
BLUEPRINT_KEYS = ("crm_customers", "sales_customers")


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Slot = env["dashboard.blueprint.slot"]
    slots = Slot.search(
        [
            ("blueprint_id.key", "in", list(BLUEPRINT_KEYS)),
            ("key", "in", list(SLOT_KEYS)),
        ]
    )
    if slots:
        slots.write(
            {
                "action_method": "open_follow_up_report",
                "action_xmlid": False,
                "action_context": "{}",
                "module_depends": "account_followup,account_reports",
            }
        )
