# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Dotted many2one paths from an aggregated model back to a dashboard card.

Stored on blueprints/slots as Char (``partner_id`` or ``product_id.categ_id``).
Multi-hop paths group on the first segment and fold hop→host in Python.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def split_path(path):
    """Return non-empty path segments."""
    if not path:
        return []
    return [part for part in str(path).split(".") if part]


def first_hop(path):
    parts = split_path(path)
    return parts[0] if parts else False


def is_direct(path):
    """True when the path is a single many2one (or empty)."""
    return len(split_path(path)) <= 1


def domain_leaf(path, host_ids, operator=None):
    """Domain leaf ``(path, 'in'|'=', ids)`` for the given cards."""
    if not path or not host_ids:
        return False
    ids = list(host_ids)
    if operator is None:
        operator = "in" if len(ids) != 1 else "="
    value = ids if operator == "in" else ids[0]
    return (path, operator, value)


def validate_path(env, source_model, path, target_model):
    """Ensure ``path`` is many2one-only and ends on ``target_model``.

    Raises :class:`~odoo.exceptions.ValidationError` on failure.
    """
    parts = split_path(path)
    if not parts:
        raise ValidationError("Relation path is empty.")
    if not source_model or source_model not in env:
        raise ValidationError("Unknown source model for relation path.")
    if not target_model:
        raise ValidationError("Card model is missing for relation path.")

    current = source_model
    for name in parts:
        Model = env[current]
        field = Model._fields.get(name)
        if field is None:
            raise ValidationError(
                "Field %(field)s does not exist on %(model)s."
                % {"field": name, "model": current}
            )
        if field.type != "many2one":
            raise ValidationError(
                "%(field)s on %(model)s must be a link to one record."
                % {"field": field.string or name, "model": current}
            )
        current = field.comodel_name
        if not current:
            raise ValidationError(
                "%(field)s on %(model)s has no related model."
                % {"field": name, "model": Model._name}
            )
    if current != target_model:
        raise ValidationError(
            "Path ends on %(landed)s, not on the card's model %(target)s."
            % {"landed": current, "target": target_model}
        )
    return True


def map_first_hop_to_hosts(env, source_model, path, host_ids):
    """``{first_hop_id: [host_id, ...]}`` for folding a read_group.

    Direct paths are the identity map. Multi-hop searches the intermediate
    model with the remaining dotted field.
    """
    host_ids = list(host_ids)
    parts = split_path(path)
    if not host_ids or not parts:
        return {}
    if len(parts) == 1:
        return {host_id: [host_id] for host_id in host_ids}

    first_name = parts[0]
    rest = parts[1:]
    if not source_model or source_model not in env:
        return {}
    Source = env[source_model]
    first_field = Source._fields.get(first_name)
    if not first_field or first_field.type != "many2one":
        return {}
    mid_model = first_field.comodel_name
    if not mid_model or mid_model not in env:
        return {}
    Mid = env[mid_model]
    rest_field = ".".join(rest)
    try:
        mids = Mid.search([(rest_field, "in", host_ids)])
    except Exception:
        _logger.warning(
            "Relation path %s.%s failed to resolve intermediates",
            source_model,
            path,
            exc_info=True,
        )
        return {}

    mapping = {}
    for mid in mids:
        host = mid
        for name in rest:
            host = host[name]
            if not host:
                host = False
                break
        if not host:
            continue
        host_id = host.id if hasattr(host, "id") else host
        if host_id in host_ids:
            mapping.setdefault(mid.id, []).append(host_id)
    return mapping


@dataclass(frozen=True)
class RelationPathInfo:
    """Runtime handle for a multi-hop Char path (duck-types the old path model)."""

    env: object
    path: str
    source_model: str

    @property
    def domain_field(self):
        return self.path

    @property
    def first_hop_field(self):
        return first_hop(self.path)

    @property
    def is_direct(self):
        return is_direct(self.path)

    def domain_leaf(self, host_ids, operator=None):
        return domain_leaf(self.path, host_ids, operator=operator)

    def map_first_hop_to_hosts(self, host_ids):
        return map_first_hop_to_hosts(
            self.env, self.source_model, self.path, host_ids
        )

    def __bool__(self):
        return bool(self.path)
