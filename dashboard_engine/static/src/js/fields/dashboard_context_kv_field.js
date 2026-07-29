/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import {
    VALUE_TYPES,
    rowsFromContextRaw,
    serializeContextRows,
    createEmptyContextRow,
    emptyGroupRule,
    collectGroupXmlids,
    applyGroupLabels,
} from "./context_kv_utils";

/**
 * Friendly action-context editor (no raw JSON).
 * Supports fixed values, card id, and multi-rule group maps.
 */
export class DashboardContextKvField extends Component {
    static template = "dashboard_engine.DashboardContextKvField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.VALUE_TYPES = VALUE_TYPES;
        this.state = useState({
            rows: rowsFromContextRaw(this.props.record.data[this.props.name]),
            groupQuery: {},
            groupHits: {},
        });
        onWillStart(async () => {
            await this._hydrateGroupLabels();
        });
        onWillUpdateProps(async (nextProps) => {
            const nextRaw = nextProps.record.data[nextProps.name];
            const curRaw = serializeContextRows(this.state.rows);
            if (nextRaw !== curRaw && nextRaw !== this.props.record.data[this.props.name]) {
                this.state.rows = rowsFromContextRaw(nextRaw);
                await this._hydrateGroupLabels();
            }
        });
    }

    get hasContextKeys() {
        return this.state.rows.some((row) => row.key);
    }

    async _hydrateGroupLabels() {
        const xmlids = collectGroupXmlids(this.state.rows);
        if (!xmlids.length) {
            return;
        }
        try {
            const labels = await this.orm.call(
                "dashboard.blueprint",
                "studio_group_labels",
                [],
                { xmlids }
            );
            applyGroupLabels(this.state.rows, labels || {});
            this.state.rows = [...this.state.rows];
        } catch {
            /* keep xmlids as labels */
        }
    }

    async _commit() {
        const value = serializeContextRows(this.state.rows);
        if (value !== (this.props.record.data[this.props.name] || "{}")) {
            await this.props.record.update({ [this.props.name]: value });
        }
    }

    _touchRows() {
        this.state.rows = [...this.state.rows];
        this._commit();
    }

    onKeyInput(index, ev) {
        this.state.rows[index].key = ev.target.value;
        this._touchRows();
    }

    onTypeChange(index, ev) {
        const row = this.state.rows[index];
        row.valueType = ev.target.value;
        if (row.valueType === "group" && !(row.groupRules && row.groupRules.length)) {
            row.groupRules = [emptyGroupRule()];
        }
        this._touchRows();
    }

    onFixedInput(index, ev) {
        this.state.rows[index].fixedValue = ev.target.value;
        this._touchRows();
    }

    onAsListChange(index, ev) {
        this.state.rows[index].asList = ev.target.checked;
        this._touchRows();
    }

    onElseValueInput(index, ev) {
        this.state.rows[index].elseValue = ev.target.value;
        this._touchRows();
    }

    onRuleValueInput(rowIndex, ruleIndex, ev) {
        this.state.rows[rowIndex].groupRules[ruleIndex].value = ev.target.value;
        this._touchRows();
    }

    _ruleKey(rowIndex, ruleIndex) {
        return `${rowIndex}:${ruleIndex}`;
    }

    getGroupHits(rowIndex, ruleIndex) {
        return this.state.groupHits[this._ruleKey(rowIndex, ruleIndex)] || [];
    }

    async onGroupSearchInput(rowIndex, ruleIndex, ev) {
        const term = ev.target.value;
        const key = this._ruleKey(rowIndex, ruleIndex);
        this.state.groupQuery[key] = term;
        this.state.rows[rowIndex].groupRules[ruleIndex].groupLabel = term;
        this._touchRows();
        if (!term || term.length < 1) {
            this.state.groupHits[key] = [];
            return;
        }
        try {
            const hits = await this.orm.call(
                "dashboard.blueprint",
                "studio_search_groups",
                [],
                { term, limit: 12 }
            );
            this.state.groupHits[key] = hits || [];
        } catch {
            this.state.groupHits[key] = [];
        }
    }

    pickGroup(rowIndex, ruleIndex, hit) {
        const key = this._ruleKey(rowIndex, ruleIndex);
        const rule = this.state.rows[rowIndex].groupRules[ruleIndex];
        rule.groupXmlid = hit.xmlid;
        rule.groupLabel = hit.name;
        this.state.groupQuery[key] = hit.name;
        this.state.groupHits[key] = [];
        this._touchRows();
    }

    addGroupRule(rowIndex) {
        this.state.rows[rowIndex].groupRules.push(emptyGroupRule());
        this._touchRows();
    }

    removeGroupRule(rowIndex, ruleIndex) {
        const rules = this.state.rows[rowIndex].groupRules;
        rules.splice(ruleIndex, 1);
        if (!rules.length) {
            rules.push(emptyGroupRule());
        }
        this._touchRows();
    }

    addRow() {
        this.state.rows.push(createEmptyContextRow());
        this._touchRows();
    }

    async removeRow(index) {
        this.state.rows.splice(index, 1);
        if (!this.state.rows.length) {
            this.state.rows.push(createEmptyContextRow());
        }
        await this._touchRows();
    }

    typeLabel(valueType) {
        const found = VALUE_TYPES.find((t) => t.value === valueType);
        return found ? found.label : valueType;
    }

    readonlySummary(row) {
        if (row.valueType === "record_id") {
            return row.asList ? "this card’s id (list)" : "this card’s id";
        }
        if (row.valueType === "group") {
            const parts = (row.groupRules || [])
                .filter((r) => r.groupXmlid)
                .map(
                    (r) =>
                        `${r.groupLabel || r.groupXmlid} → ${r.value}`
                );
            const otherwise = row.elseValue !== "" ? `otherwise ${row.elseValue}` : "";
            return [...parts, otherwise].filter(Boolean).join("; ") || "—";
        }
        return row.fixedValue;
    }
}

export const dashboardContextKvField = {
    component: DashboardContextKvField,
    displayName: _t("Action defaults"),
    supportedTypes: ["char", "text"],
};

registry.category("fields").add("dashboard_context_kv", dashboardContextKvField);
