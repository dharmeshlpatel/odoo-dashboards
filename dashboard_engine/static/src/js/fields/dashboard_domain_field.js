/** @odoo-module **/

import { Component } from "@odoo/owl";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { Domain } from "@web/core/domain";
import { DomainSelector } from "@web/core/domain_selector/domain_selector";
import { _t } from "@web/core/l10n/translation";
import {
    deserializeDate,
    deserializeDateTime,
    serializeDate,
    serializeDateTime,
} from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { connector } from "@web/core/tree_editor/condition_tree";
import { constructTreeFromDomain } from "@web/core/tree_editor/construct_tree_from_domain";
import { TreeEditor } from "@web/core/tree_editor/tree_editor";
import { getValueEditorInfo } from "@web/core/tree_editor/tree_editor_value_editors";
import { DomainField, domainField } from "@web/views/fields/domain/domain_field";

const { DateTime } = luxon;

const RELATIVE_DATE_OPERATORS = new Set(["<", ">"]);

/**
 * Presets for before/after on date fields — same idea as DomainSelector
 * "is in" (today, last 7 days, …) but as a single comparison point.
 */
export class RelativeDateValue extends Component {
    static template = "dashboard_engine.TreeEditor.RelativeDateValue";
    static components = { DateTimeInput };
    static props = ["value", "update", "fieldType"];
    static options = [
        ["today", _t("Today")],
        ["today -7d", _t("7 days ago")],
        ["today -30d", _t("30 days ago")],
        ["custom date", _t("Specific date")],
    ];

    get presetValues() {
        return RelativeDateValue.options
            .filter(([value]) => value !== "custom date")
            .map(([value]) => value);
    }

    get valueType() {
        return this.presetValues.includes(this.props.value)
            ? this.props.value
            : "custom date";
    }

    get dateValue() {
        if (this.valueType !== "custom date" || this.props.value === false) {
            return false;
        }
        try {
            return this.props.fieldType === "date"
                ? deserializeDate(this.props.value)
                : deserializeDateTime(this.props.value);
        } catch {
            return false;
        }
    }

    onTypeChange(ev) {
        const next = ev.target.value;
        if (next === "custom date") {
            const now = DateTime.local().startOf("day");
            this.props.update(
                this.props.fieldType === "date"
                    ? serializeDate(now)
                    : serializeDateTime(now)
            );
            return;
        }
        this.props.update(next);
    }

    onDateApply(value) {
        const dt = value || DateTime.local().startOf("day");
        this.props.update(
            this.props.fieldType === "date"
                ? serializeDate(dt)
                : serializeDateTime(dt)
        );
    }
}

function isParsableDate(fieldType, value) {
    if (typeof value !== "string") {
        return false;
    }
    try {
        if (fieldType === "date") {
            deserializeDate(value);
        } else {
            deserializeDateTime(value);
        }
        return true;
    } catch {
        return false;
    }
}

function makeRelativeDateEditorInfo(fieldDef) {
    const fieldType = fieldDef.type;
    const presetValues = RelativeDateValue.options
        .filter(([value]) => value !== "custom date")
        .map(([value]) => value);

    return {
        component: RelativeDateValue,
        extractProps: ({ value, update }) => ({
            value,
            update,
            fieldType,
        }),
        isSupported: (value) =>
            typeof value === "string" &&
            (presetValues.includes(value) || isParsableDate(fieldType, value)),
        defaultValue: () => "today",
        shouldResetValue: (value) =>
            typeof value !== "string" ||
            (!presetValues.includes(value) && !isParsableDate(fieldType, value)),
        stringify: (value) => {
            const option = RelativeDateValue.options.find(([v]) => v === value);
            if (option) {
                return option[1];
            }
            if (typeof value === "string" && isParsableDate(fieldType, value)) {
                try {
                    const dt =
                        fieldType === "date"
                            ? deserializeDate(value)
                            : deserializeDateTime(value);
                    return dt.toLocaleString(
                        fieldType === "date" ? DateTime.DATE_MED : DateTime.DATETIME_MED
                    );
                } catch {
                    /* fall through */
                }
            }
            return String(value);
        },
        message: _t("Not a valid date"),
    };
}

export function getDashboardValueEditorInfo(fieldDef, operator, options = {}) {
    if (
        fieldDef &&
        ["date", "datetime"].includes(fieldDef.type) &&
        RELATIVE_DATE_OPERATORS.has(operator)
    ) {
        return {
            extractProps: ({ value, update }) => ({ value, update }),
            message: _t("Value not supported"),
            stringify: (val) => String(val),
            ...makeRelativeDateEditorInfo(fieldDef),
        };
    }
    return getValueEditorInfo(fieldDef, operator, options);
}

function getDashboardDefaultValue(fieldDef, operator, value = null) {
    const { isSupported, shouldResetValue, defaultValue } = getDashboardValueEditorInfo(
        fieldDef,
        operator
    );
    if (value === null || !isSupported(value) || shouldResetValue?.(value)) {
        return defaultValue(operator);
    }
    return value;
}

export class DashboardTreeEditor extends TreeEditor {
    static components = {
        ...TreeEditor.components,
        TreeEditor: DashboardTreeEditor,
    };

    getValueEditorInfo(node) {
        const fieldDef = this.getFieldDef(node.path);
        if (!fieldDef) {
            return getValueEditorInfo({ type: "char", name: node.path || "id" }, node.operator);
        }
        return getDashboardValueEditorInfo(fieldDef, node.operator);
    }

    async _updatePath(node, path) {
        const { fieldDef } = await this.fieldService.loadFieldInfo(this.props.resModel, path);
        node.path = path;
        node.negate = false;
        node.operator = this.props.getDefaultOperator(fieldDef);
        node.value = getDashboardDefaultValue(fieldDef, node.operator);
        node.isProperty = fieldDef?.is_property;
    }

    _updateLeafOperator(node, operator, negate) {
        const fieldDef = this.getFieldDef(node.path);
        node.negate = negate;
        node.operator = operator;
        node.value = getDashboardDefaultValue(fieldDef, operator, node.value);
    }
}

const DATE_PERIODS = new Set(["day", "week", "month", "quarter", "year"]);

/** Virtual ``x_<date>_<period>`` tags — Group By only, never domain leaves. */
export function isDashboardDatePeriodFieldName(name) {
    if (!name || typeof name !== "string" || !name.startsWith("x_")) {
        return false;
    }
    const sep = name.lastIndexOf("_");
    if (sep <= 2) {
        return false;
    }
    return DATE_PERIODS.has(name.slice(sep + 1));
}

function dashboardDomainFieldFilter(fieldDef) {
    const base =
        fieldDef?.searchable &&
        fieldDef.type !== "json" &&
        fieldDef.type !== "separator";
    if (!base) {
        return false;
    }
    // Prefer technical name when present (properties / enriched defs).
    if (fieldDef.name && isDashboardDatePeriodFieldName(fieldDef.name)) {
        return false;
    }
    // Label pattern from ir.model.fields: "Created on > Month".
    const label = fieldDef.string || "";
    if (/\s>\s(Day|Week|Month|Quarter|Year)$/i.test(label)) {
        return false;
    }
    return true;
}

export class DashboardDomainSelector extends DomainSelector {
    static components = {
        ...DomainSelector.components,
        TreeEditor: DashboardTreeEditor,
    };

    async onPropsUpdated(p) {
        // Never use stock "in range" virtual operators here. Two month/year
        // ranges (even count) rewrite to an empty tree → "Match all records".
        let domain;
        try {
            domain = new Domain(p.domain);
        } catch {
            this.tree = connector("&");
            this.showArchivedCheckbox = false;
            this.includeArchived = false;
            return;
        }
        try {
            this.tree = constructTreeFromDomain(domain, false);
            const { fieldDef: activeFieldDef } = await this.fieldService.loadFieldInfo(
                p.resModel,
                "active"
            );
            this.showArchivedCheckbox = this.getShowArchivedCheckBox(
                Boolean(activeFieldDef),
                p
            );
            this.includeArchived = false;
        } catch {
            this.tree = connector("&");
            this.showArchivedCheckbox = false;
            this.includeArchived = false;
        }
    }

    getPathEditorInfo(resModel, defaultCondition) {
        const info = super.getPathEditorInfo(resModel, defaultCondition);
        const extractProps = info.extractProps;
        return {
            ...info,
            extractProps: (params) => ({
                ...extractProps(params),
                filter: dashboardDomainFieldFilter,
            }),
        };
    }
}

export class DashboardDomainField extends DomainField {
    static components = {
        ...DomainField.components,
        DomainSelector: DashboardDomainSelector,
    };

    async loadFacets(props = this.props) {
        try {
            await super.loadFacets(props);
        } catch {
            this.state.facets = [];
            this.state.folded = false;
        }
    }
}

export const dashboardDomainField = {
    ...domainField,
    component: DashboardDomainField,
    // Reuse stock domain block/full-width styles (`.o_field_domain`).
    additionalClasses: ["o_field_domain"],
};

registry.category("fields").add("dashboard_domain", dashboardDomainField);
