/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { DashboardDomainSelectorDialog } from "@dashboard_engine/js/fields/dashboard_domain_selector_dialog";
import { ContextFieldValueWidget } from "./context_field_value_widget";
import {
    VALUE_TYPES,
    CONTEXT_PRESETS,
    CARD_PASS_TARGETS,
    rowsFromContextRaw,
    serializeContextRows,
    createEmptyContextRow,
    createContextPreset,
    emptyGroupRule,
    collectGroupXmlids,
    applyGroupLabels,
    contextRowPurpose as purposeOfRow,
    contextRowTitle as titleOfRow,
    searchFilterShortName as filterShortNameOf,
    formDefaultShortName as defaultShortNameOf,
    toSearchFilterKey,
    toFormDefaultKey,
} from "./context_kv_utils";

/**
 * Advanced-form Action Defaults editor — same When Opened UX as Studio.
 */
export class DashboardContextKvField extends Component {
    static template = "dashboard_engine.DashboardContextKvField";
    static components = { ContextFieldValueWidget, CheckBox };
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.VALUE_TYPES = VALUE_TYPES;
        this.CONTEXT_PRESETS = CONTEXT_PRESETS;
        this.CARD_PASS_TARGETS = CARD_PASS_TARGETS;
        this.state = useState({
            rows: rowsFromContextRaw(this.props.record.data[this.props.name]),
            groupQuery: {},
            groupHits: {},
            fieldsCatalog: {},
            filtersCatalog: {},
            targetModel: "",
            hostModel: "",
        });
        onWillStart(async () => {
            await this._hydrateGroupLabels();
            await this._refreshCatalogs();
        });
        onWillUpdateProps(async (nextProps) => {
            const nextRaw = nextProps.record.data[nextProps.name];
            const curRaw = serializeContextRows(this.state.rows);
            if (nextRaw !== curRaw && nextRaw !== this.props.record.data[this.props.name]) {
                this.state.rows = rowsFromContextRaw(nextRaw);
                await this._hydrateGroupLabels();
            }
            await this._refreshCatalogs(nextProps);
        });
    }

    get hasContextKeys() {
        return this.state.rows.some((row) => row.key);
    }

    _m2oId(value) {
        if (Array.isArray(value)) {
            return value[0] || false;
        }
        return value || false;
    }

    _blueprintId(props = this.props) {
        const data = props.record.data;
        if (props.record.resModel === "dashboard.blueprint") {
            return props.record.resId;
        }
        return this._m2oId(data.blueprint_id);
    }

    _fallbackModels(props = this.props) {
        const data = props.record.data;
        const targetModel =
            data.action_model ||
            data.graph_model ||
            data.compute_model ||
            data.host_model_name ||
            "";
        const hostModel =
            data.host_model_name || data.graph_model || targetModel || "";
        return {
            targetModel: targetModel || "",
            hostModel: hostModel || "",
        };
    }

    /**
     * Same target-model rules as Studio When Opened:
     * prefer the Action's res_model, then fall back to slot/option models.
     */
    async _resolveModels(props = this.props) {
        const fallback = this._fallbackModels(props);
        const data = props.record.data;
        const bp = this._blueprintId(props);
        const xmlid = (
            data.primary_action_xmlid ||
            data.action_xmlid ||
            ""
        ).trim();
        if (bp && xmlid) {
            try {
                const res = await this.orm.call(
                    "dashboard.blueprint",
                    "studio_resolve_action_model",
                    [[bp], xmlid]
                );
                if (res?.res_model) {
                    return {
                        targetModel: res.res_model,
                        hostModel: fallback.hostModel || res.res_model,
                    };
                }
            } catch {
                /* fall through */
            }
        }
        const actionId =
            this._m2oId(data.primary_action_id) || this._m2oId(data.action_id);
        if (actionId) {
            try {
                const rows = await this.orm.read(
                    "ir.actions.act_window",
                    [actionId],
                    ["res_model"]
                );
                const resModel = rows?.[0]?.res_model;
                if (resModel) {
                    return {
                        targetModel: resModel,
                        hostModel: fallback.hostModel || resModel,
                    };
                }
            } catch {
                /* fall through */
            }
        }
        return fallback;
    }

    async _refreshCatalogs(props = this.props) {
        const { targetModel, hostModel } = await this._resolveModels(props);
        this.state.targetModel = targetModel;
        this.state.hostModel = hostModel;
        if (!targetModel) {
            return;
        }
        const bp = this._blueprintId(props);
        if (!bp) {
            return;
        }
        await Promise.all([
            this._ensureFieldsCatalog(bp, targetModel),
            this._ensureFiltersCatalog(bp, targetModel),
        ]);
    }

    async _ensureFieldsCatalog(blueprintId, model) {
        if (Object.prototype.hasOwnProperty.call(this.state.fieldsCatalog, model)) {
            return;
        }
        try {
            const rows = await this.orm.call("dashboard.blueprint", "studio_model_fields", [
                [blueprintId],
                model,
                null,
                false,
            ]);
            this.state.fieldsCatalog = { ...this.state.fieldsCatalog, [model]: rows || [] };
        } catch {
            this.state.fieldsCatalog = { ...this.state.fieldsCatalog, [model]: [] };
        }
    }

    async _ensureFiltersCatalog(blueprintId, model) {
        if (Object.prototype.hasOwnProperty.call(this.state.filtersCatalog, model)) {
            return;
        }
        try {
            const rows = await this.orm.call(
                "dashboard.blueprint",
                "studio_action_search_filters",
                [[blueprintId], model]
            );
            this.state.filtersCatalog = { ...this.state.filtersCatalog, [model]: rows || [] };
        } catch {
            this.state.filtersCatalog = { ...this.state.filtersCatalog, [model]: [] };
        }
    }

    fieldOptions() {
        const model = this.state.targetModel;
        return model ? this.state.fieldsCatalog[model] || [] : [];
    }

    filterOptions() {
        const model = this.state.targetModel;
        return model ? this.state.filtersCatalog[model] || [] : [];
    }

    contextFieldFor(row) {
        const shortName = defaultShortNameOf(row?.key);
        if (!shortName) {
            return null;
        }
        return this.fieldOptions().find((f) => f.name === shortName) || null;
    }

    isKnownFieldName(name) {
        return Boolean(name && this.fieldOptions().some((f) => f.name === name));
    }

    isKnownFilterName(name) {
        return Boolean(name && this.filterOptions().some((f) => f.name === name));
    }

    isKnownCardPassTarget(key) {
        return this.CARD_PASS_TARGETS.some((t) => t.key === key);
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

    contextRowPurpose(row) {
        return purposeOfRow(row);
    }

    contextRowTitle(row) {
        return titleOfRow(row);
    }

    searchFilterShortName(row) {
        return filterShortNameOf(row?.key);
    }

    formDefaultShortName(row) {
        return defaultShortNameOf(row?.key);
    }

    addPreset(presetId) {
        const row = createContextPreset(presetId);
        if (!row) {
            return;
        }
        this.state.rows.push(row);
        this._touchRows();
        this._refreshCatalogs();
    }

    addRow() {
        this.state.rows.push(createEmptyContextRow());
        this._touchRows();
    }

    async removeRow(index) {
        this.state.rows.splice(index, 1);
        if (!this.state.rows.length) {
            this.state.rows = [];
        }
        await this._touchRows();
    }

    onCardPassTarget(index, ev) {
        const row = this.state.rows[index];
        row.key = ev.target.value;
        row.valueType = "record_id";
        this._touchRows();
    }

    onAsListChange(index, checked) {
        this.state.rows[index].asList = Boolean(checked);
        this._touchRows();
    }

    onSearchFilterName(index, ev) {
        const row = this.state.rows[index];
        row.key = toSearchFilterKey(ev.target.value);
        row.valueType = "fixed";
        if (row.fixedValue === "" || row.fixedValue === undefined) {
            row.fixedValue = "1";
        }
        this._touchRows();
    }

    onFormFieldName(index, ev) {
        const row = this.state.rows[index];
        row.key = toFormDefaultKey(ev.target.value);
        row.valueType = "fixed";
        this._touchRows();
        this._refreshCatalogs();
    }

    onGroupSettingName(index, ev) {
        const row = this.state.rows[index];
        row.key = toFormDefaultKey(ev.target.value || "type");
        row.valueType = "group";
        this._touchRows();
        this._refreshCatalogs();
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

    setFixedValue(index, value) {
        this.state.rows[index].fixedValue = value;
        this._touchRows();
    }

    setRuleValue(rowIndex, ruleIndex, value) {
        this.state.rows[rowIndex].groupRules[ruleIndex].value = value;
        this._touchRows();
    }

    setElseValue(index, value) {
        this.state.rows[index].elseValue = value;
        this._touchRows();
    }

    onRuleWhenTypeChange(rowIndex, ruleIndex, ev) {
        const rule = this.state.rows[rowIndex].groupRules[ruleIndex];
        rule.whenType = ev.target.value || "group";
        if (rule.whenType === "record" && !(rule.domain || "").trim()) {
            rule.domain = "[]";
        }
        this._touchRows();
    }

    openRuleDomainEditor(rowIndex, ruleIndex) {
        const rule = this.state.rows[rowIndex].groupRules[ruleIndex];
        const resModel = this.state.hostModel || this.state.targetModel || "res.partner";
        this.dialog.add(DashboardDomainSelectorDialog, {
            resModel,
            domain: rule.domain || "[]",
            title: _t("Card Condition"),
            onConfirm: (domain) => {
                rule.domain = domain || "[]";
                this._touchRows();
            },
        });
    }

    ruleDomainSummary(rule) {
        const domain = (rule?.domain || "[]").trim() || "[]";
        if (domain === "[]") {
            return _t("No condition set");
        }
        return domain.length > 72 ? `${domain.slice(0, 69)}…` : domain;
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
                .filter(
                    (r) =>
                        ((r.whenType || "group") === "group" && r.groupXmlid) ||
                        ((r.whenType || "group") === "record" &&
                            (r.domain || "[]").trim() &&
                            (r.domain || "[]").trim() !== "[]")
                )
                .map((r) => {
                    if ((r.whenType || "group") === "record") {
                        return `card ${r.domain} → ${r.value}`;
                    }
                    return `${r.groupLabel || r.groupXmlid} → ${r.value}`;
                });
            const otherwise = row.elseValue !== "" ? `otherwise ${row.elseValue}` : "";
            return [...parts, otherwise].filter(Boolean).join("; ") || "—";
        }
        return row.fixedValue;
    }
}

export const dashboardContextKvField = {
    component: DashboardContextKvField,
    displayName: _t("Action Defaults"),
    supportedTypes: ["char", "text"],
};

registry.category("fields").add("dashboard_context_kv", dashboardContextKvField);
