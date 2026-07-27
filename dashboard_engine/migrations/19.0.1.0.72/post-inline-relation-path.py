# -*- coding: utf-8 -*-
"""Copy legacy relation-path M2Os onto Char link fields."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Blueprint = env["dashboard.blueprint"].sudo()
    Slot = env["dashboard.blueprint.slot"].sudo()

    for bp in Blueprint.search([("graph_relation_path_id", "!=", False)]):
        path = bp.graph_relation_path_id
        if path and path.domain_field:
            bp.graph_data_field = path.domain_field
        bp.graph_relation_path_id = False

    for slot in Slot.search([("relation_path_id", "!=", False)]):
        path = slot.relation_path_id
        if path and path.domain_field:
            slot.relate_field = path.domain_field
        slot.relation_path_id = False
