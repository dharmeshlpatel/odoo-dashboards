/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Record } from "@web/model/record";
import { ImageField } from "@web/views/fields/image/image_field";

/**
 * Standalone ImageField for Studio draft state (no live form save).
 * Changes flow through onChange; parent persists on Setup save.
 */
export class StudioBinaryImage extends Component {
    static template = "dashboard_engine.StudioBinaryImage";
    static components = { Record, ImageField };
    static props = {
        value: { optional: true },
        onChange: { type: Function },
        fieldName: { type: String, optional: true },
        width: { type: Number, optional: true },
        height: { type: Number, optional: true },
    };
    static defaultProps = {
        fieldName: "image",
        width: 64,
        height: 64,
    };

    setup() {
        this.fields = {
            [this.props.fieldName]: {
                type: "binary",
                string: "Image",
            },
        };
        this.hooks = {
            onRecordChanged: (_record, changes) => {
                if (Object.prototype.hasOwnProperty.call(changes, this.props.fieldName)) {
                    this.props.onChange(changes[this.props.fieldName] || false);
                }
            },
        };
    }

    get fieldNames() {
        return [this.props.fieldName];
    }

    get values() {
        return {
            [this.props.fieldName]: this.props.value || false,
        };
    }
}
