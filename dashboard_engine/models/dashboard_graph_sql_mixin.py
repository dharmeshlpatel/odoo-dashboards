# -*- coding: utf-8 -*-
import re
from odoo import models
from odoo.tools import Query

GRAPH_GROUP = ["day", "week", "month", "quarter", "year"]


class BaseDashboardGraphSQLMixin(models.AbstractModel):
    """
    SQL-focused mixin responsible for building, joining, and executing
    dashboard graph queries.

    This class encapsulates:
    - SELECT / FROM / JOIN construction
    - GROUP BY and ORDER BY logic
    - Related-field joins
    - Many2many expansion
    - Query parameter preparation

    It is intentionally isolated to keep SQL logic separate
    from graph formatting and UI concerns.
    """

    _name = "base.dashboard.graph.sql.mixin"
    _inherit = ["base.dashboard.mixin"]
    _description = "Dashboard Graph SQL Mixin"

    def _prefix_sql_columns(self, sql, table):
        """
        Prefix unqualified column names with table name.

        Rules:
        - user_id = %s        -> table.user_id = %s
        - type = 'lead'       -> table.type = 'lead'
        - preserve %s, %(key)s, quoted strings, SQL keywords
        """

        protected = {}
        counter = 0

        def protect(match):
            nonlocal counter
            key = f"__PROT_{counter}__"
            protected[key] = match.group(0)
            counter += 1
            return key

        # Protect named placeholders: %(uid)s
        sql = re.sub(r"%\([a-zA-Z_][a-zA-Z0-9_]*\)s", protect, sql)

        # Protect positional placeholders: %s
        sql = re.sub(r"%s", protect, sql)

        # Protect quoted strings: 'lead', 'some value'
        sql = re.sub(r"'([^']|'')*'", protect, sql)

        # Protect escaped quoted strings: \'value\'
        sql = re.sub(r"\\'([^\\']|\\\\')*\\'", protect, sql)

        # Protect numeric literals
        sql = re.sub(r"\b\d+\b", protect, sql)

        # Prefix only column names on the LEFT side of comparison operators
        def prefix_lhs(match):
            column = match.group("column")
            operator = match.group("op")
            return f"{table}.{column} {operator} "

        sql = re.sub(
            r"(?P<column>\b[a-zA-Z_][a-zA-Z0-9_]*\b)\s*(?P<op>=|!=|<>|>=|<=|<|>|LIKE|IN|IS)\s*",
            prefix_lhs,
            sql,
            flags=re.IGNORECASE,
        )

        # Restore protected values
        for key, value in protected.items():
            sql = sql.replace(key, value)

        return sql

    def _get_group_by(self, group_by, based_on):
        """
        Build the group-by expression list for a given field.

        This helper normalizes group-by inputs so they can be safely
        consumed by graph query builders.

        Special handling:
            - If the group-by value represents a date period
              (day, week, month, quarter, year), it is expressed
              in the `<base_field>:<period>` format.
            - All other group-by values are returned as-is.

        :param group_by: Group-by key or period identifier
        :param based_on: Base date/datetime field name
        :return: list containing normalized group-by expression(s)
        """
        # Handle date-period group-by values (day/week/month/quarter/year)
        if group_by in GRAPH_GROUP:
            # Build period-based group-by expression using base field
            return ["%s:%s" % (based_on, group_by)]
        # Fallback: return raw group-by field
        return [group_by]

    def _get_compute_field_query(self, model, field_id):
        """
        Build SQL query components for a computed group-by field.

        This helper delegates to the model’s internal
        `_read_group_groupby` implementation to generate the
        SQL fragments required for grouping on computed fields
        (such as activity_state or company_currency).

        It returns both:
            - the generated Query object containing SQL code and parameters
            - the base Query object used during construction

        These components are later merged into the main dashboard
        graph SQL query, along with their parameters.

        :param model: Odoo model on which the group-by is computed
        :param field_id: ir.model.fields record representing the computed field
        :return: tuple (query, base_query)
        """
        # Initialize base Query object for the target model table
        que_obj = Query(self.env, model._table, "")
        # Let Odoo build SQL fragments for computed group-by field
        query = model._read_group_groupby(
            alias=model._table, groupby_spec=field_id.name, query=que_obj
        )
        return query, que_obj

    def _graph_x_date_period_sql(
        self,
        field,
        graph_table,
        tz_offset,
        is_primary,
    ):
        """
        Build SQL expressions for date-period groupings.
        """
        date_field, group = field.get_date_period().split(":")

        # Build unique alias using the source date field name to prevent
        # ambiguity when multiple group-by fields share the same period
        # type (e.g., create_date:day and date_deadline:day).
        group_alias = f"{date_field}_{group}"
        year_alias = f"{date_field}_year"

        def alias(expr, name):
            return expr if is_primary else f"{expr} AS {name}"

        year_expr = "CAST(EXTRACT(YEAR FROM %s.%s) AS INTEGER)" % (
            graph_table,
            date_field,
        )

        if group == "day":
            expr = "DATE(%s.%s::TIMESTAMP - make_interval(secs => %s))" % (
                graph_table,
                date_field,
                tz_offset,
            )
            return [alias(expr, group_alias)]

        if group in ("week", "month"):
            expr = (
                "CAST(EXTRACT(%s FROM %s.%s::TIMESTAMP - make_interval(secs => %s)) AS INTEGER)"
                % (group, graph_table, date_field, tz_offset)
            )
            return [
                alias(expr, group_alias),
                f"{year_expr} AS {year_alias}",
            ]

        if group == "quarter":
            expr = (
                "'Q' || CAST(EXTRACT(QUARTER FROM %s.%s::TIMESTAMP - make_interval(secs => %s)) AS INTEGER)"
                " || ' ' || to_char(%s.%s,'yyyy')"
                % (
                    graph_table,
                    date_field,
                    tz_offset,
                    graph_table,
                    date_field,
                )
            )
            return [
                alias(expr, group_alias),
                f"{year_expr} AS {year_alias}",
            ]

        # year
        return [alias(year_expr, year_alias)]

    def _graph_x_field_sql(
        self,
        field,
        model,
        graph_table,
        primary_field,
        tz_offset,
        ctx,
    ):
        """
        Return a list of SQL SELECT expressions for a single group-by field.
        """
        field_name = field.name
        is_primary = field == primary_field

        # Computed fields (model-level SQL generation required)
        if field_name in self.env.user._get_graph_computed_groupby_fields():
            sql_query, _ = self._get_compute_field_query(
                model=model, field_id=field
            )
            ctx.setdefault("params", [])
            ctx["params"] += sql_query.params
            code = sql_query.code.replace("%s", "%%s")
            return [code if is_primary else f"({code}) AS {field_name}"]

        # Many2many
        if field.ttype == "many2many":
            select_query, _, _ = self._get_m2m_values(
                table=graph_table,
                field=field,
            )
            return [select_query]

        # Related fields
        if field.related:
            column, _, _ = self._get_related_column_joins(
                base_model=model._name,
                related_path=field.related.split("."),
                field_id=field,
                is_alias=is_primary,
            )
            return [column]

        # Date period fields
        if field.ttype == "char" and field.is_date_period():
            return self._graph_x_date_period_sql(
                field=field,
                graph_table=graph_table,
                tz_offset=tz_offset,
                is_primary=is_primary,
            )

        # Default: simple column
        return [f"{graph_table}.{field_name}"]

    def _get_aggregate_spec(self):
        user = self.env.user
        measure = user._get_graph_measure()

        if measure == "__count":
            return "__count"

        return f"{measure}:{user._get_graph_measure_aggregator()}"

    def _graph_x_query(self, ctx):
        """
        Build SQL SELECT expressions for X-axis grouping fields.
        """
        model_name = self._get_graph_model()
        GraphModel = self.env[model_name]
        graph_table = GraphModel._table

        groupby_fields = self.env.user._get_graph_groupby()
        tz_offset = self.env.context.get("webclient_tz_offset", 0)

        x_query = []
        seen = set()
        primary_field = groupby_fields[:1]

        for field in groupby_fields:
            for expr in self._graph_x_field_sql(
                field=field,
                model=GraphModel,
                graph_table=graph_table,
                primary_field=primary_field,
                tz_offset=tz_offset,
                ctx=ctx,
            ):
                if expr not in seen:
                    seen.add(expr)
                    x_query.append(expr)

        return x_query

    def _graph_y_query(self):
        """
        CRM dashboard override for graph Y-axis aggregation.
        """
        model = self.env[self._get_graph_model()]
        query = Query(self.env, model._table, "")

        aggregate_spec = self._get_aggregate_spec()

        sql = model._read_group_select(aggregate_spec, query)
        from_clause = query.from_clause
        return sql.code, from_clause.code, from_clause.params

    def _extra_join_sql_conditions(self):
        """
        Returns extra SQL join conditions for specific fields.

        Supports two formats in the config dict:

        **Raw SQL (legacy):**::

            "extra_join_sql_conditions": {
                "product_id": " LEFT JOIN product_template"
                              " ON product_template.id"
                              " = product_product"
                              ".product_tmpl_id",
            }

        **Declarative (preferred):**::

            "extra_join_sql_conditions": {
                "product_id": {
                    "join_table": "product_template",
                    "on_left": "product_product"
                               ".product_tmpl_id",
                    "on_right": "product_template.id",
                },
            }

        Declarative entries are auto-compiled into SQL.
        """
        raw = (
            self._get_dashboard_config_value("extra_join_sql_conditions") or {}
        )
        result = {}
        for field_name, spec in raw.items():
            if isinstance(spec, str):
                # Legacy raw SQL — use as-is
                result[field_name] = spec
            elif isinstance(spec, dict):
                # Declarative — compile to SQL
                result[field_name] = (
                    " LEFT JOIN {table}" " ON {on_right} = {on_left}"
                ).format(
                    table=spec["join_table"],
                    on_left=spec["on_left"],
                    on_right=spec["on_right"],
                )
            else:
                result[field_name] = spec
        return result

    def _get_related_column_joins(
        self, base_model, related_path, field_id, is_alias=False
    ):
        """
        Builds JOINs for related fields and returns column expression, joins, and groupby.
        """
        joins = []
        table_alias = field_id.name
        current_model = self.env[base_model]
        prev_alias = current_model._table
        for idx, field_name in enumerate(related_path):
            field = current_model._fields[field_name]

            if idx == len(related_path) - 1:
                expr = (
                    f"{prev_alias}.{field.name}"
                    if is_alias
                    else f"{prev_alias}.{field.name} AS {table_alias}"
                )
                return expr, joins, f"{prev_alias}.{field.name}"

            rel_model = self.env[field.comodel_name]
            rel_table = rel_model._table
            alias = f"{prev_alias}_{field.name}"

            joins.append(
                {
                    "alias": alias,
                    "table": rel_table,
                    "on": f"{alias}.id = {prev_alias}.{field.name}",
                }
            )

            current_model = rel_model
            prev_alias = alias

    def _prepare_query_context(self, field):
        """
        Collects model, table, join, and condition metadata for query building.
        """
        IrModel = self.env["ir.model"]
        dashboard_graph_model = self._get_graph_model()
        GraphModel = self.env[dashboard_graph_model]
        graph_table = GraphModel._table
        dashboard_graph_group = self.env.user._get_graph_groupby()
        related_joins = []

        for field in dashboard_graph_group:
            if field.related and not field.store:
                related_path = field.related.split(".")
                _, joins, _ = self._get_related_column_joins(
                    base_model=dashboard_graph_model,
                    related_path=related_path,
                    field_id=field,
                )
                related_joins.extend(joins)

        join_table_metadata = {}
        for group in dashboard_graph_group:
            join_table_metadata.update(
                {group.name: IrModel._get_model_table_info(group.relation)}
            )
        where_clause = self._get_where_clause(model=GraphModel)
        graph_model_record_ids = self._get_hierarchy_record_ids()
        return {
            "GraphModel": GraphModel,
            "graph_table": graph_table,
            "dashboard_graph_group": dashboard_graph_group,
            "join_table_metadata": join_table_metadata,
            "related_joins": related_joins,
            "graph_model_record_ids": graph_model_record_ids,
            "where_clause": where_clause,
        }

    def _get_hierarchy_record_ids(self):
        """
        Return hierarchical record IDs for the graph model.

        IMPORTANT:
        `self` is a dashboard record, NOT a record of the graph model.
        """
        self.ensure_one()
        # If dashboard model supports hierarchy, include self.id + children
        domain = self._get_dashboard_hierarchy_domain()
        if domain:
            return self.search(domain).ids
        return [self.id]

    def _build_field_condition(self, field):
        """
        Builds SQL condition for target field values.
        """
        return f" WHERE %(table)s.{field} IN %(field_value)s"

    def _get_m2m_values(self, table, field):
        """
        Returns SELECT, JOIN, and GROUP BY SQL for many2many fields.
        """
        rel_table = field.relation_table
        rel_model = self.env[field.relation]
        rel_model_table = rel_model._table
        rel_alias = f"{table}__{field.name}"
        model_alias = f"{rel_model_table}"
        select_query = f"{rel_alias}.{field.column2}"
        join_query = f" LEFT JOIN {rel_table} AS {rel_alias} ON {rel_alias}.{field.column1} = {table}.id LEFT JOIN {rel_model_table} AS {model_alias} ON {model_alias}.id = {rel_alias}.{field.column2}"
        groupby_query = f"{rel_alias}.{field.column2}"
        return select_query, join_query, groupby_query

    def _build_groupby_orderby_clause(self, ctx, dashboard_graph_group):
        """
        Build GROUP BY and ORDER BY expressions.
        Returns a tuple of (groupby_parts, orderby_parts).

        This method ensures that:
        1. Ordering follows the model's defined sequence (e.g. Stage order).
        2. Date periods are ordered chronologically (Year then Month).
        3. All ordered fields are included in the GROUP BY clause.
        """
        table = ctx["graph_table"]
        join_meta = ctx["join_table_metadata"]
        primary_field = dashboard_graph_group[:1]
        groupby_parts = []
        orderby_parts = []

        for field in dashboard_graph_group:
            is_primary = field == primary_field
            field_groupby = []
            field_orderby = []

            # 1. Computed fields
            if (
                field.name
                in self.env.user._get_graph_computed_groupby_fields()
            ):
                expr = "x" if is_primary else field.name
                field_groupby.append(expr)
                field_orderby.append(expr)

            # 2. Related fields
            elif field.related:
                _, _, groupby = self._get_related_column_joins(
                    base_model=self._get_graph_model(),
                    related_path=field.related.split("."),
                    field_id=field,
                )
                expr = "x" if is_primary else groupby
                field_groupby.append(expr)
                field_orderby.append(expr)

            # 3. Many2many
            elif field.ttype == "many2many":
                _, _, groupby_query = self._get_m2m_values(
                    table=table,
                    field=field,
                )
                field_groupby.append(groupby_query)
                field_orderby.append(groupby_query)

            # 4. Date periods
            elif field.is_date_period():
                date_field, group = field.get_date_period().split(":")
                group_alias = f"{date_field}_{group}"
                year_alias = f"{date_field}_year"

                if is_primary:
                    if group in ("week", "month", "quarter"):
                        # Order by year then period (e.g. 2023 then Jan)
                        field_groupby.extend(["x", year_alias])
                        field_orderby.extend([year_alias, "x"])
                    else:
                        field_groupby.append("x")
                        field_orderby.append("x")
                else:
                    if group in ("week", "month", "quarter"):
                        field_groupby.extend([group_alias, year_alias])
                        field_orderby.extend([year_alias, group_alias])
                    else:
                        field_groupby.append(group_alias)
                        field_orderby.append(group_alias)

            # 5. Many2one (respect comodel _order)
            elif field.ttype == "many2one":
                meta = join_meta.get(field.name)
                expr = "x" if is_primary else f"{table}.{field.name}"
                field_groupby.append(expr)

                if meta and meta.get("table"):
                    alias = meta["table"].split()[-1]
                    field_groupby.append(f"{alias}.id")

                    if meta.get("order"):
                        # Use model-defined ordering
                        for part in meta["order"].split(","):
                            part = part.strip()
                            if not part:
                                continue
                            field_orderby.append(part)
                            # Extract base expression for GROUP BY
                            order_expr = re.split(
                                r"\s+(?:ASC|DESC)\b", part, flags=re.I
                            )[0].strip()
                            field_groupby.append(order_expr)
                    else:
                        field_orderby.append(f"{alias}.id")
                else:
                    field_orderby.append(expr)

            # 6. Default (Standard fields / Selection)
            else:
                expr = f"{table}.{field.name}"
                field_groupby.append(expr)
                field_orderby.append(expr)

            groupby_parts.extend(field_groupby)
            orderby_parts.extend(field_orderby)

        # Deduplicate while maintaining order
        deduped_groupby = []
        seen_groupby = set()
        for p in groupby_parts:
            if p not in seen_groupby:
                deduped_groupby.append(p)
                seen_groupby.add(p)

        deduped_orderby = []
        seen_orderby = set()
        for p in orderby_parts:
            if p not in seen_orderby:
                deduped_orderby.append(p)
                seen_orderby.add(p)

        return deduped_groupby, deduped_orderby

    def _build_graph_query(self, ctx, field_condition):
        """
        Constructs the complete SQL query for the dashboard graph.
        """
        dashboard_graph_group = ctx["dashboard_graph_group"]
        join_meta = ctx["join_table_metadata"]
        table = ctx["graph_table"]
        GraphModel = ctx["GraphModel"]
        join_q = []

        joins = {}
        join_order = []

        def add_join(alias, sql):
            if alias in joins:
                return
            joins[alias] = sql
            join_order.append(alias)

        def add_from_clause(from_clause):
            for part in from_clause.split("LEFT JOIN")[1:]:
                join_sql = " LEFT JOIN " + part
                if " AS " in join_sql:
                    alias = join_sql.split(" AS ")[1].split()[0]
                else:
                    alias = join_sql
                add_join(alias, join_sql)

        for field in dashboard_graph_group.filtered(
            lambda x: x.ttype == "many2many"
        ):
            _, join_query, _ = self._get_m2m_values(table=table, field=field)
            join_q.append(join_query)

        query = "SELECT *"

        query += " FROM ( SELECT "

        x_query = self._graph_x_query(ctx)
        y_query, join_y_query, _ = self._graph_y_query()
        query += x_query[0] + " AS x, "
        query += y_query + " AS y "
        if x_query[1:]:
            query += ", " + ", ".join(x_query[1:])

        query += f" FROM {table} "

        for field in dashboard_graph_group:
            # Many2many joins
            if field.ttype == "many2many":
                _, join_sql, _ = self._get_m2m_values(table=table, field=field)
                add_join(field.name, join_sql)

            # related fields
            if field.related and not field.store:
                for join in ctx.get("related_joins", []):
                    add_join(
                        join["alias"],
                        f" LEFT JOIN {join['table']} {join['alias']} ON {join['on']} ",
                    )

            if (
                field.name
                in self.env.user._get_graph_computed_groupby_fields()
            ):
                _, sql_join = self._get_compute_field_query(
                    model=GraphModel, field_id=field
                )
                from_clause = sql_join.from_clause.code.replace("%s", "%%s")
                add_from_clause(from_clause)

                ctx.setdefault("activity_params", [])
                ctx["activity_params"] += sql_join.from_clause.params[1:]
                continue

            # many2one joins
            meta = join_meta.get(field.name)
            if meta and meta.get("table") and field.ttype == "many2one":
                alias = meta["table"].split()[-1]
                add_join(
                    alias,
                    f" LEFT JOIN {meta['table']} "
                    f"ON {table}.{field.name} = {alias}.id ",
                )

                # Special case: res_users often requires res_partner for 'name' ordering
                if alias == "res_users" and "res_partner" in meta.get(
                    "order", ""
                ):
                    add_join(
                        "res_partner",
                        " LEFT JOIN res_partner ON res_partner.id = res_users.partner_id ",
                    )

                if meta.get("extra_join_conditions"):
                    add_join(f"{alias}_extra", meta["extra_join_conditions"])

            extra = self._extra_join_sql_conditions().get(field.name)
            if extra:
                add_join(f"{field.name}_extra", extra)

        if join_y_query.find("LEFT JOIN") != -1:
            add_from_clause(join_y_query.replace("%s", "%%s"))

        for alias in join_order:
            query += joins[alias]

        query += field_condition + "%(where_condition)s"

        groupby_parts, orderby_parts = self._build_groupby_orderby_clause(
            ctx=ctx,
            dashboard_graph_group=dashboard_graph_group,
        )

        query += " GROUP BY " + ", ".join(groupby_parts)
        if orderby_parts:
            query += " ORDER BY " + ", ".join(orderby_parts)

        query += ") AS graph_data"
        return query % {
            "table": ctx["graph_table"],
            "field_value": "%s",
            "where_condition": (
                " AND " + ctx["where_clause"].code
                if ctx["where_clause"]
                else ""
            ),
        }

    def _prepare_query_parameters(self, ctx):
        """
        Prepares parameter list for SQL execution.
        """
        query_parameters = []
        if ctx.get("params"):
            query_parameters += ctx["params"]
        if ctx.get("activity_params"):
            query_parameters += ctx["activity_params"]
        _, _, join_params = self._graph_y_query()
        if join_params:
            query_parameters += join_params[1:]
        query_parameters += [tuple(ctx["graph_model_record_ids"])]
        # Add dynamic where clause params from GraphModel
        if ctx["where_clause"]:
            query_parameters += ctx["where_clause"].params
        return query_parameters
