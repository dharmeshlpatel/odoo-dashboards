/** @odoo-module **/

import {
    Component,
    onWillUnmount,
    onWillUpdateProps,
    useEffect,
    useState,
} from "@odoo/owl";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { getFieldDomain } from "@web/model/relational_model/utils";
import { useSpecialData } from "@web/views/fields/relational_utils";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Settings-style scope tick boxes for the dashboard gear popup.
 *
 * Presentation (label, help, mode) comes from the blueprint scopes — never
 * from host-app strings in this widget. Layout mirrors Odoo settings boxes:
 * ``restrict`` scopes sit alone on a row; ``include`` scopes pack two-across
 * (same chrome as v1's My Pipeline / Pipeline|Leads arrangement, driven by
 * mode + sequence rather than CRM-specific markup).
 *
 * The live form may mount this widget twice on ``scope_ids`` with different
 * domains (include vs restrict) so Data to Include and My Data stay separate.
 */
export class DashboardScopeCheckboxesField extends Component {
    static template = "dashboard_engine.DashboardScopeCheckboxesField";
    static components = { CheckBox };
    static props = {
        ...standardFieldProps,
        domain: { type: [Array, Function], optional: true },
        context: { type: Object, optional: true },
    };

    setup() {
        this.specialData = useSpecialData((orm, props) => {
            const { relation } = props.record.fields[props.name];
            const domain = getFieldDomain(props.record, props.name, props.domain);
            return orm.searchRead(
                relation,
                domain,
                ["display_label", "display_description", "sequence", "mode"],
                {
                    order: "sequence, id",
                    context: this.props.context || {},
                }
            );
        });
        this.idsToAdd = new Set();
        this.idsToRemove = new Set();
        this.debouncedCommitChanges = debounce(this.commitChanges.bind(this), 500);
        useBus(this.props.record.model.bus, "NEED_LOCAL_CHANGES", this.commitChanges.bind(this));
        onWillUnmount(this.commitChanges.bind(this));
        this.state = useState({ scopeWarning: "" });
        // useSpecialData resolves asynchronously — items are empty at mount.
        useEffect(
            () => {
                this._updateScopeWarning();
            },
            () => [this.specialData.data]
        );
        onWillUpdateProps(() => this._updateScopeWarning());
    }

    get items() {
        return this.specialData.data || [];
    }

    /**
     * Group scopes into settings rows: each restrict scope alone, include
     * scopes two per row (in sequence order).
     */
    get rows() {
        const rows = [];
        let includeBuffer = [];
        const flushIncludes = () => {
            while (includeBuffer.length) {
                rows.push(includeBuffer.splice(0, 2));
            }
        };
        for (const item of this.items) {
            if (item.mode === "restrict") {
                flushIncludes();
                rows.push([item]);
            } else {
                includeBuffer.push(item);
                if (includeBuffer.length === 2) {
                    rows.push(includeBuffer.splice(0, 2));
                }
            }
        }
        flushIncludes();
        return rows;
    }

    isSelected(item) {
        return this.props.record.data[this.props.name].currentIds.includes(item.id);
    }

    /**
     * Odoo settings style: help text sits under the label.
     * Only show a ? when there is no visible description line.
     */
    showHelpIcon(item) {
        return false;
    }

    commitChanges() {
        if (this.idsToAdd.size === 0 && this.idsToRemove.size === 0) {
            return;
        }
        const result = this.props.record.data[this.props.name].addAndRemove({
            add: [...this.idsToAdd],
            remove: [...this.idsToRemove],
        });
        this.idsToAdd.clear();
        this.idsToRemove.clear();
        return result;
    }

    onChange(resId, checked) {
        if (checked) {
            if (this.idsToRemove.has(resId)) {
                this.idsToRemove.delete(resId);
            } else {
                this.idsToAdd.add(resId);
            }
        } else {
            if (this.idsToAdd.has(resId)) {
                this.idsToAdd.delete(resId);
            } else {
                this.idsToRemove.add(resId);
            }
        }
        this.debouncedCommitChanges();
        this._updateScopeWarning();
    }

    onLabelClick(item) {
        if (this.props.readonly) {
            return;
        }
        this.onChange(item.id, !this.isSelected(item));
    }

    _updateScopeWarning() {
        const warning = this.props.record.data.scope_warning || "";
        if (!warning) {
            this.state.scopeWarning = "";
            return;
        }

        const includeScopes = this.items.filter((s) => s.mode === "include");
        if (!includeScopes.length) {
            this.state.scopeWarning = "";
            return;
        }

        const currentIds = this.props.record.data[this.props.name].currentIds;
        const pendingOn = new Set([...currentIds, ...this.idsToAdd]);
        this.idsToRemove.forEach((id) => pendingOn.delete(id));

        const anyIncludeOn = includeScopes.some((s) => pendingOn.has(s.id));
        this.state.scopeWarning = anyIncludeOn ? "" : warning;
    }
}

export const dashboardScopeCheckboxesField = {
    component: DashboardScopeCheckboxesField,
    displayName: _t("Dashboard Scope Checkboxes"),
    supportedTypes: ["many2many"],
    isEmpty: () => false,
    extractProps(fieldInfo, dynamicInfo) {
        return {
            domain: dynamicInfo.domain,
            context: dynamicInfo.context,
        };
    },
};

registry.category("fields").add("dashboard_scope_checkboxes", dashboardScopeCheckboxesField);
