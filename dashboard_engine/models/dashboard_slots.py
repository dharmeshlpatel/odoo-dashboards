# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Generic dashboard slot renderer (server side).

Serializes the dashboard action configuration into a JSON payload
(``dashboard_slots``) that the ``dashboard_slots`` OWL field widget
renders generically. Dashboard modules only declare a ``ui`` block on
their action config entries — no per-module kanban XML is required.

``ui`` block schema (all keys optional unless stated)::

    "ui": {
        "sequence": 10,             # ordering inside the slot
        "label": "Open Opportunity",        # str or callable(record)
        "label_plural": "Open Opportunities",  # used when count != 1
        "count_field": "open_opportunity_count",  # record field
        "amount_field": "open_opportunity_amount",  # monetary field
        "icon": "fa-star",          # bottom buttons only
        "style": "danger",          # visual emphasis (default: "default")
        "group": "crm.group_use_lead",  # server-side group filter
        "method": "action_view_opportunity",  # overrides action_name
        "show_if_zero": True,       # keep item when count is falsy
        "context": {...},           # extra ctx, values may be callables
    }

Slot mapping (config section → payload key):

- ``actions.primary_right``  → ``kpis``
- ``actions.bottom_block``   → ``buttons``
- ``actions.menu.views/new/reports`` → ``menu.views/new/reports``

Entries without a ``ui`` block are ignored, so legacy dashboards that
still render through hand-written XML keep working unchanged.
"""
from odoo import models

MENU_SECTIONS = ("views", "new", "reports")


class BaseDashboardGraphMixin(models.AbstractModel):
    """Config-dict slot builder for models that declare a dashboard config.

    The ``dashboard_slots`` field itself is declared on ``base`` (see
    models/base.py) and is normally filled from a blueprint. These helpers
    remain the builder for models that carry a hand-written config dict.
    """

    _inherit = "base.dashboard.graph.mixin"

    def _get_dashboard_slots(self):
        """Build the generic slot payload for this record."""
        self.ensure_one()
        actions = self._get_dashboard_config_value("actions") or {}
        menu_cfg = actions.get("menu", {})
        return {
            "kpis": self._get_dashboard_slot_items(
                actions.get("primary_right", {})
            ),
            "buttons": self._get_dashboard_slot_items(
                actions.get("bottom_block", {})
            ),
            "menu": {
                section: self._get_dashboard_slot_items(
                    menu_cfg.get(section, {})
                )
                for section in MENU_SECTIONS
            },
        }

    def _get_dashboard_slot_items(self, section_cfg):
        """Convert one config section into a sorted list of slot items."""
        self.ensure_one()
        if not isinstance(section_cfg, dict):
            return []
        user = self.env.user
        items = []
        for key, cfg in section_cfg.items():
            if not isinstance(cfg, dict):
                continue
            ui = cfg.get("ui")
            if not isinstance(ui, dict):
                # Entry not migrated to the generic renderer yet.
                continue
            group = ui.get("group")
            if group and not user.has_group(group):
                continue

            item = {
                "key": key,
                "sequence": ui.get("sequence", 100),
                "method": ui.get("method") or cfg.get("action_name"),
                "style": ui.get("style", "default"),
            }
            if ui.get("icon"):
                item["icon"] = ui["icon"]

            count = None
            if ui.get("count_field"):
                count = self[ui["count_field"]] or 0
                if not count and not ui.get("show_if_zero"):
                    continue
                item["count"] = count

            item["label"] = self._resolve_dashboard_slot_label(ui, count)

            if ui.get("amount_field"):
                item["amount"] = self[ui["amount_field"]] or 0
                item["currency_id"] = self.currency_id.id

            context = ui.get("context")
            if isinstance(context, dict):
                item["context"] = {
                    ctx_key: self._resolve_dashboard_slot_value(ctx_value)
                    for ctx_key, ctx_value in context.items()
                }

            items.append(item)

        items.sort(key=lambda item: item["sequence"])
        return items

    def _resolve_dashboard_slot_label(self, ui, count):
        """Pick singular/plural label and resolve callables."""
        label = ui.get("label")
        if count is not None and count != 1 and ui.get("label_plural"):
            label = ui["label_plural"]
        return self._resolve_dashboard_slot_value(label) or ""

    def _resolve_dashboard_slot_value(self, value):
        """Resolve callable config values against the current record."""
        return value(self) if callable(value) else value
