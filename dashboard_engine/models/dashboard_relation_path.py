# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Named multi-hop links from an aggregated model back to a dashboard card.

A path is an ordered chain of many2one fields. For Product Category cards that
chart Sales Order Lines the hops are ``product_id`` then ``categ_id``, which
compiles to the domain leaf ``('product_id.categ_id', 'in', category_ids)``.

``formatted_read_group`` can only group by fields local to the aggregated
model. Multi-hop paths therefore group on the **first hop** and fold the
hop-to-host mapping in Python. One query still covers every visible card.
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DashboardRelationPath(models.Model):
    _name = "dashboard.relation.path"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Relation Path"
    _order = "name, id"

    name = fields.Char(required=True, translate=True)
    source_model_id = fields.Many2one(
        "ir.model",
        required=True,
        ondelete="cascade",
        string="From",
        help="Model being counted or charted, e.g. Sales Order Line.",
    )
    source_model = fields.Char(
        related="source_model_id.model",
        store=True,
        readonly=True,
        string="From (technical)",
    )
    target_model_id = fields.Many2one(
        "ir.model",
        required=True,
        ondelete="cascade",
        string="To the card",
        help="Model shown as kanban cards, e.g. Product Category.",
    )
    target_model = fields.Char(
        related="target_model_id.model",
        store=True,
        readonly=True,
        string="To the card (technical)",
    )
    hop_ids = fields.One2many(
        "dashboard.relation.hop",
        "path_id",
        string="Steps",
        copy=True,
    )
    domain_field = fields.Char(
        compute="_compute_compiled",
        store=True,
        help="Dotted field path used in domains, e.g. product_id.categ_id.",
    )
    first_hop_field = fields.Char(
        compute="_compute_compiled",
        store=True,
        help="Local field on the source model used for read_group.",
    )
    is_direct = fields.Boolean(
        compute="_compute_compiled",
        store=True,
        help="True when a single hop already lands on the card's model.",
    )
    hop_count = fields.Integer(compute="_compute_compiled", store=True)

    @api.depends(
        "hop_ids.sequence",
        "hop_ids.field_name",
        "hop_ids.field_id",
        "source_model",
        "target_model",
    )
    def _compute_compiled(self):
        for path in self:
            hops = path.hop_ids.sorted("sequence")
            names = [hop.field_name for hop in hops if hop.field_name]
            path.hop_count = len(names)
            path.domain_field = ".".join(names) if names else False
            path.first_hop_field = names[0] if names else False
            path.is_direct = len(names) == 1

    @api.constrains("hop_ids", "source_model_id", "target_model_id")
    def _check_hops(self):
        for path in self:
            hops = path.hop_ids.sorted("sequence")
            # Empty paths are allowed while the form is being filled in.
            if not hops:
                continue
            current_model = path.source_model
            for hop in hops:
                if not hop.field_id:
                    raise ValidationError(
                        _("Every step of %(path)s needs a field.", path=path.name)
                    )
                if hop.field_id.ttype != "many2one":
                    raise ValidationError(
                        _(
                            "%(field)s on %(path)s must be a link to one record.",
                            field=hop.field_id.field_description,
                            path=path.name,
                        )
                    )
                if hop.field_id.model != current_model:
                    raise ValidationError(
                        _(
                            "%(field)s belongs to %(model)s, but the previous "
                            "step of %(path)s lands on %(current)s.",
                            field=hop.field_id.field_description,
                            model=hop.field_id.model,
                            path=path.name,
                            current=current_model,
                        )
                    )
                current_model = hop.field_id.relation
            if current_model != path.target_model:
                raise ValidationError(
                    _(
                        "%(path)s ends on %(landed)s, not on the card's "
                        "model %(target)s.",
                        path=path.name,
                        landed=current_model,
                        target=path.target_model,
                    )
                )

    def domain_leaf(self, host_ids, operator=None):
        """Domain leaf that keeps records belonging to the given cards."""
        self.ensure_one()
        if not self.domain_field or not host_ids:
            return False
        ids = list(host_ids)
        if operator is None:
            operator = "in" if len(ids) != 1 else "="
        value = ids if operator == "in" else ids[0]
        return (self.domain_field, operator, value)

    def map_first_hop_to_hosts(self, host_ids):
        """``{first_hop_id: [host_id, ...]}`` for folding a read_group.

        Direct paths are the identity map: the first hop *is* the host id, so
        no extra query is needed.
        """
        self.ensure_one()
        host_ids = list(host_ids)
        if not host_ids or not self.hop_ids:
            return {}
        if self.is_direct:
            return {host_id: [host_id] for host_id in host_ids}

        hops = self.hop_ids.sorted("sequence")
        first = hops[0]
        rest = hops[1:]
        mid_model = first.field_id.relation
        if mid_model not in self.env:
            return {}
        Mid = self.env[mid_model]
        rest_field = ".".join(hop.field_name for hop in rest)
        try:
            mids = Mid.search([(rest_field, "in", host_ids)])
        except Exception:
            _logger.warning(
                "Dashboard relation path %s failed to resolve intermediates",
                self.name,
                exc_info=True,
            )
            return {}

        mapping = {}
        for mid in mids:
            host = mid
            for hop in rest:
                host = host[hop.field_name]
                if not host:
                    host = False
                    break
            if not host:
                continue
            host_id = host.id if hasattr(host, "id") else host
            if host_id in host_ids:
                mapping.setdefault(mid.id, []).append(host_id)
        return mapping


class DashboardRelationHop(models.Model):
    _name = "dashboard.relation.hop"
    _inherit = ["dashboard.mirror.mixin"]
    _description = "Dashboard Relation Path Step"
    _order = "sequence, id"

    path_id = fields.Many2one(
        "dashboard.relation.path", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    # Model the field picker should offer. For the first hop this is the
    # path's source; afterwards it is wherever the previous hop landed.
    current_model = fields.Char(compute="_compute_current_model")
    field_name = fields.Char()
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Follows",
        compute="_compute_field_id",
        inverse="_inverse_field_id",
        store=True,
        readonly=False,
        ondelete="cascade",
        required=True,
    )

    @api.depends(
        "path_id.source_model",
        "path_id.hop_ids.sequence",
        "path_id.hop_ids.field_id",
        "sequence",
    )
    def _compute_current_model(self):
        for hop in self:
            path = hop.path_id
            if not path:
                hop.current_model = False
                continue
            earlier = path.hop_ids.filtered(
                lambda other, h=hop: other.sequence < h.sequence
                or (other.sequence == h.sequence and other.id and h.id and other.id < h.id)
            ).sorted("sequence")
            if not earlier:
                hop.current_model = path.source_model
            else:
                last = earlier[-1]
                hop.current_model = last.field_id.relation if last.field_id else False

    @api.depends("field_name", "current_model")
    def _compute_field_id(self):
        for hop in self:
            hop.field_id = hop._mirror_field(hop.current_model, hop.field_name)

    def _inverse_field_id(self):
        for hop in self:
            hop.field_name = hop.field_id.name or False

    @api.constrains("field_id", "path_id", "sequence")
    def _check_path_chain(self):
        # Creating or reordering a step must re-validate the whole path;
        # the path's own constrains do not always fire on inverse O2M writes.
        self.mapped("path_id")._check_hops()
