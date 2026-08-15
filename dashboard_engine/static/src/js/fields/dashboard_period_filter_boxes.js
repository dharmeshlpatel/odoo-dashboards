/** @odoo-module **/

import { Component, useEffect } from "@odoo/owl";
import { Domain } from "@web/core/domain";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { DashboardMany2ManyTagsField } from "@dashboard_engine/js/fields/dashboard_no_search_more";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

function customFilterFromPeriodPayload(raw) {
    // Prefer the server-computed domain string (Python tuple format,
    // already verified by _domain_to_char and safe_eval).  The JS
    // Domain.or fallback is kept for safety but should rarely be needed.
    if (raw && typeof raw === "object") {
        if (typeof raw.domain === "string" && raw.domain && raw.domain !== "[]") {
            return raw.domain;
        }
        if (Array.isArray(raw.ranges) && raw.ranges.length) {
            const parts = raw.ranges
                .filter((r) => r && r.field && r.start && r.end)
                .map(
                    (r) =>
                        new Domain([
                            [r.field, ">=", r.start],
                            [r.field, "<=", r.end],
                        ])
                );
            if (!parts.length) {
                return "[]";
            }
            const combined =
                parts.length === 1
                    ? parts[0]
                    : raw.operator === "all"
                      ? Domain.and(parts)
                      : Domain.or(parts);
            return combined.toString();
        }
    }
    if (typeof raw === "string" && raw) {
        return raw;
    }
    return "[]";
}

function x2mIds(value) {
    const ids = [];
    const push = (id) => {
        const num = typeof id === "number" ? id : parseInt(id, 10);
        if (Number.isInteger(num) && num > 0 && !ids.includes(num)) {
            ids.push(num);
        }
    };
    if (!value) {
        return ids;
    }
    if (Array.isArray(value.currentIds)) {
        value.currentIds.forEach(push);
    }
    if (Array.isArray(value.records)) {
        value.records.forEach((rec) => push(rec.resId));
    }
    return ids;
}

/**
 * Live gear date filters: one full-width settings box per date field.
 *
 * Nested list rows are often not in edition, so tags are rendered with the
 * parent form's readonly flag (not the line's isInEdition).
 */
export class DashboardPeriodFilterBoxesField extends Component {
    static template = "dashboard_engine.DashboardPeriodFilterBoxesField";
    static components = { Many2ManyTagsField: DashboardMany2ManyTagsField };
    static props = {
        ...standardFieldProps,
        relatedFields: { type: Object, optional: true },
        views: { type: Object, optional: true },
        viewMode: { type: String, optional: true },
        context: { type: Object, optional: true },
        domain: { type: [Array, Function], optional: true },
        widget: { type: String, optional: true },
        string: { type: String, optional: true },
        crudOptions: { type: Object, optional: true },
        addLabel: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this._pickSnapshot = undefined;
        this._syncing = false;
        useRecordObserver((record) => {
            void this._syncCustomFilter(record);
        });
        useEffect(
            () => {
                void this._syncCustomFilter(this.props.record);
            },
            () => [this.pickKey, this.props.readonly, this.props.record.resId]
        );
    }

    get pickKey() {
        return JSON.stringify({
            picks: this._picksFromRecord(this.props.record),
            operator: this.props.record.data.period_operator || "any",
        });
    }

    get lines() {
        const value = this.props.record.data[this.props.name];
        const records = value?.records || [];
        return [...records].sort((a, b) => {
            const seqA = a.data.sequence || 0;
            const seqB = b.data.sequence || 0;
            if (seqA !== seqB) {
                return seqA - seqB;
            }
            return (a.resId || 0) - (b.resId || 0);
        });
    }

    _picksFromRecord(record) {
        const lines = record.data[this.props.name]?.records || [];
        return lines.map((line) => ({
            id: line.resId || 0,
            field_name: line.data.field_name || false,
            period_mq_ids: x2mIds(line.data.period_mq_ids),
            period_year_ids: x2mIds(line.data.period_year_ids),
        }));
    }

    _picksHaveDates(picks) {
        return (picks || []).some(
            (pick) =>
                (pick.period_mq_ids && pick.period_mq_ids.length) ||
                (pick.period_year_ids && pick.period_year_ids.length)
        );
    }

    async _syncCustomFilter(record) {
        if (this.props.readonly || !record.resId || this._syncing) {
            return;
        }
        const picks = this._picksFromRecord(record);
        const operator = record.data.period_operator || "any";
        const snapshot = JSON.stringify({ picks, operator });
        const current = record.data.custom_filter || "[]";
        const currentEmpty = !current || current === "[]";
        // First open used to skip this RPC, so tags showed and Custom Filter
        // stayed "Match all records". Always copy when picks exist.
        if (snapshot === this._pickSnapshot && !(currentEmpty && this._picksHaveDates(picks))) {
            return;
        }
        this._pickSnapshot = snapshot;
        this._syncing = true;
        try {
            const raw = await this.orm.call(
                "dashboard.user.pref",
                "web_custom_filter_from_period_picks",
                [[record.resId], picks, operator]
            );
            const value = customFilterFromPeriodPayload(raw);
            const latest = record.data.custom_filter || "[]";
            if (latest !== value) {
                // Skip onchange: a missing Label on a date line makes OWL skip
                // (or wipe) Custom Filter. Write the domain on the form only.
                await record.model.mutex.exec(() =>
                    record._update({ custom_filter: value }, { withoutOnchange: true })
                );
            }
        } catch {
            this._pickSnapshot = undefined;
        } finally {
            this._syncing = false;
        }
    }
}

export const dashboardPeriodFilterBoxesField = {
    component: DashboardPeriodFilterBoxesField,
    displayName: _t("Dashboard Period Filter Boxes"),
    supportedTypes: ["one2many"],
    useSubView: true,
    isEmpty: () => false,
    extractProps: (
        { relatedFields, viewMode, views, widget, options, string, attrs },
        dynamicInfo
    ) => ({
        addLabel: attrs["add-label"],
        context: dynamicInfo.context,
        domain: dynamicInfo.domain,
        crudOptions: options,
        string,
        views,
        viewMode,
        relatedFields,
        widget,
    }),
};

registry
    .category("fields")
    .add("dashboard_period_filter_boxes", dashboardPeriodFilterBoxesField);
