/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import {
    FieldSelectorField,
    fieldSelectorField,
} from "@web/views/fields/field_selector/field_selector_field";

/**
 * Field drill-down limited to many2one chains (card link paths).
 */
export class DashboardRelationPathSelectorField extends FieldSelectorField {
    filter(fieldDef) {
        if (!super.filter(fieldDef)) {
            return false;
        }
        return fieldDef.type === "many2one";
    }
}

export const dashboardRelationPathSelectorField = {
    ...fieldSelectorField,
    component: DashboardRelationPathSelectorField,
    displayName: _t("Relation path"),
};

registry.category("fields").add(
    "dashboard_relation_path",
    dashboardRelationPathSelectorField
);
