# -*- coding: utf-8 -*-

from odoo import models


class IrModel(models.Model):
    _inherit = "ir.model"

    """
    Extension of `ir.model` providing SQL helper utilities
    for building ORDER BY clauses with proper table aliasing
    and translation (i18n) support.

    This is primarily used by dashboard and reporting queries
    that require deterministic ordering across translated
    and relational fields.
    """

    def _get_table_alias_map(self):
        """
        Define table alias mapping rules for ORDER BY clauses.

        Some fields belong logically to related tables
        (e.g. product names stored on product_template).
        This mapping allows ORDER BY expressions to use
        the correct SQL table alias automatically.

        :return: dict mapping model → alias configuration
        """
        # Configuration defining which fields require table alias substitution
        return {
            "product_product": {
                "fields": ["is_favorite", "name"],
                "alias_table": "product_template",
            },
            "res_users": {
                "fields": ["name"],
                "alias_table": "res_partner",
            },
        }

    def _get_table_alias_for_field(self, table, field, table_alias_map):
        """
        Resolve the correct SQL table alias for a given order field.

        If the field is configured to be ordered via a related
        table, the corresponding alias table is returned.
        Otherwise, the base table is used.

        :param table: base SQL table name
        :param field: field name (may include ordering direction)
        :param table_alias_map: alias configuration mapping
        :return: resolved SQL table name or alias
        """
        # Strip ordering direction and extract raw field name
        field_name = field.strip().split()[0]
        # Use alias table if field is mapped for the given model
        if (
            table in table_alias_map
            and field_name in table_alias_map[table]["fields"]
        ):
            return table_alias_map[table]["alias_table"]
        return table

    def _build_order_expr(self, model, table, field, lang, table_alias_map):
        """
        Build a single SQL ORDER BY expression with i18n support.

        This method:
            - Resolves correct table aliases
            - Detects translatable fields
            - Applies JSONB language extraction when required
            - Preserves explicit ordering direction (ASC / DESC)

        :param model: technical model name
        :param table: base SQL table name
        :param field: order field with optional direction
        :param lang: user language code
        :param table_alias_map: alias configuration mapping
        :return: SQL ORDER BY expression string
        """
        # Separate field name and ordering direction
        parts = field.strip().rsplit(" ", 1)
        field_name = parts[0]
        direction = parts[1] if len(parts) > 1 else ""

        # Resolve table alias based on configured mappings
        table_alias = self._get_table_alias_for_field(
            table, field_name, table_alias_map
        )
        column = field_name.split(".")[-1]

        # Check if field is translatable (JSONB stored)
        translate = self.env[model].fields_get(column)[column].get("translate")
        if translate:
            expr = f"{table_alias}.{column} ->> '{lang}'"
        else:
            expr = f"{table_alias}.{column}"

        # Append ordering direction if provided
        return f"{expr} {direction}".strip()

    def _get_model_table_info(self, model):
        """
        Resolve SQL table and ORDER BY metadata for a model.

        This helper prepares all SQL-related information
        required to query a model with correct ordering,
        including:
            - database table name
            - translated ORDER BY clause
            - alias handling for related fields

        :param model: technical model name
        :return: dict with keys: model, table, order
        """
        # Resolve current user's language (fallback to en_US)
        lang = self.env.user.lang or "en_US"
        table_alias_map = self._get_table_alias_map()

        # Fetch ir.model entry to validate model existence
        ir_model = self.sudo().search([("model", "=", model)], limit=1)
        if not ir_model:
            return {"model": "", "table": "", "order": ""}

        model_obj = self.env[ir_model.model]
        # Build ORDER BY clause using model's _order definition
        order_clause = ", ".join(
            self._build_order_expr(
                model_obj._name,
                model_obj._table,
                field,
                lang,
                table_alias_map,
            )
            for field in model_obj._order.split(",")
        )

        return {
            "model": model_obj._name,
            "table": model_obj._table,
            "order": order_clause,
        }
