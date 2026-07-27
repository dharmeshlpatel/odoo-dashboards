/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import {
    Many2ManyOrderedTagsField,
    many2ManyOrderedTagsField,
} from "@dashboard_engine/js/fields/many2many_ordered_tags_field";

const GRANULARITY_LABELS = {
    day: _t("Day"),
    week: _t("Week"),
    month: _t("Month"),
    quarter: _t("Quarter"),
    year: _t("Year"),
};

/**
 * Ordered Group By tags with v1-style date labels.
 *
 * Separators are facet-style text (``>``) from the ordered-tags widget — each
 * level keeps its own ×. V1-style period tags already carry labels like
 * ``Created on > Month`` (virtual ``x_<date>_<period>`` fields). For legacy
 * raw date/datetime tags, sibling ``groupby_granularity`` /
 * ``graph_groupby_granularity`` still formats the first level as
 * ``Created on > Day``.
 *
 * ``ttype`` is loaded as ``char`` (not ``selection``) so the relational model
 * never calls ``field.selection.find`` on a related-field stub that has no
 * selection list — that was the gear-form UncaughtPromise TypeError.
 */
export class DashboardGroupbyTagsField extends Many2ManyOrderedTagsField {
    get tags() {
        const tags = super.tags;
        if (!Array.isArray(tags) || !tags.length) {
            return tags || [];
        }
        // Pref form uses groupby_granularity; blueprint form uses
        // graph_groupby_granularity — accept either.
        const granularity =
            this.props.record.data.groupby_granularity ||
            this.props.record.data.graph_groupby_granularity ||
            "month";
        const granLabel = GRANULARITY_LABELS[granularity] || granularity;
        let firstDateTagged = false;

        return tags.map((tag) => {
            if (!tag) {
                return tag;
            }
            const rec = this._recordByTagId(tag);
            if (!rec || firstDateTagged) {
                return tag;
            }
            const ttype = rec.data?.ttype;
            if (ttype !== "date" && ttype !== "datetime") {
                return tag;
            }
            firstDateTagged = true;
            const base = tag.text || "";
            if (base.includes(" > ")) {
                return tag;
            }
            return {
                ...tag,
                text: `${base} > ${granLabel}`,
            };
        });
    }

    _recordByTagId(tag) {
        const records = this.props.record.data[this.props.name]?.records;
        if (!records || typeof records.find !== "function") {
            return null;
        }
        // Tag.id is the datapoint id; tag.resId is the ir.model.fields id.
        return (
            records.find((rec) => rec.id === tag.id) ||
            records.find((rec) => rec.resId === tag.resId) ||
            null
        );
    }
}

export const dashboardGroupbyTagsField = {
    ...many2ManyOrderedTagsField,
    component: DashboardGroupbyTagsField,
    relatedFields: (fieldInfo) => {
        const stock = many2ManyOrderedTagsField.relatedFields;
        const base =
            typeof stock === "function"
                ? stock(fieldInfo || { options: {} })
                : [{ name: "display_name", type: "char" }];
        // char — never selection — see class docstring.
        return [...(base || []), { name: "ttype", type: "char" }];
    },
};

registry.category("fields").add("dashboard_groupby_tags", dashboardGroupbyTagsField);
