# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Attach the overdue condition to the seeded CRM overdue slot.

The blueprint seed is noupdate, so databases installed before conditions
existed would keep the incomplete domain. Only slots that do not already
reference the condition are touched.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    condition = env.ref(
        "dashboard_engine.condition_crm_overdue_opportunity", raise_if_not_found=False
    )
    slot = env.ref(
        "dashboard_engine.slot_crm_overdue_opportunities", raise_if_not_found=False
    )
    if not condition or not slot:
        return
    if condition not in slot.condition_ids:
        slot.write(
            {
                "condition_ids": [(4, condition.id)],
                "compute_domain": "[]",
                "action_domain": "[('partner_id', '=', '{{id}}')]",
            }
        )
