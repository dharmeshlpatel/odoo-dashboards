# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Phase 12 — export/import a blueprint as a portable JSON template.

Every configuration model in this engine already keeps its real value on a
plain technical field (Char/Selection/…) and exposes Many2one/Many2many
*pickers* computed from it (see ``dashboard_mirror.py``). Database ids mean
nothing in another database, so a template is just the technical side of
every model in the blueprint's tree, plus the handful of fields that are
themselves the source of truth on a database id (``host_model_id``,
``graph_groupby_extra_ids``, ``closed_period_field_id``) exported by name and
re-resolved on import — the same trick ``_mirror_model``/``_mirror_field``
already do for every picker.

A template always imports as a new **draft** blueprint. Nothing here ever
touches an existing blueprint's data; the person importing reviews and
publishes it themselves.
"""
import base64
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TEMPLATE_MARKER = "dashboard_engine.blueprint_template"


class DashboardBlueprint(models.Model):
    _inherit = "dashboard.blueprint"

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def action_export_template(self):
        """Download this blueprint as a portable ``.json`` template."""
        self.ensure_one()
        data = self._export_template()
        attachment = self.env["ir.attachment"].create(
            {
                "name": "%s.dashboard.json" % (self.key or "blueprint"),
                "type": "binary",
                "raw": json.dumps(data, indent=2, default=str).encode(),
                "mimetype": "application/json",
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }

    def _export_template(self):
        self.ensure_one()
        vals = self._portable_vals(exclude={"key", "state"})
        # Meaningless on another database: ids of local ir.model.fields
        # rows. The name list below carries the same information portably.
        vals.pop("ordered_graph_groupby_extra_ids", None)
        engine_module = self.env["ir.module.module"].sudo().search(
            [("name", "=", "dashboard_engine")], limit=1
        )
        return {
            "marker": TEMPLATE_MARKER,
            "engine_version": engine_module.installed_version or False,
            "key": self.key,
            "blueprint": vals,
            "graph_groupby_extra_fields": [
                f.name for f in self._ordered_groupby_extra_fields()
            ],
            "period_field_name": self.period_field_id.name or False,
            "closed_period_field_name": self.closed_period_field_id.name or False,
            "graph_relation_path": (
                # Legacy key for older importers; Char is already in blueprint vals.
                self.graph_data_field
                or (
                    self.graph_relation_path_id.domain_field
                    if self.graph_relation_path_id
                    else False
                )
            ),
            "primary_label_alt_scope_name": self.primary_label_alt_scope_id.name
            or False,
            "scopes": [
                {
                    **s._portable_vals(),
                    "labels": [
                        label._portable_vals()
                        for label in s.label_ids.sorted("sequence")
                    ],
                }
                for s in self.scope_ids.sorted("sequence")
            ],
            "alternate_actions": [
                v._portable_vals()
                for v in self.alternate_action_ids.sorted("sequence")
            ],
            "header_lines": [
                h._portable_vals() for h in self.header_line_ids.sorted("sequence")
            ],
            "slots": [s._export_slot() for s in self.slot_ids.sorted("sequence")],
        }

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _unique_import_key(self, key):
        base = key or "dashboard"
        candidate = base
        n = 1
        while self.search([("key", "=", candidate)], limit=1):
            n += 1
            candidate = "%s_%s" % (base, n)
        return candidate

    @api.model
    def _import_template(self, data):
        """Create a new draft blueprint from an exported template dict."""
        if not isinstance(data, dict) or data.get("marker") != TEMPLATE_MARKER:
            raise UserError(
                _("This file is not a Dynamic Dashboard Engine template.")
            )

        vals = dict(data.get("blueprint") or {})
        # Older templates used pre-1.0.74 / post-1.0.40 field names.
        for old, new in (
            ("primary_action_label", "primary_button_label"),
            ("alternate_label", "primary_label_alt"),
            ("alternate_label_scope_id", "primary_label_alt_scope_id"),
            ("link_hierarchy", "include_child_records"),
        ):
            if old in vals and new not in vals:
                vals[new] = vals.pop(old)
            else:
                vals.pop(old, None)
        host_model_name = vals.pop("host_model_name", None)
        host_model = self._mirror_model(host_model_name) if host_model_name else False
        if not host_model:
            raise UserError(
                _(
                    "This template needs the %(model)s model, which is not "
                    "installed on this database. Install the app that "
                    "provides it, then import again.",
                    model=host_model_name or _("host"),
                )
            )
        vals["host_model_id"] = host_model.id
        vals["state"] = "draft"
        vals["active"] = True
        vals.pop("generated_view_id", None)
        vals.pop("generated_action_id", None)
        vals.pop("generated_menu_id", None)
        key = data.get("key") or vals.get("name") and self._suggest_key(vals["name"])
        vals["key"] = self._unique_import_key(key or "imported_dashboard")

        graph_relation_path = data.get("graph_relation_path")
        if not vals.get("graph_data_field") and graph_relation_path:
            if isinstance(graph_relation_path, str):
                vals["graph_data_field"] = graph_relation_path
            elif isinstance(graph_relation_path, dict):
                path = self.env["dashboard.relation.path"]._import_relation_path(
                    graph_relation_path
                )
                if path and path.domain_field:
                    vals["graph_data_field"] = path.domain_field
        vals.pop("graph_relation_path_id", None)

        blueprint = self.create(vals)

        self._import_extra_groupby_fields(blueprint, data)
        self._import_period_fields(blueprint, data)

        for scope_data in data.get("scopes") or []:
            scope_vals = dict(scope_data)
            label_vals_list = scope_vals.pop("labels", None) or []
            scope = self.env["dashboard.blueprint.scope"].create(
                dict(scope_vals, blueprint_id=blueprint.id)
            )
            for label_vals in label_vals_list:
                self.env["dashboard.blueprint.scope.label"].create(
                    dict(label_vals, scope_id=scope.id)
                )

        alt_scope_name = data.get("primary_label_alt_scope_name") or data.get(
            "alternate_label_scope_name"
        )
        if alt_scope_name:
            scope = blueprint.scope_ids.filtered(
                lambda s, n=alt_scope_name: s.name == n
            )[:1]
            if scope:
                blueprint.primary_label_alt_scope_id = scope.id

        for variant_vals in (
            data.get("alternate_actions") or data.get("primary_action_variants") or []
        ):
            self.env["dashboard.blueprint.action.variant"].create(
                dict(variant_vals, blueprint_id=blueprint.id)
            )

        for item_vals in data.get("header_lines") or data.get("header_items") or []:
            vals = dict(item_vals, blueprint_id=blueprint.id)
            # Pre-1.0.44 kinds: detail → left, tags → right.
            kind = vals.get("kind")
            if kind == "detail":
                vals["kind"] = "left"
            elif kind == "tags":
                vals["kind"] = "right"
            # Pre-1.0.52 field_name / field2_name → field_names.
            vals = self.env["dashboard.blueprint.header.item"]._coerce_legacy_header_fields(
                vals
            )
            self.env["dashboard.blueprint.header.item"].create(vals)

        for slot_data in data.get("slots") or []:
            self.env["dashboard.blueprint.slot"]._import_slot(blueprint, slot_data)

        _logger.info(
            "Dashboard engine: imported template as blueprint %s", blueprint.key
        )
        return blueprint

    @api.model
    def _import_extra_groupby_fields(self, blueprint, data):
        names = data.get("graph_groupby_extra_fields") or []
        if not names or not blueprint.graph_model:
            return
        Fields = self.env["ir.model.fields"]
        found = []
        for name in names:
            field = Fields.search(
                [("model", "=", blueprint.graph_model), ("name", "=", name)], limit=1
            )
            if field:
                found.append(field)
        if found:
            blueprint.write(
                {
                    "graph_groupby_extra_ids": [(6, 0, [f.id for f in found])],
                    "ordered_graph_groupby_extra_ids": ",".join(
                        str(f.id) for f in found
                    ),
                }
            )

    @api.model
    def _import_period_fields(self, blueprint, data):
        if not blueprint.graph_model:
            return
        Fields = self.env["ir.model.fields"].sudo()
        for key, fname in (
            ("period_field_name", "period_field_id"),
            ("closed_period_field_name", "closed_period_field_id"),
        ):
            name = data.get(key)
            if not name:
                continue
            field = Fields.search(
                [("model", "=", blueprint.graph_model), ("name", "=", name)],
                limit=1,
            )
            if field:
                blueprint[fname] = field.id


class DashboardBlueprintSlot(models.Model):
    _inherit = "dashboard.blueprint.slot"

    def _export_slot(self):
        self.ensure_one()
        return {
            "vals": self._portable_vals(),
            "relation_path": (
                self.relate_field
                or (
                    self.relation_path_id.domain_field
                    if self.relation_path_id
                    else False
                )
            ),
            "conditions": [c._export_condition() for c in self.condition_ids],
            "action_variants": [
                v._portable_vals() for v in self.action_variant_ids.sorted("sequence")
            ],
        }

    @api.model
    def _import_slot(self, blueprint, slot_data):
        vals = dict(slot_data.get("vals") or {})
        vals["blueprint_id"] = blueprint.id
        relation_path_data = slot_data.get("relation_path")
        if not vals.get("relate_field") and relation_path_data:
            if isinstance(relation_path_data, str):
                vals["relate_field"] = relation_path_data
            elif isinstance(relation_path_data, dict):
                path = self.env["dashboard.relation.path"]._import_relation_path(
                    relation_path_data
                )
                if path and path.domain_field:
                    vals["relate_field"] = path.domain_field
        vals.pop("relation_path_id", None)
        slot = self.create(vals)
        condition_ids = [
            condition.id
            for condition in (
                self.env["dashboard.condition"]._import_condition(condition_data)
                for condition_data in slot_data.get("conditions") or []
            )
            if condition
        ]
        if condition_ids:
            slot.condition_ids = [(6, 0, condition_ids)]
        for variant_vals in slot_data.get("action_variants") or []:
            self.env["dashboard.blueprint.slot.action.variant"].create(
                dict(variant_vals, slot_id=slot.id)
            )
        return slot


class DashboardRelationPath(models.Model):
    _inherit = "dashboard.relation.path"

    def _export_relation_path(self):
        self.ensure_one()
        return {
            "name": self.name,
            "source_model": self.source_model,
            "target_model": self.target_model,
            "hops": [h.field_name for h in self.hop_ids.sorted("sequence")],
        }

    @api.model
    def _import_relation_path(self, data):
        source_model = self._mirror_model(data.get("source_model"))
        target_model = self._mirror_model(data.get("target_model"))
        if not source_model or not target_model:
            return self.browse()
        hops = [name for name in (data.get("hops") or []) if name]
        if not hops:
            return self.browse()
        existing = self.search(
            [
                ("source_model_id", "=", source_model.id),
                ("target_model_id", "=", target_model.id),
            ]
        )
        for path in existing:
            if [h.field_name for h in path.hop_ids.sorted("sequence")] == hops:
                return path
        path = self.create(
            {
                "name": data.get("name") or _("Imported path"),
                "source_model_id": source_model.id,
                "target_model_id": target_model.id,
            }
        )
        Hop = self.env["dashboard.relation.hop"]
        for index, field_name in enumerate(hops, start=1):
            Hop.create(
                {
                    "path_id": path.id,
                    "sequence": index * 10,
                    "field_name": field_name,
                }
            )
        return path


class DashboardCondition(models.Model):
    _inherit = "dashboard.condition"

    def _export_condition(self):
        self.ensure_one()
        if not self.domain_tree and self.rule_ids:
            self._rebuild_domain_tree_from_rules()
        return {
            "vals": self._portable_vals(),
            "domain_tree": self.domain_tree or [],
            "rules": [r._export_rule() for r in self.rule_ids.sorted("sequence")],
        }

    @api.model
    def _import_condition(self, data):
        vals = dict(data.get("vals") or {})
        model_name = vals.get("model")
        if model_name and model_name not in self.env:
            return self.browse()
        name = vals.get("name")
        existing = (
            self.search([("name", "=", name), ("model", "=", model_name)], limit=1)
            if name
            else self.browse()
        )
        if existing:
            return existing
        # Prefer an explicit domain tree when present (complex filters).
        domain_tree = data.get("domain_tree")
        if domain_tree is not None:
            vals["domain_tree"] = domain_tree
        condition = self.create(vals)
        Rule = self.env["dashboard.condition.rule"]
        GroupValue = self.env["dashboard.condition.group.value"]
        for rule_data in data.get("rules") or []:
            rule_vals = dict(rule_data.get("vals") or {})
            rule_vals["condition_id"] = condition.id
            rule = Rule.create(rule_vals)
            for gv_vals in rule_data.get("group_values") or []:
                GroupValue.create(dict(gv_vals, rule_id=rule.id))
        if domain_tree is not None:
            # Rules sync would overwrite a nested tree — restore it.
            condition.domain_tree = domain_tree
        elif condition.rule_ids:
            condition._rebuild_domain_tree_from_rules()
        return condition


class DashboardConditionRule(models.Model):
    _inherit = "dashboard.condition.rule"

    def _export_rule(self):
        self.ensure_one()
        return {
            "vals": self._portable_vals(),
            "group_values": [
                gv._portable_vals() for gv in self.group_value_ids.sorted("sequence")
            ],
        }


class DashboardBlueprintImportWizard(models.TransientModel):
    _name = "dashboard.blueprint.import.wizard"
    _description = "Import Dashboard Blueprint Template"

    data_file = fields.Binary(string="Template file (.json)", required=True)
    filename = fields.Char()

    def action_import(self):
        self.ensure_one()
        if not self.data_file:
            raise UserError(_("Choose a template file first."))
        try:
            raw = base64.b64decode(self.data_file)
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise UserError(
                _("Could not read this file as a dashboard template: %(error)s",
                  error=exc)
            ) from exc
        blueprint = self.env["dashboard.blueprint"]._import_template(data)
        return {
            "type": "ir.actions.act_window",
            "res_model": "dashboard.blueprint",
            "res_id": blueprint.id,
            "views": [(False, "form")],
            "target": "current",
        }
