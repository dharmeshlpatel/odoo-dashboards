# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Domain-tree compiler for dashboard.condition.

Storage shape is a JSON-serialisable Odoo domain list. Leaf values may be
literals or typed tokens::

    {"__de__": "uid"}
    {"__de__": "relative_date", "when": "today"}
    {"__de__": "group_value", "default": "opportunity",
     "map": [{"groups": ["crm.group_use_lead"], "value": "lead"}]}
    {"__de__": "rule_value", "default": "opportunity",
     "map": [
         {"when": {"type": "group", "groups": ["crm.group_use_lead"]},
          "value": "lead"},
         {"when": {"type": "record", "domain": "[('country_id.code', '=', 'DE')]"},
          "value": "b2b_de"},
     ]}

Compile at render time via :func:`compile_domain_tree` or
:func:`compile_context_value` — never ``safe_eval`` for tokens.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

TOKEN_KEY = "__de__"

RELATIVE_WHENS = frozenset(
    {
        "today",
        "now",
        "start_of_today",
        "end_of_today",
        "days_ago",
        "days_ahead",
    }
)


def is_token(value):
    return isinstance(value, dict) and TOKEN_KEY in value


def token(kind, **extra):
    """Build a portable token dict."""
    payload = {TOKEN_KEY: kind}
    payload.update(extra)
    return payload


def compile_domain_tree(tree, env, record=None, model_name=None):
    """Resolve tokens in ``tree`` to a concrete ORM domain list."""
    if not tree:
        return []
    result = []
    for node in tree:
        if node in ("&", "|", "!"):
            result.append(node)
            continue
        if isinstance(node, (list, tuple)) and len(node) == 3:
            name, operator, value = node
            if is_token(value):
                resolved = resolve_token(
                    value, env, record, model_name, name
                )
                if resolved is _SKIP:
                    result.append(None)
                    continue
                value = resolved
            result.append((name, operator, value))
            continue
        raise ValidationError(
            "Invalid domain tree node %r — expected operator or "
            "(field, op, value)." % (node,)
        )
    return _normalize_compiled_domain(result)


_SKIP = object()


def _normalize_compiled_domain(nodes):
    """Drop skipped leaves and repair flat AND / prefix-OR trees."""
    if not nodes:
        return []
    skipped = any(node is None for node in nodes)
    if not skipped:
        return list(nodes)

    ops = [node for node in nodes if node in ("&", "|", "!")]
    leaves = [
        node
        for node in nodes
        if node not in ("&", "|", "!") and node is not None
    ]
    if not leaves:
        return []
    if not ops:
        return leaves
    # Prefix OR produced by rules_to_domain_tree(match='any').
    if ops and all(op == "|" for op in ops):
        if len(leaves) == 1:
            return leaves
        return ["|"] * (len(leaves) - 1) + leaves
    # Complex tree with a skipped leaf: strip Nones (may be imperfect).
    _logger.warning(
        "condition domain tree dropped a skipped leaf inside a complex "
        "expression; verify the filter still matches intent"
    )
    return [node for node in nodes if node is not None]


def resolve_token(tok, env, record=None, model_name=None, field_name=None):
    """Resolve one ``__de__`` token to a concrete leaf value."""
    kind = tok.get(TOKEN_KEY)
    if kind == "uid":
        return env.uid
    if kind == "company":
        return env.company.id
    if kind == "company_ids":
        return env.companies.ids
    if kind == "false":
        return False
    if kind == "true":
        return True
    if kind == "record":
        if record is None:
            return _SKIP
        attr = tok.get("field") or "id"
        if getattr(record, "_ids", None) is not None and len(record) > 1:
            if attr == "id":
                return list(record.ids)
            return record.mapped(attr)
        return record[attr] if attr != "id" else record.id
    if kind == "relative_date":
        return _resolve_relative_date(tok, env, model_name, field_name)
    if kind == "group_value":
        return _resolve_rule_map(tok, env, record=record, allow_record=False)
    if kind == "rule_value":
        return _resolve_rule_map(tok, env, record=record, allow_record=True)
    raise ValidationError(
        "Unknown dashboard condition token %(kind)s." % {"kind": kind}
    )


def compile_context_value(value, env, record=None, model_name=None):
    """Resolve ``__de__`` tokens inside an action-context tree.

    Used for blueprint ``primary_action_context`` and slot ``action_context``.
    Nested dicts/lists are walked; token dicts are replaced with concrete
    values. A skipped token becomes ``False``.
    """
    if is_token(value):
        resolved = resolve_token(
            value, env, record=record, model_name=model_name
        )
        return False if resolved is _SKIP else resolved
    if isinstance(value, dict):
        return {
            key: compile_context_value(
                item, env, record=record, model_name=model_name
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            compile_context_value(
                item, env, record=record, model_name=model_name
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            compile_context_value(
                item, env, record=record, model_name=model_name
            )
            for item in value
        )
    return value


def _resolve_relative_date(tok, env, model_name, field_name):
    when = tok.get("when") or "today"
    if when not in RELATIVE_WHENS:
        raise ValidationError(
            "Unknown relative date when=%(when)s." % {"when": when}
        )
    days = int(tok.get("days") or 0)
    today = fields.Date.context_today(env.user)
    now = fields.Datetime.now()
    is_datetime = _field_is_datetime(env, model_name, field_name)

    if when == "now":
        return fields.Datetime.to_string(now)
    if when == "today":
        return (
            fields.Datetime.to_string(fields.Datetime.to_datetime(today))
            if is_datetime
            else fields.Date.to_string(today)
        )
    if when == "start_of_today":
        return fields.Datetime.to_string(fields.Datetime.to_datetime(today))
    if when == "end_of_today":
        end = fields.Datetime.end_of(fields.Datetime.to_datetime(today), "day")
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


def _field_is_datetime(env, model_name, field_name):
    if not model_name or not field_name or model_name not in env:
        return False
    # Support simple dotted paths: take the terminal field.
    model = env[model_name]
    parts = field_name.split(".")
    for index, part in enumerate(parts):
        field = model._fields.get(part)
        if not field:
            return False
        if index == len(parts) - 1:
            return field.type == "datetime"
        if not field.comodel_name or field.comodel_name not in env:
            return False
        model = env[field.comodel_name]
    return False


def _resolve_group_value(tok, env, record=None):
    """Legacy alias — group-only maps (no card-record when clauses)."""
    return _resolve_rule_map(tok, env, record=record, allow_record=False)


def _resolve_rule_map(tok, env, record=None, allow_record=True):
    """First matching rule wins; otherwise ``default``.

    Map entries may be legacy ``{"groups": [...], "value": ...}`` or::

        {"when": {"type": "group", "groups": [...]}, "value": ...}
        {"when": {"type": "record", "domain": [...] | "..."}, "value": ...}
    """
    user = env.user
    for entry in tok.get("map") or []:
        if not isinstance(entry, dict):
            continue
        when = entry.get("when")
        if when is None:
            groups = entry.get("groups") or []
            if any(user.has_group(xmlid) for xmlid in groups if xmlid):
                return _coerce_literal(entry.get("value"))
            continue
        if not isinstance(when, dict):
            continue
        wtype = when.get("type") or "group"
        if wtype == "group":
            groups = when.get("groups") or []
            if any(user.has_group(xmlid) for xmlid in groups if xmlid):
                return _coerce_literal(entry.get("value"))
            continue
        if wtype == "record":
            if not allow_record:
                continue
            if record is None:
                continue
            domain = _coerce_domain(when.get("domain"))
            if domain is None:
                _logger.warning(
                    "rule_value record domain invalid; skipping rule: %r",
                    when.get("domain"),
                )
                continue
            if not domain:
                # Empty domain never matches (avoids accidental always-true).
                continue
            try:
                if record.filtered_domain(domain):
                    return _coerce_literal(entry.get("value"))
            except Exception:
                _logger.warning(
                    "rule_value record domain failed on %s; skipping rule",
                    record._name,
                    exc_info=True,
                )
            continue
    return _coerce_literal(tok.get("default"))


def _coerce_domain(raw):
    """Normalize a stored domain to a list, or ``None`` if invalid."""
    if isinstance(raw, (list, tuple)):
        return list(raw)
    if raw is None or raw is False:
        return []
    text = str(raw).strip()
    if not text or text == "[]":
        return []
    try:
        from ast import literal_eval

        parsed = literal_eval(text)
        if isinstance(parsed, (list, tuple)):
            return list(parsed)
    except Exception:
        pass
    try:
        from odoo.tools.safe_eval import safe_eval

        # Same expression helpers as domain Char ↔ tree (uid / True / False).
        parsed = safe_eval(text, _token_eval_context())
        if isinstance(parsed, (list, tuple)):
            return list(parsed)
    except Exception:
        pass
    return None


def _coerce_literal(raw):
    if raw is None or raw is False or raw == "":
        return False
    if isinstance(raw, (int, float, bool, list)):
        return raw
    text = str(raw).strip()
    lowered = text.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if text.startswith("["):
        try:
            return list(json.loads(text.replace("'", '"')))
        except Exception:
            pass
    try:
        return int(text)
    except (TypeError, ValueError):
        pass
    try:
        return float(text)
    except (TypeError, ValueError):
        pass
    return text


def rules_to_domain_tree(rules, match="all"):
    """Build a domain tree from ``dashboard.condition.rule`` records.

    Leaves keep tokens (unresolved) so the tree stays portable across days
    and users.
    """
    leaves = []
    for rule in rules:
        leaf = rule_to_token_leaf(rule)
        if leaf is not None:
            leaves.append(leaf)
    if not leaves:
        return []
    if match == "any" and len(leaves) > 1:
        # Prefix OR: | | leaf leaf leaf  (n-1 operators)
        return ["|"] * (len(leaves) - 1) + leaves
    return leaves


def rule_to_token_leaf(rule):
    """One unresolved domain leaf ``[field, op, value_or_token]``."""
    name = rule.field_name or (rule.field_id.name if rule.field_id else False)
    if not name:
        return None
    value_type = rule.value_type
    if value_type == "false":
        value = token("false")
    elif value_type == "true":
        value = token("true")
    elif value_type == "user":
        value = token("uid")
    elif value_type == "company":
        value = token("company")
    elif value_type == "record":
        value = token("record")
    elif value_type == "relative_date":
        value = token(
            "relative_date",
            when=rule.relative_when or "today",
            days=rule.relative_days or 0,
        )
    else:
        # static — possibly with group overrides
        group_map = []
        for group_value in rule.sudo().group_value_ids.sorted("sequence"):
            xmlids = group_value._group_xmlids()
            if not xmlids:
                continue
            group_map.append(
                {"groups": list(xmlids), "value": group_value.value_char}
            )
        if group_map:
            value = token(
                "group_value",
                default=rule.value_char,
                map=group_map,
            )
        else:
            value = rule._parse_static(rule.value_char)
    return [name, rule.operator, value]


def domain_tree_to_jsonable(tree):
    """Ensure tuples become lists for Json storage."""
    if not tree:
        return []
    out = []
    for node in tree:
        if node in ("&", "|", "!"):
            out.append(node)
        elif isinstance(node, (list, tuple)) and len(node) == 3:
            out.append([node[0], node[1], node[2]])
        elif isinstance(node, (list, tuple)):
            out.append(domain_tree_to_jsonable(node))
        else:
            out.append(node)
    return out


# ---------------------------------------------------------------------------
# Domain editor (Char + widget="domain") ↔ token tree
# ---------------------------------------------------------------------------

def _token_eval_context():
    """Context so ``safe_eval`` of a domain string yields ``__de__`` tokens."""

    class _Attr:
        def __init__(self, **attrs):
            for key, value in attrs.items():
                setattr(self, key, value)

    class _RelDelta:
        def __init__(self, days=0, **_kwargs):
            self.days = int(days or 0)

    class _TodayExpr:
        """Stand-in for ``context_today()`` so ``.strftime(...)`` round-trips."""

        def __init__(self, when="today", days=0):
            self.when = when
            self.days = days

        def strftime(self, _fmt):
            return token("relative_date", when=self.when, days=self.days)

        def __add__(self, other):
            if isinstance(other, _RelDelta):
                days = other.days
                if days < 0:
                    return _TodayExpr("days_ago", -days)
                if days > 0:
                    return _TodayExpr("days_ahead", days)
                return _TodayExpr("today")
            return NotImplemented

        def __radd__(self, other):
            return self.__add__(other)

    class _DatetimeModule:
        class datetime:  # noqa: N801 — mirrors datetime.datetime for domains
            @staticmethod
            def now():
                return token("relative_date", when="now")

            @staticmethod
            def today():
                return token("relative_date", when="today")

            @staticmethod
            def combine(date_part, _time_part):
                # datetime.datetime.combine(context_today(), ...) → today token
                if isinstance(date_part, _TodayExpr):
                    return _TodayExpr(date_part.when, date_part.days)
                if is_token(date_part) and date_part.get(TOKEN_KEY) == "relative_date":
                    return _TodayExpr(
                        date_part.get("when") or "today",
                        int(date_part.get("days") or 0),
                    )
                return _TodayExpr("today")

        class time:  # noqa: N801
            def __init__(self, *args, **kwargs):
                pass

    def _context_today(*_a, **_k):
        return _TodayExpr("today")

    def _relativedelta(**kwargs):
        return _RelDelta(**kwargs)

    return {
        "uid": token("uid"),
        "user": _Attr(id=token("uid")),
        "company_id": token("company"),
        "company": _Attr(id=token("company"), ids=token("company_ids")),
        "allowed_company_ids": token("company_ids"),
        "active_id": token("record"),
        "record_id": token("record"),
        "context_today": _context_today,
        "relativedelta": _relativedelta,
        "datetime": _DatetimeModule(),
        # Group-dependent value — not a native Odoo domain literal; used by
        # our domain Char ↔ token round-trip with allow_expressions.
        "group_value": _eval_group_value,
        "True": True,
        "False": False,
        "None": None,
    }


def _eval_group_value(default, map=None):
    """Build a group_value token from a domain-editor expression."""
    if isinstance(map, str):
        try:
            map = json.loads(map)
        except Exception:
            map = []
    return token("group_value", default=default, map=list(map or []))



def domain_string_to_tree(domain_str):
    """Parse an Odoo domain Char (with expressions) into a token tree."""
    from odoo.tools.safe_eval import safe_eval

    raw = (domain_str or "").strip() or "[]"
    try:
        parsed = safe_eval(raw, _token_eval_context())
    except Exception as exc:
        raise ValidationError(
            "Invalid domain: %s" % exc
        ) from exc
    if not isinstance(parsed, (list, tuple)):
        raise ValidationError("Domain must be a list.")
    return domain_tree_to_jsonable(list(parsed))


def _relative_date_to_smart_string(value):
    """Map a relative_date token to DomainSelector smart-date text.

    Examples: ``today``, ``today -7d``, ``today +1d``.
    """
    when = value.get("when") or "today"
    days = int(value.get("days") or 0)
    if when in ("today", "start_of_today", "now"):
        return "today"
    if when == "end_of_today":
        return "today +1d"
    if when == "days_ago":
        return "today -%sd" % days
    if when == "days_ahead":
        return "today +%sd" % days
    return "today"


def _token_to_expression(value, env=None, model_name=None, field_name=None):
    """Serialize a ``__de__`` token back to a domain-editor expression.

    Relative dates use Odoo smart-date strings (``\"today\"``, ``\"today -7d\"``)
    so the Conditions domain widget can offer before/after presets like
    DomainSelector ``is in``. Tokens stay in ``domain_tree`` for KPI compile.
    """
    if not is_token(value):
        return None
    kind = value.get(TOKEN_KEY)
    if kind == "uid":
        return "uid"
    if kind == "company":
        return "company_id"
    if kind == "company_ids":
        return "allowed_company_ids"
    if kind == "record":
        return "active_id"
    if kind == "false":
        return "False"
    if kind == "true":
        return "True"
    if kind == "relative_date":
        return json.dumps(_relative_date_to_smart_string(value))
    if kind == "group_value":
        return _format_literal(value.get("default"))
    return None


def _format_literal(value):
    """Format a plain domain literal (not a token expression)."""
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[%s]" % ", ".join(_format_literal(v) for v in value)
    return repr(value)


def _format_domain_value(value, env=None, model_name=None, field_name=None):
    expr = _token_to_expression(
        value, env=env, model_name=model_name, field_name=field_name
    )
    if expr is not None:
        return expr
    if isinstance(value, dict):
        # Never embed raw dicts in the Char — DomainSelector rejects them.
        return json.dumps(json.dumps(value))
    return _format_literal(value)


def tree_to_domain_string(tree, env=None, model_name=None):
    """Serialize a token tree to a domain Char for ``widget='dashboard_domain'``.

    Relative-date tokens become smart-date strings (``today``, ``today -7d``)
    for before/after presets. ``env`` / ``model_name`` are kept for API
    compatibility with callers.
    """
    if not tree:
        return "[]"
    parts = []
    for node in tree:
        if node in ("&", "|", "!"):
            parts.append(json.dumps(node))
        elif isinstance(node, (list, tuple)) and len(node) == 3:
            name, operator, value = node
            parts.append(
                "(%s, %s, %s)"
                % (
                    json.dumps(name),
                    json.dumps(operator),
                    _format_domain_value(
                        value, env=env, model_name=model_name, field_name=name
                    ),
                )
            )
        else:
            parts.append(repr(node))
    return "[%s]" % ", ".join(parts)


def normalize_tree_values(tree):
    """Convert marker strings / JSON token blobs into real tokens."""
    if not tree:
        return []
    out = []
    for node in tree:
        if node in ("&", "|", "!"):
            out.append(node)
            continue
        if isinstance(node, (list, tuple)) and len(node) == 3:
            name, operator, value = node
            value = _coerce_editor_value(value)
            out.append([name, operator, value])
            continue
        out.append(node)
    return out


def preserve_group_value_tokens(old_tree, new_tree):
    """Re-attach ``group_value`` tokens after the domain Char shows defaults.

    The domain builder cannot represent group overrides, so
    :func:`tree_to_domain_string` emits the default literal. On inverse, if
    the leaf still matches a known value from the previous token, keep it.
    """
    old_tokens = {}
    for node in old_tree or []:
        if not (isinstance(node, (list, tuple)) and len(node) == 3):
            continue
        value = node[2]
        if is_token(value) and value.get(TOKEN_KEY) == "group_value":
            old_tokens[(node[0], node[1])] = value
    if not old_tokens:
        return new_tree

    out = []
    for node in new_tree or []:
        if not (isinstance(node, (list, tuple)) and len(node) == 3):
            out.append(node)
            continue
        name, operator, value = node
        old = old_tokens.get((name, operator))
        if old and not is_token(value):
            known = {old.get("default")}
            for entry in old.get("map") or []:
                known.add(entry.get("value"))
            if value in known:
                out.append([name, operator, old])
                continue
        out.append([name, operator, value])
    return out


def preserve_relative_date_tokens(old_tree, new_tree, env=None, model_name=None):
    """Keep ``relative_date`` tokens when Domain Char shows smart/ISO dates.

    The builder may display ``\"today\"`` / ``\"today -7d\"`` (or a legacy ISO
    date). If the user did not change that value, restore the token so KPI
    compilation stays relative.
    """
    old_tokens = {}
    for node in old_tree or []:
        if not (isinstance(node, (list, tuple)) and len(node) == 3):
            continue
        value = node[2]
        if is_token(value) and value.get(TOKEN_KEY) == "relative_date":
            old_tokens[(node[0], node[1])] = value
    if not old_tokens:
        return new_tree

    out = []
    for node in new_tree or []:
        if not (isinstance(node, (list, tuple)) and len(node) == 3):
            out.append(node)
            continue
        name, operator, value = node
        old = old_tokens.get((name, operator))
        if old and not is_token(value) and isinstance(value, str):
            if value == _relative_date_to_smart_string(old):
                out.append([name, operator, old])
                continue
            if env is not None:
                resolved = _resolve_relative_date(old, env, model_name, name)
                if value == resolved:
                    out.append([name, operator, old])
                    continue
        if old and is_token(value) and value.get(TOKEN_KEY) == "relative_date":
            out.append([name, operator, value])
            continue
        out.append([name, operator, value])
    return out


def _coerce_editor_value(value):
    if is_token(value):
        return value
    # Legacy Char form embedded a dict literal; safe_eval may yield a dict.
    if isinstance(value, dict) and is_token(value):
        return value
    if isinstance(value, str):
        relative = _parse_virtual_date_string(value)
        if relative is not None:
            return relative
        if value.startswith("__de__.relative_date."):
            # __de__.relative_date.days_ago.7
            parts = value.split(".")
            when = parts[2] if len(parts) > 2 else "today"
            days = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
            return token("relative_date", when=when, days=days)
        if value.startswith("{") and '"__de__"' in value:
            try:
                parsed = json.loads(value)
                if is_token(parsed):
                    return parsed
            except Exception:
                pass
    return value


def _parse_virtual_date_string(value):
    """Map DomainSelector virtual dates (``today``, ``today -7d``) to tokens."""
    text = (value or "").strip()
    if not text.startswith("today"):
        return None
    if text == "today":
        return token("relative_date", when="today")
    if text == "today +1d":
        return token("relative_date", when="end_of_today")
    # today -Nd / today +Nd
    rest = text[len("today") :].strip()
    if not rest:
        return token("relative_date", when="today")
    sign = rest[0]
    if sign not in "-+" or not rest.endswith("d"):
        return None
    try:
        days = int(rest[1:-1].strip())
    except ValueError:
        return None
    if days < 0:
        return None
    if sign == "-":
        return token("relative_date", when="days_ago", days=days)
    return token("relative_date", when="days_ahead", days=days)
