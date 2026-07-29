/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
    many2ManyTagsField,
    Many2ManyTagsField,
} from "@web/views/fields/many2many_tags/many2many_tags_field";

/**
 * Many2ManyOrderedTagsField
 *
 * Ordered many2many tags. Selection order is stored in ``ordered_<field>``.
 *
 * Between tags, an optional separator is rendered as muted text (Odoo search
 * facet style — e.g. ``Stage > Company``), not as a fake deletable pill.
 * Each real tag still has its own × so levels can be removed individually.
 *
 * options.separator:
 *   - default ``">"`` (Group By chain)
 *   - ``false`` / ``""`` / ``null`` → no separators (Header Fields)
 *   - any string → that separator text (e.g. ``" at "``)
 */
export class Many2ManyOrderedTagsField extends Many2ManyTagsField {
    static template = "dashboard_engine.Many2ManyOrderedTagsField";
    static props = {
        ...Many2ManyTagsField.props,
        separator: { type: [String, Boolean], optional: true },
        labelFormat: { type: String, optional: true },
    };
    static defaultProps = {
        ...Many2ManyTagsField.defaultProps,
        separator: ">",
    };

    getTagProps(record) {
        const props = super.getTagProps(record);
        if (this.props.labelFormat === "string_name") {
            const label = record.data.field_description || record.data.display_name;
            const tech = record.data.name;
            props.text = tech ? `${label} (${tech})` : label;
        }
        return props;
    }

    /**
     * Resolved separator text, or null when separators are disabled.
     */
    get separatorText() {
        const sep = this.props.separator;
        if (sep === false || sep === null || sep === "") {
            return null;
        }
        return sep === true ? ">" : sep;
    }

    get tags() {
        const { record } = this.props;
        const fieldName = this.props.name;
        const value = record.data[fieldName];
        // StaticList.records is always an array once the datapoint exists; fall
        // back when the field is not yet hydrated (avoids .map/.find on undefined).
        const records = value?.records ?? [];

        const orderString = record.data[`ordered_${fieldName}`] || "";
        const selectedOrder = orderString
            .split(",")
            .map((value) => Number(value))
            .filter((id) => Boolean(id));

        // Order string stores database ids (resId), not datapoint ids.
        const recordByResId = new Map(records.map((rec) => [rec.resId, rec]));

        const orderedRecords = selectedOrder.length
            ? selectedOrder.map((id) => recordByResId.get(id)).filter(Boolean)
            : records;

        // Real tags only — separators are not tags (so × / keyboard delete
        // never hit a fake ">" chip).
        return orderedRecords.map((rec) => this.getTagProps(rec));
    }

    /**
     * Tags interleaved with separator markers for the template.
     */
    get displayItems() {
        const tags = this.tags;
        const sep = this.separatorText;
        const items = [];
        tags.forEach((tag, index) => {
            items.push({ type: "tag", key: `tag_${tag.id}`, tags: [tag] });
            if (sep && index < tags.length - 1) {
                items.push({
                    type: "sep",
                    key: `sep_${index}`,
                    text: sep,
                });
            }
        });
        return items;
    }

    async deleteTag(id) {
        if (typeof id === "string" && id.startsWith("sep_")) {
            return;
        }
        return super.deleteTag(id);
    }
}

export const many2ManyOrderedTagsField = {
    ...many2ManyTagsField,
    component: Many2ManyOrderedTagsField,
    relatedFields: (fieldInfo) => {
        const options = fieldInfo?.options || {};
        const base =
            typeof many2ManyTagsField.relatedFields === "function"
                ? many2ManyTagsField.relatedFields(fieldInfo)
                : [{ name: "display_name", type: "char" }];
        if (options.label_format === "string_name") {
            return [
                ...base,
                { name: "name", type: "char" },
                { name: "field_description", type: "char" },
            ];
        }
        return base;
    },
    extractProps(fieldInfo, dynamicInfo) {
        const props = many2ManyTagsField.extractProps(fieldInfo, dynamicInfo);
        const options = fieldInfo.options || {};
        if (Object.prototype.hasOwnProperty.call(options, "separator")) {
            props.separator = options.separator;
        } else {
            props.separator = ">";
        }
        if (options.label_format) {
            props.labelFormat = options.label_format;
        }
        return props;
    },
};

registry.category("fields").add("many2many_ordered_tags", many2ManyOrderedTagsField);
