/** @odoo-module **/

import { Component } from "@odoo/owl";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import {
    deserializeDate,
    deserializeDateTime,
    serializeDate,
    serializeDateTime,
} from "@web/core/l10n/dates";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";

/**
 * Type-aware value control for When Opened rows (Prefill / Then use / Otherwise).
 * Relational fields use stock RecordSelector / MultiRecordSelector.
 */
export class ContextFieldValueWidget extends Component {
    static template = "dashboard_engine.ContextFieldValueWidget";
    static components = { CheckBox, DateTimeInput, RecordSelector, MultiRecordSelector };
    static props = {
        fieldMeta: { optional: true },
        value: { optional: true },
        readonly: { type: Boolean, optional: true },
        placeholder: { type: String, optional: true },
        onValueChange: { type: Function },
        // Legacy custom hit-list props (ignored when RecordSelector is used).
        recordDisplay: { type: String, optional: true },
        recordHits: { type: Array, optional: true },
        onRecordSearchInput: { type: Function, optional: true },
        onRecordPick: { type: Function, optional: true },
    };

    get ttype() {
        return this.props.fieldMeta?.ttype || "char";
    }

    get kind() {
        const t = this.ttype;
        if (t === "boolean") {
            return "boolean";
        }
        if (t === "selection") {
            return "selection";
        }
        if (t === "many2one") {
            return "many2one";
        }
        if (t === "many2many" || t === "one2many") {
            return "many2many";
        }
        if (t === "integer") {
            return "integer";
        }
        if (t === "float" || t === "monetary") {
            return "float";
        }
        if (t === "date") {
            return "date";
        }
        if (t === "datetime") {
            return "datetime";
        }
        return "text";
    }

    get relationModel() {
        return this.props.fieldMeta?.relation || "";
    }

    get fieldString() {
        return this.props.fieldMeta?.string || this.props.placeholder || "";
    }

    get selectionOptions() {
        return this.props.fieldMeta?.selection || [];
    }

    get stringValue() {
        if (this.props.value === null || this.props.value === undefined) {
            return "";
        }
        return String(this.props.value);
    }

    get boolValue() {
        const raw = this.props.value;
        if (raw === true || raw === 1) {
            return true;
        }
        const s = String(raw || "").toLowerCase();
        return s === "true" || s === "1" || s === "yes";
    }

    get recordResId() {
        const raw = this.props.value;
        if (raw === false || raw === null || raw === undefined || raw === "") {
            return false;
        }
        const n = Number(raw);
        return Number.isFinite(n) && n > 0 ? n : false;
    }

    get recordResIds() {
        const raw = this.props.value;
        if (raw === false || raw === null || raw === undefined || raw === "") {
            return [];
        }
        if (Array.isArray(raw)) {
            return raw.map(Number).filter((n) => Number.isFinite(n) && n > 0);
        }
        const s = String(raw).trim();
        if (!s) {
            return [];
        }
        if (s.startsWith("[")) {
            try {
                const parsed = JSON.parse(s);
                if (Array.isArray(parsed)) {
                    return parsed.map(Number).filter((n) => Number.isFinite(n) && n > 0);
                }
            } catch {
                // fall through
            }
        }
        return s
            .split(/[\s,]+/)
            .map(Number)
            .filter((n) => Number.isFinite(n) && n > 0);
    }

    get dateValue() {
        const raw = this.stringValue;
        if (!raw) {
            return false;
        }
        try {
            return this.kind === "datetime"
                ? deserializeDateTime(raw)
                : deserializeDate(raw);
        } catch {
            return false;
        }
    }

    onInputChange(ev) {
        this.props.onValueChange(ev.target.value);
    }

    onBoolChange(checked) {
        if (this.props.readonly) {
            return;
        }
        this.props.onValueChange(checked ? "true" : "false");
    }

    onDateApply(value) {
        if (!value) {
            this.props.onValueChange("");
            return;
        }
        const serialized =
            this.kind === "datetime" ? serializeDateTime(value) : serializeDate(value);
        this.props.onValueChange(serialized);
    }

    onRecordUpdate(resId) {
        if (this.props.readonly) {
            return;
        }
        this.props.onValueChange(resId ? String(resId) : "");
    }

    onMultiRecordUpdate(resIds) {
        if (this.props.readonly) {
            return;
        }
        const ids = (resIds || []).filter((n) => Number.isFinite(n) && n > 0);
        this.props.onValueChange(ids.length ? ids.join(",") : "");
    }
}
