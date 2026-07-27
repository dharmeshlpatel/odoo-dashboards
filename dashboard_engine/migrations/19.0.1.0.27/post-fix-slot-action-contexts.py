# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Align CRM KPI / bottom slot click-through context with v1 search defaults."""
from odoo import api, SUPERUSER_ID

UPDATES = {
    "dashboard_engine.slot_crm_open_opportunities": {
        "action_context": '{"default_type": "opportunity"}',
    },
    "dashboard_engine.slot_crm_overdue_opportunities": {
        "action_context": '{"default_type": "opportunity"}',
    },
    "dashboard_engine.slot_crm_bottom_opportunities": {
        "action_domain": (
            "[('partner_id', 'child_of', '{{id}}'), ('type', '=', 'opportunity')]"
        ),
        "action_context": (
            '{"search_default_partner_id": [{{id}}], '
            '"default_partner_id": {{id}}, '
            '"default_type": "opportunity"}'
        ),
    },
    "dashboard_engine.slot_crm_bottom_meetings": {
        "action_context": (
            '{"search_default_partner_ids": [{{id}}], '
            '"default_partner_ids": [{{id}}], '
            '"partner_id": {{id}}}'
        ),
    },
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, values in UPDATES.items():
        slot = env.ref(xmlid, raise_if_not_found=False)
        if slot:
            slot.write(values)
