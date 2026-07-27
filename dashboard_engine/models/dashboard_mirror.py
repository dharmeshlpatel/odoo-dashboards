# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Pairing of relational configuration pickers with durable technical mirrors.

A blueprint is configured by picking records — a model, a field, an action —
so nobody has to type ``crm.lead`` or ``create_date:month`` by hand. What the
runtime reads, however, is still the technical name held in a plain text
field.

Keeping both is deliberate:

- The **picker** is the user interface. It validates, it scopes choices to the
  chosen model, and it makes the configuration browsable.
- The **mirror** is what survives. Database ids mean nothing in another
  database, so export/import and packaged blueprint templates travel on the
  technical name. When a module is uninstalled its ``ir.model`` rows vanish
  and the picker is emptied, but the mirror still records what the blueprint
  was pointing at, which is what lets the blueprint go quietly inactive
  instead of breaking, and lets it heal itself if the module comes back.

The mirror is therefore the source of truth: pickers are computed from it and
write back to it.
"""
from odoo import api, models

# Fields every mirror-mixin model carries that never travel in a template
# export: bookkeeping (ids, audit trail) and generated-artifact caches that
# get recomputed on publish anyway.
_PORTABLE_EXCLUDE = frozenset({
    "id", "display_name", "create_date", "create_uid", "write_date",
    "write_uid", "__last_update",
    "generated_arch_hash",
})


class DashboardMirrorMixin(models.AbstractModel):
    _name = "dashboard.mirror.mixin"
    _description = "Dashboard Configuration Mirror Helpers"

    def _portable_field_names(self):
        """Field names safe to travel across databases (Phase 12).

        Every model using this mixin stores its real configuration on
        plain technical fields (Char/Selection/Boolean/…) and exposes
        Many2one/Many2many *pickers* computed from them (see the module
        docstring above). Database ids mean nothing in another database,
        so a template export keeps only the technical side: every stored,
        non-relational field except bookkeeping columns. Callers that hold
        a genuine exception (e.g. a mirror that is itself the source of
        truth rather than a computed pointer) resolve it separately.
        """
        self.ensure_one()
        names = []
        for name, field in self._fields.items():
            if name in _PORTABLE_EXCLUDE:
                continue
            if field.type in (
                "many2one", "many2many", "one2many", "reference", "binary",
            ):
                continue
            if field.inverse:
                # A writable "picker" mirror recomputed from a plain
                # technical field elsewhere (see module docstring above) —
                # e.g. ``graph_groupby_granularity`` alongside
                # ``graph_groupby_field_id``/``graph_groupby``. Odoo treats
                # any value passed for such a field on create/write as user
                # input and calls its inverse, which can overwrite the real
                # technical field with an empty value. Never round-trip
                # this side, even though it is a plain Selection/Char.
                continue
            if field.compute and not field.store:
                continue
            names.append(name)
        return names

    def _portable_vals(self, exclude=()):
        """This record's portable fields as a plain ``{name: value}`` dict."""
        self.ensure_one()
        exclude = set(exclude)
        return {
            name: self[name]
            for name in self._portable_field_names()
            if name not in exclude
        }

    @api.model
    def _mirror_model(self, model_name):
        """``ir.model`` for a technical model name, empty when absent."""
        Model = self.env["ir.model"].sudo()
        if not model_name:
            return Model.browse()
        return Model.search([("model", "=", model_name)], limit=1)

    @api.model
    def _mirror_field(self, model_name, field_name):
        """``ir.model.fields`` for a model/field pair, empty when absent."""
        Field = self.env["ir.model.fields"].sudo()
        if not model_name or not field_name:
            return Field.browse()
        return Field.search(
            [("model", "=", model_name), ("name", "=", field_name)], limit=1
        )

    @api.model
    def _mirror_record(self, model_name, xmlid):
        """Record behind an xmlid, empty when it is missing or of another model."""
        Model = self.env[model_name]
        if not xmlid or "." not in xmlid:
            return Model.browse()
        record = self.env.ref(xmlid, raise_if_not_found=False)
        if not record or record._name != model_name:
            return Model.browse()
        return Model.browse(record.id)

    @api.model
    def _mirror_xmlid(self, record):
        """External id of a record, or False when it has none."""
        if not record:
            return False
        return record.get_external_id().get(record.id) or False

    @api.model
    def _mirror_records(self, model_name, csv_xmlids):
        """Records behind a comma-separated list of xmlids, skipping missing ones."""
        records = self.env[model_name].browse()
        for xmlid in self._mirror_names(csv_xmlids):
            records |= self._mirror_record(model_name, xmlid)
        return records

    @api.model
    def _mirror_xmlids(self, records):
        """Comma-separated external ids for a recordset."""
        if not records:
            return False
        mapping = records.get_external_id()
        found = [mapping[record.id] for record in records if mapping.get(record.id)]
        return ",".join(sorted(found)) or False

    @api.model
    def _mirror_names(self, csv_value):
        return [part.strip() for part in (csv_value or "").split(",") if part.strip()]

    def _resolve_stale_mirrors(self, specs):
        """Force a recompute of pickers whose mirror is set but resolved empty.

        ``specs`` is a list of ``(picker_field, source_fields)`` pairs. A
        mirror goes stale when the module/model/field/action it names was
        not installed yet when the picker was last computed; nothing marks
        the record dirty when that module installs later, so nobody ever
        recomputes it on its own. Called at registry boot (see
        ``_register_hook``) so the picker heals itself once its target
        exists, the same way a freshly (re)installed module's own data
        would have resolved it the first time.
        """
        for rec in self:
            dirty = []
            for picker_field, source_fields in specs:
                if rec[source_fields[0]] and not rec[picker_field]:
                    dirty.extend(source_fields)
            if dirty:
                rec.modified(list(dict.fromkeys(dirty)))
                rec.flush_recordset()
