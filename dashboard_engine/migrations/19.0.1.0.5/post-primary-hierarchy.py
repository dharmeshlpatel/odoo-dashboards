# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Apply CRM primary-button hierarchy/label field updates on existing DBs.

New xmlids (the primary action variant, and the child_of action domains on
brand-new/changed slots) are created or overwritten by
data/seed_blueprints.xml and data/seed_crm_parity.xml on upgrade, since
those specific fields are set for the first time. This script only patches
existing blueprint/slot rows whose noupdate="1" seed values predate
19.0.1.0.5 and would otherwise keep the old flat behaviour.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    bp = env.ref(
        "dashboard_engine.blueprint_crm_customers", raise_if_not_found=False
    )
    if bp:
        vals = {}
        if not bp.include_child_records:
            vals["include_child_records"] = True
        scope = env.ref(
            "dashboard_engine.scope_crm_pipeline", raise_if_not_found=False
        )
        if scope and not bp.primary_label_alt_scope_id:
            vals["primary_label_alt_scope_id"] = scope.id
            vals["primary_label_alt"] = "Leads Analysis"
        if vals:
            bp.write(vals)

    old_domain = "[('partner_id', '=', '{{id}}')]"
    new_domain = "[('partner_id', 'child_of', '{{id}}')]"
    for xmlid in (
        "dashboard_engine.slot_crm_menu_opportunities",
        "dashboard_engine.slot_crm_menu_view_leads",
    ):
        slot = env.ref(xmlid, raise_if_not_found=False)
        if slot and slot.action_domain == old_domain:
            slot.action_domain = new_domain
