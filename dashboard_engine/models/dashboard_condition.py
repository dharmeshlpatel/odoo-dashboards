# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Reusable filters for dashboard slots and scopes.

A condition is a named domain tree that compiles to an ORM domain at render
time. Leaves may use typed ``__de__`` tokens (relative dates, uid, company,
card record, group-dependent values).

Primary editor: ``domain`` Char with Odoo's domain builder
(``allow_expressions``). Canonical store: ``domain_tree``. Simple Rules O2M
is optional and rebuilds the tree when changed.
"""
import json
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..tools.condition_domain import (
    compile_domain_tree,
    domain_string_to_tree,
    domain_tree_to_jsonable,
    normalize_tree_values,
    preserve_group_value_tokens,
    preserve_relative_date_tokens,
    rules_to_domain_tree,
    tree_to_domain_string,
)

_logger = logging.getLogger(__name__)

OPERATORS = [
    ("=", "equals"),
    ("!=", "does not equal"),
    (">", "is greater than"),
    (">=", "is at least"),
    ("<", "is less than"),
    ("<=", "is at most"),
    ("in", "is one of"),
    ("not in", "is not one of"),
    ("ilike", "contains"),
    ("like", "contains (exact case)"),
    ("=?", "is empty or equals"),
    ("child_of", "is under"),
]

VALUE_TYPES = [
    ("static", "Fixed value"),
    ("relative_date", "Relative date"),
    ("user", "Current user"),
    ("company", "Current company"),
    ("record", "This card's record"),
    ("false", "Empty / not set"),
    ("true", "Yes / True"),
]

RELATIVE_WHEN = [
    ("today", "Today"),
    ("now", "Right now"),
    ("start_of_today", "Start of today"),
    ("end_of_today", "End of today"),
    ("days_ago", "N days ago"),
    ("days_ahead", "N days from now"),
]


class DashboardCondition(models.Model):
    _name = "dashboard.condition"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Condition"
    _order = "name, id"

    name = fields.Char(required=True, translate=True)
    model = fields.Char(
        required=True,
        index=True,
        help="Technical model the filter applies to, e.g. crm.lead.",
    )
    model_id = fields.Many2one(
        "ir.model",
        string="On",
        compute="_compute_model_id",
        inverse="_inverse_model_id",
        store=True,
        readonly=False,
        ondelete="cascade",
    )
    domain_model_name = fields.Char(
        string="Domain model",
        related="model_id.model",
        readonly=True,
        help="Technical model name for the domain builder widget.",
    )
    match = fields.Selection(
        [("all", "all of these rules"), ("any", "any of these rules")],
        default="all",
        required=True,
        string="Match",
    )
    rule_ids = fields.One2many(
        "dashboard.condition.rule",
        "condition_id",
        string="Rules",
        copy=True,
    )
    domain_tree = fields.Json(
        string="Domain tree",
        help="Portable Odoo domain list with optional __de__ tokens. "
        "Compiled at render time. Synced from the Domain builder and from Rules.",
    )
    domain = fields.Char(
        string="Domain",
        compute="_compute_domain",
        inverse="_inverse_domain",
        readonly=False,
        store=True,
        help="Visual domain builder. Supports nested AND/OR/NOT and "
        "expressions such as uid, company_id, context_today(), active_id.",
    )
    domain_tree_readonly = fields.Text(
        string="Domain tree (JSON)",
        compute="_compute_domain_tree_readonly",
        help="Technical preview of the stored domain tree.",
    )
    module_ids = fields.Many2many(
        "ir.module.module",
        string="Only when apps installed",
        help="Leave empty to always apply. Otherwise the condition is ignored "
        "until every listed app is installed.",
    )
    module_depends = fields.Char(
        compute="_compute_module_depends",
        inverse="_inverse_module_depends",
        store=True,
        readonly=False,
    )
    note = fields.Char(help="Optional reminder for the person configuring it.")

    @api.depends("model")
    def _compute_model_id(self):
        for rec in self:
            rec.model_id = rec._mirror_model(rec.model)

    def _inverse_model_id(self):
        for rec in self:
            rec.model = rec.model_id.model or False

    @api.depends("module_ids")
    def _compute_module_depends(self):
        for rec in self:
            rec.module_depends = (
                ",".join(sorted(rec.module_ids.mapped("name"))) or False
            )

    def _inverse_module_depends(self):
        Module = self.env["ir.module.module"].sudo()
        for rec in self:
            names = rec._mirror_names(rec.module_depends)
            rec.module_ids = Module.search([("name", "in", names)]) if names else False

    @api.depends("domain_tree")
    def _compute_domain_tree_readonly(self):
        for rec in self:
            if not rec.domain_tree:
                rec.domain_tree_readonly = ""
            else:
                rec.domain_tree_readonly = json.dumps(
                    rec.domain_tree, indent=2, sort_keys=False
                )

    @api.depends("domain_tree")
    def _compute_domain(self):
        for rec in self:
            rec.domain = tree_to_domain_string(
                rec.domain_tree or [], env=rec.env, model_name=rec.model
            )

    def _inverse_domain(self):
        for rec in self:
            tree = normalize_tree_values(domain_string_to_tree(rec.domain))
            tree = preserve_group_value_tokens(rec.domain_tree, tree)
            tree = preserve_relative_date_tokens(
                rec.domain_tree, tree, env=rec.env, model_name=rec.model
            )
            rec.domain_tree = domain_tree_to_jsonable(tree)

    def _is_applicable(self):
        """False when a required app is missing — condition is then skipped."""
        self.ensure_one()
        if not self.module_depends:
            return True
        return self.env["dashboard.blueprint"]._modules_installed_static(
            self.module_depends
        )

    def _rebuild_domain_tree_from_rules(self):
        """Sync ``domain_tree`` (and Domain builder) from the rules O2M."""
        for rec in self:
            tree = rules_to_domain_tree(rec.rule_ids.sorted("sequence"), rec.match)
            # Assigning domain_tree triggers _compute_domain for the editor.
            rec.domain_tree = domain_tree_to_jsonable(tree)

    def to_domain(self, record=None):
        """Compile this condition to an ORM domain for the current user."""
        self.ensure_one()
        if not self._is_applicable():
            return []
        tree = self.domain_tree
        if tree:
            try:
                return compile_domain_tree(
                    tree, self.env, record=record, model_name=self.model
                )
            except Exception:
                _logger.warning(
                    "Dashboard condition %s domain_tree failed to compile; "
                    "falling back to rules",
                    self.id,
                    exc_info=True,
                )
        return self._to_domain_from_rules(record)

    def _to_domain_from_rules(self, record=None):
        leaves = []
        for rule in self.rule_ids.sorted("sequence"):
            leaf = rule.to_leaf(record)
            if leaf is not None:
                leaves.append(leaf)
        if not leaves:
            return []
        if self.match == "any":
            return list(fields.Domain.OR([[leaf] for leaf in leaves]))
        return leaves

    @api.model
    def merge_conditions(self, conditions, record=None):
        """AND together every applicable condition in ``conditions``."""
        parts = []
        for condition in conditions:
            domain = condition.to_domain(record)
            if domain:
                parts.append(domain)
        parts = [part for part in parts if part]
        if not parts:
            return []
        if len(parts) == 1:
            return list(parts[0])
        return list(fields.Domain.AND(parts))

    @api.model
    def _prepare_condition_vals(self, vals, for_write=False):
        """Keep ``model`` in sync with ``model_id``; ignore stale empty ``model``."""
        vals = dict(vals)
        model_id = vals.get("model_id")
        if model_id:
            model_name = self.env["ir.model"].browse(model_id).model
            if model_name:
                vals["model"] = model_name
        elif for_write and vals.get("model") in (False, ""):
            # Client must not clear model when only other fields (domain, rules) change.
            vals.pop("model", None)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_condition_vals(vals) for vals in vals_list]
        records = super().create(vals_list)
        # Seeds may create rules in a follow-up; rebuild when rules already set.
        need = records.filtered("rule_ids")
        if need:
            need._rebuild_domain_tree_from_rules()
        return records

    def write(self, vals):
        vals = self._prepare_condition_vals(vals, for_write=True)
        res = super().write(vals)
        # Rules editor owns the tree unless Domain builder / domain_tree was set.
        if (
            "domain_tree" not in vals
            and "domain" not in vals
            and ("match" in vals or "rule_ids" in vals)
        ):
            self._rebuild_domain_tree_from_rules()
        return res


class DashboardConditionRule(models.Model):
    _name = "dashboard.condition.rule"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Condition Rule"
    _order = "sequence, id"

    condition_id = fields.Many2one(
        "dashboard.condition", required=True, ondelete="cascade", index=True
    )
    model = fields.Char(related="condition_id.model", readonly=True)
    sequence = fields.Integer(default=10)
    field_name = fields.Char()
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Field",
        compute="_compute_field_id",
        inverse="_inverse_field_id",
        store=True,
        readonly=False,
        ondelete="set null",
        # Not required: seeds store the technical name so a missing app does
        # not block loading; the picker fills in when the model is present.
    )
    operator = fields.Selection(OPERATORS, required=True, default="=")
    value_type = fields.Selection(VALUE_TYPES, required=True, default="static")
    value_char = fields.Char(
        string="Value",
        help="Fixed value. For 'is one of', use a comma-separated list.",
    )
    relative_when = fields.Selection(RELATIVE_WHEN, string="When")
    relative_days = fields.Integer(string="Days", default=0)
    group_value_ids = fields.One2many(
        "dashboard.condition.group.value",
        "rule_id",
        string="Value by group",
        copy=True,
        help="If the viewer belongs to a listed group, use that value instead.",
    )

    @api.depends("field_name", "model")
    def _compute_field_id(self):
        for rule in self:
            rule.field_id = rule._mirror_field(rule.model, rule.field_name)

    def _inverse_field_id(self):
        for rule in self:
            rule.field_name = rule.field_id.name or False

    @api.constrains("field_id", "condition_id")
    def _check_field_on_condition_model(self):
        for rule in self:
            if not rule.field_id or not rule.condition_id.model:
                continue
            if rule.field_id.model != rule.condition_id.model:
                raise ValidationError(
                    _(
                        "%(field)s belongs to %(wrong)s, not %(expected)s.",
                        field=rule.field_id.field_description,
                        wrong=rule.field_id.model,
                        expected=rule.condition_id.model,
                    )
                )

    @api.constrains("value_type", "relative_when", "field_id")
    def _check_relative_date(self):
        for rule in self:
            if rule.value_type != "relative_date":
                continue
            if not rule.relative_when:
                raise ValidationError(
                    _("Pick when the date is for rule on %(field)s.",
                      field=rule.field_id.field_description or rule.field_name)
                )
            if (
                rule.field_id
                and rule.field_id.ttype not in ("date", "datetime")
            ):
                raise ValidationError(
                    _(
                        "%(field)s is not a date, so it cannot use a relative date.",
                        field=rule.field_id.field_description,
                    )
                )

    def to_leaf(self, record=None):
        """One domain leaf, or None when the rule cannot be resolved."""
        self.ensure_one()
        name = self.field_name or (self.field_id.name if self.field_id else False)
        if not name:
            return None
        # Card-bound values are only known when a single card is in hand
        # (action open). The batch count path skips them; the link field
        # already scopes rows to the visible cards.
        if self.value_type == "record" and record is None:
            return None
        try:
            value = self._resolve_value(record)
        except Exception:
            _logger.warning(
                "Dashboard condition rule %s failed to resolve", self.id, exc_info=True
            )
            return None
        return (name, self.operator, value)

    def _resolve_value(self, record=None):
        self.ensure_one()
        value_type = self.value_type
        if value_type == "false":
            return False
        if value_type == "true":
            return True
        if value_type == "user":
            return self.env.uid
        if value_type == "company":
            return self.env.company.id
        if value_type == "record":
            if record is None:
                return False
            if getattr(record, "_ids", None) is not None and len(record) > 1:
                return list(record.ids)
            return record.id
        if value_type == "relative_date":
            return self._resolve_relative_date()
        # static, possibly overridden by the viewer's groups
        return self._resolve_static_value()

    def _resolve_static_value(self):
        self.ensure_one()
        # Config rows are readable as sudo; the viewer's groups still decide
        # which override applies.
        rule = self.sudo()
        user = self.env.user
        for group_value in rule.group_value_ids:
            xmlids = group_value._group_xmlids()
            if any(user.has_group(xmlid) for xmlid in xmlids if xmlid):
                return rule._parse_static(group_value.value_char)
        return rule._parse_static(rule.value_char)

    def _parse_static(self, raw):
        if raw is None or raw is False or raw == "":
            return False
        text = str(raw).strip()
        if self.operator in ("in", "not in"):
            if text.startswith("["):
                try:
                    return list(json.loads(text.replace("'", '"')))
                except Exception:
                    pass
            return [part.strip() for part in text.split(",") if part.strip()]
        # Booleans written as text.
        lowered = text.lower()
        if lowered in ("true", "yes"):
            return True
        if lowered in ("false", "no"):
            return False
        # Integers when the field is numeric / many2one.
        field = self.sudo().field_id
        if field and field.ttype in (
            "integer",
            "many2one",
            "many2many",
            "one2many",
        ):
            try:
                return int(text)
            except (TypeError, ValueError):
                pass
        if field and field.ttype in ("float", "monetary"):
            try:
                return float(text)
            except (TypeError, ValueError):
                pass
        return text

    def _resolve_relative_date(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        when = self.relative_when
        days = self.relative_days or 0
        field = self.sudo().field_id
        is_datetime = field and field.ttype == "datetime"

        if when == "now":
            return fields.Datetime.to_string(now)
        if when == "today":
            return (
                fields.Datetime.to_string(
                    fields.Datetime.to_datetime(today)
                )
                if is_datetime
                else fields.Date.to_string(today)
            )
        if when == "start_of_today":
            start = fields.Datetime.to_datetime(today)
            return fields.Datetime.to_string(start)
        if when == "end_of_today":
            end = fields.Datetime.end_of(
                fields.Datetime.to_datetime(today), "day"
            )
            return fields.Datetime.to_string(end)
        if when == "days_ago":
            target = today - timedelta(days=days)
            return (
                fields.Datetime.to_string(fields.Datetime.to_datetime(target))
                if is_datetime
                else fields.Date.to_string(target)
            )
        if when == "days_ahead":
            target = today + timedelta(days=days)
            return (
                fields.Datetime.to_string(fields.Datetime.to_datetime(target))
                if is_datetime
                else fields.Date.to_string(target)
            )
        return fields.Date.to_string(today)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped("condition_id")._rebuild_domain_tree_from_rules()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.mapped("condition_id")._rebuild_domain_tree_from_rules()
        return res

    def unlink(self):
        conditions = self.mapped("condition_id")
        res = super().unlink()
        conditions._rebuild_domain_tree_from_rules()
        return res


class DashboardConditionGroupValue(models.Model):
    """Override a rule's fixed value when the viewer is in a given group.

    Example: CRM type is ``lead`` for users in Leads, otherwise ``opportunity``.
    """

    _name = "dashboard.condition.group.value"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Condition Group Value"
    _order = "sequence, id"

    rule_id = fields.Many2one(
        "dashboard.condition.rule", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    groups_xmlids = fields.Char(
        help="Durable group xmlids; survives when the app that defines "
        "the group is not installed yet."
    )
    group_ids = fields.Many2many(
        "res.groups",
        string="When viewer is in",
        compute="_compute_group_ids",
        inverse="_inverse_group_ids",
        store=True,
        readonly=False,
    )
    value_char = fields.Char(required=True, string="Use value")

    @api.depends("groups_xmlids")
    def _compute_group_ids(self):
        for rec in self:
            rec.group_ids = rec._mirror_records("res.groups", rec.groups_xmlids)

    def _inverse_group_ids(self):
        for rec in self:
            rec.groups_xmlids = rec._mirror_xmlids(rec.group_ids)

    def _group_xmlids(self):
        self.ensure_one()
        return self._mirror_names(self.groups_xmlids)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped("rule_id.condition_id")._rebuild_domain_tree_from_rules()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.mapped("rule_id.condition_id")._rebuild_domain_tree_from_rules()
        return res

    def unlink(self):
        conditions = self.mapped("rule_id.condition_id")
        res = super().unlink()
        conditions._rebuild_domain_tree_from_rules()
        return res
