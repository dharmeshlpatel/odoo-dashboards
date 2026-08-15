/** @odoo-module **/

/**
 * Studio shared field kit — stock Odoo OWL pieces used across all Studio pages.
 *
 * | Control   | Component |
 * |-----------|-----------|
 * | boolean   | CheckBox |
 * | many2one  | RecordSelector |
 * | many2many | MultiRecordSelector |
 * | date      | DateTimeInput (via ContextFieldValueWidget) |
 * | domain    | DashboardDomainSelectorDialog |
 * | image     | StudioBinaryImage |
 *
 * Char / text / selection use Bootstrap form-control / form-select with
 * `.o_ds_field` labels (same tokens as Odoo form labels).
 */

import { CheckBox } from "@web/core/checkbox/checkbox";
import {
    DashboardRecordSelector as RecordSelector,
    DashboardMultiRecordSelector as MultiRecordSelector,
} from "@dashboard_engine/js/fields/dashboard_no_search_more";

export { CheckBox, RecordSelector, MultiRecordSelector };

/** Shared empty-domain summary for Studio domain rows. */
export function domainSummaryText(domain, emptyLabel = "No domain set") {
    const text = (domain || "[]").trim() || "[]";
    if (text === "[]") {
        return emptyLabel;
    }
    return text.length > 72 ? `${text.slice(0, 69)}…` : text;
}
