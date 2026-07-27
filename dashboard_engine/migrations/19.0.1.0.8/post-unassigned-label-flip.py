# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Apply Unassigned Lead/Opportunity label flip on existing CRM slots.

noupdate="1" seeds do not refresh labels on upgrade; this patches the
pre-19.0.1.0.8 neutral "Unassigned" wording to match v1 (Opportunity by
default, Lead when the viewer has crm.group_use_lead).
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    slot = env.ref(
        "dashboard_engine.slot_crm_unassigned", raise_if_not_found=False
    )
    if not slot:
        return
    vals = {}
    if slot.label in (False, "Unassigned"):
        vals["label"] = "Unassigned Opportunity"
        vals["label_plural"] = "Unassigned Opportunities"
    if not slot.label_alt:
        vals["label_alt"] = "Unassigned Lead"
        vals["label_plural_alt"] = "Unassigned Leads"
    if not slot.label_alt_groups_xmlids:
        vals["label_alt_groups_xmlids"] = "crm.group_use_lead"
    if vals:
        slot.write(vals)
