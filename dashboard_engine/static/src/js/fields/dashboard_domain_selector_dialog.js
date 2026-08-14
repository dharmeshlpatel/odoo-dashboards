/** @odoo-module **/

import { DomainSelectorDialog } from "@web/core/domain_selector_dialog/domain_selector_dialog";
import { DashboardDomainSelector } from "@dashboard_engine/js/fields/dashboard_domain_field";

/**
 * Domain dialog that hides dashboard date-period virtual fields
 * (``create_date > Month``, …). Those tags are for Group By only.
 */
export class DashboardDomainSelectorDialog extends DomainSelectorDialog {
    static components = {
        ...DomainSelectorDialog.components,
        DomainSelector: DashboardDomainSelector,
    };
}
