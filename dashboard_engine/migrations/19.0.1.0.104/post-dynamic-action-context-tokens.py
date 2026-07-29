# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Wire CRM action contexts to generic __de__ group_value tokens."""
from odoo import SUPERUSER_ID, api

DEFAULT_TYPE = (
    '{"default_type": {"__de__": "group_value", "default": "opportunity", '
    '"map": [{"groups": ["crm.group_use_lead"], "value": "lead"}]}}'
)
UNASSIGNED_CTX = (
    '{"search_default_unassigned_leads": 1, "default_type": '
    '{"__de__": "group_value", "default": "opportunity", '
    '"map": [{"groups": ["crm.group_use_lead"], "value": "lead"}]}}'
)
ACTIVITIES_CTX = (
    '{"graph_groupbys": ["date:month", "subtype_id", "partner_id"], '
    '"graph_measure": false, "graph_domain": [], '
    '"pivot_measures": [], "pivot_column_groupby": []}'
)

SLOT_UPDATES = {
    "crm_customer_dashboard.slot_crm_open_opportunities": {
        "action_context": DEFAULT_TYPE,
    },
    "crm_customer_dashboard.slot_crm_overdue_opportunities": {
        "action_context": DEFAULT_TYPE,
    },
    "crm_customer_dashboard.slot_crm_unassigned": {
        "action_context": UNASSIGNED_CTX,
    },
    "crm_customer_dashboard.slot_crm_menu_report_activities": {
        "action_context": ACTIVITIES_CTX,
    },
    # Legacy xmlids before preset reassignment
    "dashboard_engine.slot_crm_open_opportunities": {
        "action_context": DEFAULT_TYPE,
    },
    "dashboard_engine.slot_crm_overdue_opportunities": {
        "action_context": DEFAULT_TYPE,
    },
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    bp = env.ref(
        "crm_customer_dashboard.blueprint_crm_customers",
        raise_if_not_found=False,
    ) or env.ref(
        "dashboard_engine.blueprint_crm_customers",
        raise_if_not_found=False,
    )
    if bp:
        bp.write({"primary_action_context": DEFAULT_TYPE})
    seen = set()
    for xmlid, values in SLOT_UPDATES.items():
        slot = env.ref(xmlid, raise_if_not_found=False)
        if slot and slot.id not in seen:
            slot.write(values)
            seen.add(slot.id)
