/** @odoo-module **/

import { Component, useState, onWillUpdateProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Edit a Char JSON object as key/value rows (primary action context).
 * Values may include ``{{id}}`` for the card record.
 */
export class DashboardContextKvField extends Component {
    static template = "dashboard_engine.DashboardContextKvField";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({ rows: this._rowsFromValue(this.props.record.data[this.props.name]) });
        onWillUpdateProps((nextProps) => {
            if (nextProps.readonly !== this.props.readonly) {
                this.state.rows = this._rowsFromValue(nextProps.record.data[nextProps.name]);
            }
            const nextRaw = nextProps.record.data[nextProps.name];
            const curRaw = this._serialize(this.state.rows);
            if (nextRaw !== curRaw && nextRaw !== this.props.record.data[this.props.name]) {
                this.state.rows = this._rowsFromValue(nextRaw);
            }
        });
    }

    get hasContextKeys() {
        return this.state.rows.some((row) => row.key);
    }

    _rowsFromValue(raw) {
        let obj = {};
        try {
            const parsed = typeof raw === "string" ? JSON.parse(raw || "{}") : raw || {};
            if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
                obj = parsed;
            }
        } catch {
            obj = {};
        }
        const rows = Object.entries(obj).map(([key, value]) => ({
            key,
            value: value === null || value === undefined ? "" : String(value),
        }));
        if (!rows.length) {
            rows.push({ key: "", value: "" });
        }
        return rows;
    }

    _serialize(rows) {
        const obj = {};
        for (const row of rows) {
            const key = (row.key || "").trim();
            if (!key) {
                continue;
            }
            obj[key] = row.value;
        }
        return JSON.stringify(obj);
    }

    async _commit() {
        const value = this._serialize(this.state.rows);
        if (value !== (this.props.record.data[this.props.name] || "{}")) {
            await this.props.record.update({ [this.props.name]: value });
        }
    }

    onKeyInput(index, ev) {
        this.state.rows[index].key = ev.target.value;
        this._commit();
    }

    onValueInput(index, ev) {
        this.state.rows[index].value = ev.target.value;
        this._commit();
    }

    addRow() {
        this.state.rows.push({ key: "", value: "" });
    }

    async removeRow(index) {
        this.state.rows.splice(index, 1);
        if (!this.state.rows.length) {
            this.state.rows.push({ key: "", value: "" });
        }
        await this._commit();
    }
}

export const dashboardContextKvField = {
    component: DashboardContextKvField,
    displayName: _t("Context key/value"),
    supportedTypes: ["char", "text"],
};

registry.category("fields").add("dashboard_context_kv", dashboardContextKvField);
