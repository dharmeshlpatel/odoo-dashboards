# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Wave 3: mark attention-signal slots on partner-customer packs."""
from odoo import SUPERUSER_ID, api

ATTENTION_SLOT_KEYS = (
    "overdue_opportunities",
    "to_invoice",
    "box_total_overdue",
    "overdue_invoices",
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Slot = env["dashboard.blueprint.slot"].sudo()
    slots = Slot.search([("key", "in", list(ATTENTION_SLOT_KEYS))])
    if slots:
        slots.write({"is_attention_signal": True})
