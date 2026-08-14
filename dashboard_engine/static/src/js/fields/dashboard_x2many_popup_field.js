/** @odoo-module **/

import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

/**
 * Editable One2many / Many2many that opens the form icon as a popup
 * (FormViewDialog), not a full-screen form action.
 *
 * Core ``open_form_view`` uses ``switchToForm`` → ``doAction``. Studio
 * expands rows in-place; Advanced should use a dialog for the same job.
 */
export class DashboardX2ManyPopupField extends X2ManyField {
    get rendererProps() {
        const props = super.rendererProps;
        if (this.props.viewMode === "list") {
            props.onOpenFormView = (record) => this.openFormPopup(record);
        }
        return props;
    }

    openFormPopup(record) {
        return this._openRecord({
            record,
            context: this.props.context,
            readonly: this.props.readonly,
        });
    }
}

export const dashboardX2ManyPopupField = {
    ...x2ManyField,
    component: DashboardX2ManyPopupField,
};

registry.category("fields").add("dashboard_x2many_popup", dashboardX2ManyPopupField);
