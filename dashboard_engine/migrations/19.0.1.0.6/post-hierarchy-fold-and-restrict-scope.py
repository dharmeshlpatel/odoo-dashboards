# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Widen the remaining CRM KPI click-throughs to ``child_of`` on upgrade.

19.0.1.0.6 makes ``_apply_aggregate``/``_build_graph_payloads`` fold child
companies' data up into the parent card in Python whenever
``include_child_records`` is set (two fixed queries, independent of page size), so
KPI badges on ``blueprint_crm_customers`` now count child-linked leads and
opportunities too. Their click-through domains are updated here to match,
the same way 19.0.1.0.5 already did for the two menu-only slots. New
installs get the widened value straight from the seed data; this script
only patches existing noupdate="1" rows.
"""
from odoo import api, SUPERUSER_ID

OLD_TO_NEW = {
    "dashboard_engine.slot_crm_open_opportunities": (
        "[('type', '=', 'opportunity'), ('probability', '<', 100), "
        "('active', '=', True), ('partner_id', '=', '{{id}}')]",
        "[('type', '=', 'opportunity'), ('probability', '<', 100), "
        "('active', '=', True), ('partner_id', 'child_of', '{{id}}')]",
    ),
    "dashboard_engine.slot_crm_overdue_opportunities": (
        "[('partner_id', '=', '{{id}}')]",
        "[('partner_id', 'child_of', '{{id}}')]",
    ),
    "dashboard_engine.slot_crm_bottom_opportunities": (
        "[('partner_id', '=', '{{id}}')]",
        "[('partner_id', 'child_of', '{{id}}')]",
    ),
    "dashboard_engine.slot_crm_unassigned": (
        "[('partner_id', '=', '{{id}}')]",
        "[('partner_id', 'child_of', '{{id}}')]",
    ),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, (old_domain, new_domain) in OLD_TO_NEW.items():
        slot = env.ref(xmlid, raise_if_not_found=False)
        if slot and slot.action_domain == old_domain:
            slot.action_domain = new_domain
