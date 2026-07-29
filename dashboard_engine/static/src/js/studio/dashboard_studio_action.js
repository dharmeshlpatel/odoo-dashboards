/** @odoo-module **/

import { Component, onWillStart, onPatched, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { DomainSelectorDialog } from "@web/core/domain_selector_dialog/domain_selector_dialog";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import {
    rowsFromContextRaw,
    serializeContextRows,
    createEmptyContextRow,
    emptyGroupRule,
    collectGroupXmlids,
    applyGroupLabels,
    VALUE_TYPES,
} from "../fields/context_kv_utils";

const MANAGE_SECTIONS = [
    { id: "menu_views", label: "Views" },
    { id: "menu_new", label: "New" },
    { id: "menu_reports", label: "Reports" },
];

const MEASURE_AGGREGATORS = [
    { value: "sum", label: _t("Total") },
    { value: "avg", label: _t("Average") },
    { value: "max", label: _t("Maximum") },
    { value: "min", label: _t("Minimum") },
];

const HEADER_IMAGE_STYLES = [
    { value: "avatar", label: _t("Fit the whole picture (logos, avatars)") },
    { value: "cover", label: _t("Fill the square, cropping edges (photos)") },
];

const HEADER_SEPARATORS = [
    { value: ", ", label: _t("Paris, France") },
    { value: " at ", label: _t("Sales Manager at Acme") },
    { value: " | ", label: _t("Service | Furniture") },
    { value: " - ", label: _t("Acme - Paris") },
    { value: " ", label: _t("Acme Paris") },
];

const ZONES = [
    { id: "header", label: "Header", icon: "fa-header", section: null },
    { id: "primary", label: "Chart & Primary", icon: "fa-area-chart", section: null },
    { id: "kpis", label: "KPIs", icon: "fa-tachometer", section: "kpi" },
    { id: "totals", label: "Totals", icon: "fa-calculator", section: "button_box" },
    { id: "shortcuts", label: "Shortcuts", icon: "fa-external-link", section: "bottom" },
    { id: "manage", label: "Manage menu", icon: "fa-bars", section: "menu" },
    { id: "config", label: "Configuration", icon: "fa-cog", section: null },
];

const EMPTY_EDITOR = () => ({
    label: "",
    label_plural: "",
    icon: "",
    style: "default",
    show_if_zero: true,
    action_xmlid: "",
    action_method: "",
    action_model: "",
    amount_field: "",
    count_field: "",
    compute_model: "",
    relate_field: "",
    compute_domain: "[]",
    value_mode: "count",
    module_depends: "",
    condition_ids: [],
    kind: "subtitle",
    alignment: "left",
    field_names: "",
    primary_button_label: "",
    primary_action_xmlid: "",
    primary_action_context: "{}",
    contextRows: [createEmptyContextRow()],
    graph_caption: "",
    graph_measure: "",
    graph_groupby: "",
    graph_groupby_field_ids: [],
    graph_measure_field_id: false,
    graph_measure_aggregator: "sum",
    graph_data_field: "",
    graph_domain: "[]",
    period_field_id: false,
    closed_period_field_id: false,
    include_child_records: false,
    header_title_field: "",
    header_image_field: "",
    header_image_style: "avatar",
});

const EMPTY_SETUP = () => ({
    host_model_id: false,
    host_model_label: "",
    menu_name: "",
    menu_parent_id: false,
    menu_parent_name: "",
    menu_sequence: 50,
    company_id: false,
    company_name: "",
    module_ids: [],
    module_names: [],
    share_link_ids: [],
    share_link_names: [],
});

export class DashboardStudioAction extends Component {
    static template = "dashboard_engine.DashboardStudioAction";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.ZONES = ZONES;
        this.MANAGE_SECTIONS = MANAGE_SECTIONS;
        this.LAYOUT_SPANS = [3, 4, 6, 8, 12];
        this.MEASURE_AGGREGATORS = MEASURE_AGGREGATORS;
        this.HEADER_IMAGE_STYLES = HEADER_IMAGE_STYLES;
        this.HEADER_SEPARATORS = HEADER_SEPARATORS;
        this.CONTEXT_VALUE_TYPES = VALUE_TYPES;
        this.previewChartRef = useRef("previewChart");
        this._previewChart = null;
        this._dragSlotId = null;
        this._dragScopeId = null;
        this._dragHeaderId = null;
        this.state = useState({
            zone: "kpis",
            studioMode: "content", // setup | content | layout
            payload: null,
            selectedSlotId: null,
            selectedHeaderId: null,
            manageSection: "menu_views",
            layoutDraft: null,
            setup: EMPTY_SETUP(),
            setupDirty: false,
            setupBanner: null,
            setupQuery: {
                host: "",
                menu: "",
                module: "",
                share: "",
                company: "",
            },
            setupResults: {
                host: [],
                menu: [],
                module: [],
                share: [],
                company: [],
            },
            contextGroupQuery: {},
            contextGroupHits: {},
            editor: EMPTY_EDITOR(),
            catalogs: {
                hostFields: [],
                graphFields: [],
                graphFieldRecords: [],
                graphMeasureFields: [],
                graphDateFields: [],
                conditions: [],
                icons: [],
                actions: [],
                samples: [],
            },
            actionQuery: "",
            sampleQuery: "",
            sampleId: null,
            preview: null,
            previewLoading: false,
            dirty: false,
            layoutDirty: false,
            loading: true,
            saving: false,
            linkPathHopFields: [],
            linkPathExtraHop: false,
        });
        onWillStart(async () => {
            await this.loadPayload();
            await this.loadCatalogs();
            await this.loadSamples("");
            await this.loadPreview();
        });
        onPatched(() => {
            this._renderPreviewChart();
        });
    }

    get blueprintId() {
        const params = this.props.action?.params || {};
        const ctx = this.props.action?.context || {};
        return params.blueprint_id || ctx.active_id;
    }

    get zoneMeta() {
        return ZONES.find((z) => z.id === this.state.zone) || ZONES[2];
    }

    get slotsForZone() {
        if (!this.state.payload) {
            return [];
        }
        const slots = this.state.payload.slots || [];
        if (this.state.zone === "manage") {
            return slots.filter((s) =>
                ["menu_views", "menu_new", "menu_reports"].includes(s.section)
            );
        }
        const section = this.zoneMeta.section;
        if (!section) {
            return [];
        }
        return slots.filter((s) => s.section === section);
    }

    get selectedSlot() {
        const id = this.state.selectedSlotId;
        return this.slotsForZone.find((s) => s.id === id) || this.slotsForZone[0] || null;
    }

    get selectedHeader() {
        const headers = this.state.payload?.headers || [];
        const id = this.state.selectedHeaderId;
        return headers.find((h) => h.id === id) || headers[0] || null;
    }

    /**
     * Merge unsaved slot editor fields into map items (match by key/id).
     */
    _overlaySelectedSlot(items) {
        const list = (items || []).map((item) => ({ ...item }));
        if (!this.state.dirty || !this.selectedSlot) {
            return list;
        }
        if (!["kpis", "totals", "shortcuts", "manage"].includes(this.state.zone)) {
            return list;
        }
        const slot = this.selectedSlot;
        const ed = this.state.editor;
        return list.map((item) => {
            if (item.key !== slot.key && item.id !== slot.id) {
                return item;
            }
            const label = (ed.label || "").trim() || item.label || item.name;
            return {
                ...item,
                label,
                label_plural: (ed.label_plural || "").trim() || item.label_plural,
                name: label,
                icon: ed.icon || item.icon,
                style: ed.style || item.style,
                _draft: true,
            };
        });
    }

    _slotsFromPayload(section) {
        return (this.state.payload?.slots || [])
            .filter((s) => s.section === section)
            .map((s) => ({
                id: s.id,
                key: s.key,
                label: s.label,
                name: s.name || s.label,
                icon: s.icon,
                count: null,
                style: s.style,
            }));
    }

    get kpisPreview() {
        let items;
        if (this.state.preview?.ok && this.state.preview.slots?.kpis) {
            items = this.state.preview.slots.kpis.slice(0, 8);
        } else {
            items = this._slotsFromPayload("kpi").slice(0, 8);
        }
        return this._overlaySelectedSlot(items);
    }

    get totalsPreview() {
        let items;
        if (this.state.preview?.ok && this.state.preview.slots?.button_box) {
            items = this.state.preview.slots.button_box.slice(0, 6);
        } else {
            items = this._slotsFromPayload("button_box").slice(0, 6);
        }
        return this._overlaySelectedSlot(items);
    }

    get shortcutsPreview() {
        let items;
        if (this.state.preview?.ok && this.state.preview.slots?.buttons) {
            items = this.state.preview.slots.buttons.slice(0, 6);
        } else {
            items = this._slotsFromPayload("bottom").slice(0, 6);
        }
        return this._overlaySelectedSlot(items);
    }

    get manageViewsPreview() {
        let items;
        if (this.state.preview?.ok) {
            items = this.state.preview.slots?.menu?.views || [];
        } else {
            items = this._slotsFromPayload("menu_views");
        }
        return this._overlaySelectedSlot(items).slice(0, 4);
    }

    get manageNewPreview() {
        let items;
        if (this.state.preview?.ok) {
            items = this.state.preview.slots?.menu?.new || [];
        } else {
            items = this._slotsFromPayload("menu_new");
        }
        return this._overlaySelectedSlot(items).slice(0, 4);
    }

    get manageReportsPreview() {
        let items;
        if (this.state.preview?.ok) {
            items = this.state.preview.slots?.menu?.reports || [];
        } else {
            items = this._slotsFromPayload("menu_reports");
        }
        return this._overlaySelectedSlot(items).slice(0, 4);
    }

    get previewTitle() {
        return this.state.preview?.title || this.state.payload?.name || "Dashboard";
    }

    get previewPrimaryLabel() {
        if (
            this.state.dirty &&
            this.state.zone === "primary" &&
            (this.state.editor.primary_button_label || "").trim()
        ) {
            return this.state.editor.primary_button_label.trim();
        }
        return (
            this.state.preview?.primary_label ||
            this.state.payload?.primary_button_label ||
            "Open"
        );
    }

    get previewGraphCaption() {
        if (
            this.state.dirty &&
            (this.state.zone === "primary" || this.state.zone === "config") &&
            this.state.editor.graph_caption != null
        ) {
            return this.state.editor.graph_caption || "Analysis";
        }
        return this.state.preview?.graph_caption || this.state.payload?.graph_caption || "Analysis";
    }

    get previewGraphBars() {
        const bars = this.state.preview?.graph_bars;
        if (bars && bars.length) {
            return bars;
        }
        return [40, 70, 55, 85, 45, 62];
    }

    get previewGraphNeedsSave() {
        if (!this.state.dirty || this.state.zone !== "config") {
            return false;
        }
        const ed = this.state.editor;
        const p = this.state.payload || {};
        const groupbyDirty =
            JSON.stringify(ed.graph_groupby_field_ids || []) !==
            JSON.stringify(p.graph_groupby_field_ids || []);
        const measureDirty =
            (ed.graph_measure_field_id || false) !== (p.graph_measure_field_id || false) ||
            (ed.graph_measure_aggregator || false) !== (p.graph_measure_aggregator || false);
        const linkDirty = (ed.graph_data_field || "") !== (p.graph_data_field || "");
        const includeChildDirty =
            Boolean(ed.include_child_records) !== Boolean(p.include_child_records);
        const domainDirty =
            (ed.graph_domain || "[]") !== (p.graph_domain != null ? p.graph_domain : "[]");
        return groupbyDirty || measureDirty || linkDirty || includeChildDirty || domainDirty;
    }

    get previewConfigSummary() {
        const p = this.state.payload || {};
        const ed = this.state.editor;
        const dirtyConfig = this.state.dirty && this.state.zone === "config";
        const groupbyIds = dirtyConfig
            ? ed.graph_groupby_field_ids || []
            : p.graph_groupby_field_ids || [];
        const byId = new Map(
            (this.state.catalogs.graphFieldRecords || []).map((f) => [f.id, f])
        );
        const groupbyLabels = groupbyIds.map((id, idx) => {
            const meta = byId.get(id);
            return (
                meta?.string ||
                meta?.field_description ||
                p.graph_groupby_field_names?.[idx] ||
                `#${id}`
            );
        });
        let measureLabel = "Count";
        const measureId = dirtyConfig ? ed.graph_measure_field_id : p.graph_measure_field_id;
        if (measureId) {
            const mf =
                (this.state.catalogs.graphMeasureFields || []).find((f) => f.id === measureId) ||
                byId.get(measureId);
            const agg = dirtyConfig ? ed.graph_measure_aggregator : p.graph_measure_aggregator;
            const name = mf?.string || mf?.field_description || p.graph_measure || `#${measureId}`;
            measureLabel = agg ? `${name} (${agg})` : name;
        } else if (!dirtyConfig && p.graph_measure && p.graph_measure !== "__count") {
            measureLabel = p.graph_measure;
        }
        const scopes = (p.scopes || []).filter((s) => s.default_on).map((s) => s.name);
        return {
            scopes: scopes.length ? scopes.join(", ") : "none on by default",
            measure: measureLabel,
            groupby: groupbyLabels.length ? groupbyLabels.join(" → ") : "—",
            model: p.graph_model || p.host_model || "—",
        };
    }

    get previewHeaderLines() {
        let lines;
        if (this.state.preview?.ok) {
            lines = (this.state.preview.header_lines || []).map((h) => ({ ...h }));
        } else {
            lines = (this.state.payload?.headers || []).map((h) => ({
                id: h.id,
                kind: h.kind || "subtitle",
                alignment: h.alignment || "left",
                icon: h.icon,
                text: h.field_names || "",
                field_names: h.field_names || "",
            }));
        }
        const selected = this.selectedHeader;
        if (this.state.zone === "header" && selected && this.state.dirty) {
            const ed = this.state.editor;
            const fieldsChanged =
                (ed.field_names || "") !== (selected.field_names || "");
            lines = lines.map((h) => {
                if (h.id !== selected.id) {
                    return h;
                }
                return {
                    ...h,
                    kind: ed.kind || h.kind || "subtitle",
                    alignment: ed.alignment || h.alignment || "left",
                    icon: ed.icon || h.icon,
                    text: fieldsChanged
                        ? (ed.field_names || "").trim() || h.text
                        : h.text || (ed.field_names || "").trim(),
                };
            });
        }
        return lines;
    }

    _headerLineMatches(h, kind, alignment) {
        const k = h.kind || "subtitle";
        const a = h.alignment || "left";
        return k === kind && a === alignment;
    }

    headerAlignFlexClass(h) {
        const a = (h && h.alignment) || "left";
        if (a === "center") {
            return "justify-content-center";
        }
        if (a === "right") {
            return "justify-content-end";
        }
        return "justify-content-start";
    }

    get previewHeaderSubtitles() {
        return this.previewHeaderLines.filter(
            (h) => h.kind === "subtitle" && h.text
        );
    }

    _headerLineIsSideTags(h) {
        if ((h.kind || "subtitle") !== "inline") {
            return false;
        }
        if ((h.alignment || "left") !== "right") {
            return false;
        }
        const names = this._parseHeaderFieldNames(h.field_names);
        if (!names.length) {
            return false;
        }
        const byName = new Map(
            (this.state.catalogs.hostFields || []).map((f) => [f.name, f])
        );
        return names.every((name) => {
            const ttype = byName.get(name)?.ttype;
            return ttype === "many2many" || ttype === "one2many";
        });
    }

    get previewHeaderInline() {
        return this.previewHeaderLines.filter(
            (h) => h.kind === "inline" && h.text && !this._headerLineIsSideTags(h)
        );
    }

    get previewHeaderLeft() {
        return this.previewHeaderInline.filter(
            (h) => (h.alignment || "left") === "left"
        );
    }

    get previewHeaderCenter() {
        return this.previewHeaderInline.filter((h) => h.alignment === "center");
    }

    get previewHeaderRight() {
        return this.previewHeaderLines.filter(
            (h) => this._headerLineIsSideTags(h) && h.text
        );
    }

    get headerLineFieldCatalog() {
        return (this.state.catalogs.hostFields || []).filter(
            (f) => f.name !== "id" && f.ttype !== "binary"
        );
    }

    get headerImageFieldCatalog() {
        return (this.state.catalogs.hostFields || []).filter((f) => f.ttype === "binary");
    }

    _parseHeaderFieldNames(fieldNames) {
        return (fieldNames || "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
    }

    _headerFieldLabel(name) {
        const meta = (this.state.catalogs.hostFields || []).find((f) => f.name === name);
        if (meta?.string) {
            return `${meta.string} (${name})`;
        }
        return name;
    }

    headerFieldChips(header) {
        return this._parseHeaderFieldNames(header?.field_names).map((name, index) => ({
            name,
            label: this._headerFieldLabel(name),
            index,
        }));
    }

    headerFieldIsSelected(header, fieldName) {
        return this._parseHeaderFieldNames(header?.field_names).includes(fieldName);
    }

    headerLineShowIcon(header) {
        return header?.kind === "inline";
    }

    headerLineShowSeparator(header) {
        const count = this._parseHeaderFieldNames(header?.field_names).length;
        if (count < 2) {
            return false;
        }
        return !this._headerLineIsSideTags(header);
    }

    isHeaderRowSelected(headerId) {
        return this.state.selectedHeaderId === headerId;
    }

    get hasLivePreview() {
        return Boolean(this.state.preview?.ok);
    }

    _isGroupByCatalogField(field) {
        if (!field || field.name === "id") {
            return false;
        }
        if (field.ttype === "date" || field.ttype === "datetime") {
            return field.name.startsWith("x_");
        }
        return field.store !== false;
    }

    get graphGroupByCatalog() {
        return (this.state.catalogs.graphFieldRecords || []).filter((f) =>
            this._isGroupByCatalogField(f)
        );
    }

    get graphGroupBySelectedChips() {
        const ids = this.state.editor.graph_groupby_field_ids || [];
        const byId = new Map(
            (this.state.catalogs.graphFieldRecords || []).map((f) => [f.id, f])
        );
        const payloadNames = this.state.payload?.graph_groupby_field_names || [];
        const payloadIds = this.state.payload?.graph_groupby_field_ids || [];
        return ids.map((id, index) => {
            const meta = byId.get(id);
            const payloadIdx = payloadIds.indexOf(id);
            const label =
                meta?.string ||
                meta?.field_description ||
                (payloadIdx >= 0 ? payloadNames[payloadIdx] : null) ||
                `#${id}`;
            return { id, label, index };
        });
    }

    get linkPathRows() {
        const segments = (this.state.editor.graph_data_field || "")
            .split(".")
            .filter(Boolean);
        const count = Math.max(1, segments.length + (this.state.linkPathExtraHop ? 1 : 0));
        const rows = [];
        for (let i = 0; i < count; i++) {
            rows.push({
                index: i,
                value: segments[i] || "",
                options: this.state.linkPathHopFields[i] || [],
                showSep: i < count - 1,
            });
        }
        return rows;
    }

    get canAddLinkPathHop() {
        if (this.state.linkPathExtraHop) {
            return false;
        }
        const segments = (this.state.editor.graph_data_field || "")
            .split(".")
            .filter(Boolean);
        if (!segments.length) {
            return false;
        }
        const lastIdx = segments.length - 1;
        const opts = this.state.linkPathHopFields[lastIdx] || [];
        const sel = opts.find((f) => f.name === segments[lastIdx]);
        return Boolean(sel?.relation);
    }

    get canRemoveLinkPathHop() {
        return Boolean(
            (this.state.editor.graph_data_field || "").split(".").filter(Boolean).length
        );
    }

    get showMeasureAggregator() {
        return Boolean(this.state.editor.graph_measure_field_id);
    }

    isMapSlotSelected(item) {
        const slot = this.selectedSlot;
        if (!slot || !item) {
            return false;
        }
        return item.key === slot.key || item.id === slot.id;
    }

    get canStructureEdit() {
        return ["kpis", "totals", "shortcuts", "manage", "header"].includes(this.state.zone);
    }

    get canSave() {
        if (this.state.studioMode === "setup") {
            return this.state.setupDirty;
        }
        if (this.state.zone === "config") {
            return this.state.dirty;
        }
        return this.state.dirty;
    }

    get headerChipHost() {
        return (
            this.state.setup?.host_model_label ||
            this.state.payload?.host_model_label ||
            this.state.payload?.host_model ||
            ""
        );
    }

    get headerChipMenu() {
        const name =
            this.state.setup?.menu_name || this.state.payload?.menu_name || "";
        return name || _t("No menu name");
    }

    get moduleChips() {
        const ids = this.state.setup.module_ids || [];
        const names = this.state.setup.module_names || [];
        return ids.map((id, i) => ({ id, name: names[i] || `#${id}` }));
    }

    get shareChips() {
        const ids = this.state.setup.share_link_ids || [];
        const names = this.state.setup.share_link_names || [];
        return ids.map((id, i) => ({ id, name: names[i] || `#${id}` }));
    }

    markDirty() {
        this.state.dirty = true;
    }

    markSetupDirty() {
        this.state.setupDirty = true;
    }

    _syncSetupFromPayload(payload) {
        if (!payload) {
            this.state.setup = EMPTY_SETUP();
            return;
        }
        this.state.setup = {
            host_model_id: payload.host_model_id || false,
            host_model_label: payload.host_model_label || payload.host_model || "",
            menu_name: payload.menu_name || "",
            menu_parent_id: payload.menu_parent_id || false,
            menu_parent_name: payload.menu_parent_name || "",
            menu_sequence: payload.menu_sequence ?? 50,
            company_id: payload.company_id || false,
            company_name: payload.company_name || "",
            module_ids: [...(payload.module_ids || [])],
            module_names: [...(payload.module_names || [])],
            share_link_ids: [...(payload.share_link_ids || [])],
            share_link_names: [...(payload.share_link_names || [])],
        };
        this.state.setupDirty = false;
        this.state.setupResults = {
            host: [],
            menu: [],
            module: [],
            share: [],
            company: [],
        };
    }

    async loadPayload() {
        this.state.loading = true;
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "get_studio_payload",
                [[this.blueprintId]]
            );
            this.state.payload = payload;
            this.state.layoutDraft = JSON.parse(
                JSON.stringify(payload.layout || { version: 1, rows: [] })
            );
            this.state.layoutDirty = false;
            this._syncSetupFromPayload(payload);
            this._syncEditorFromSelection();
            this.state.dirty = false;
            this.state.setupBanner = null;
            await this.loadPreview();
        } finally {
            this.state.loading = false;
        }
    }

    get layoutRows() {
        return this.state.layoutDraft?.rows || [];
    }

    get usedLayoutWidgetTypes() {
        const used = new Set();
        for (const row of this.layoutRows) {
            for (const col of row.cols || []) {
                const t = col.widget?.type;
                if (t && t !== "richtext") {
                    used.add(t);
                }
            }
        }
        return used;
    }

    get layoutPalette() {
        const labels = this.state.payload?.layout_widget_labels || {};
        const used = this.usedLayoutWidgetTypes;
        return Object.keys(labels)
            .filter((t) => !used.has(t))
            .map((t) => ({ type: t, label: labels[t] }));
    }

    layoutWidgetLabel(widgetType) {
        const labels = this.state.payload?.layout_widget_labels || {};
        return labels[widgetType] || widgetType;
    }

    colLabel(col) {
        const type = col?.widget?.type;
        return this.layoutWidgetLabel(type);
    }

    setStudioMode(mode) {
        if (mode === "layout") {
            this.state.studioMode = "layout";
        } else if (mode === "setup") {
            this.state.studioMode = "setup";
        } else {
            this.state.studioMode = "content";
        }
    }

    openSetupMode() {
        this.setStudioMode("setup");
    }

    markLayoutDirty() {
        this.state.layoutDirty = true;
    }

    _newId(prefix) {
        return `${prefix}_${Date.now().toString(36)}_${Math.floor(Math.random() * 1000)}`;
    }

    addLayoutRow() {
        const row = { id: this._newId("r"), cols: [] };
        this.state.layoutDraft.rows.push(row);
        this.markLayoutDirty();
    }

    removeLayoutRow(rowId) {
        this.state.layoutDraft.rows = this.layoutRows.filter((r) => r.id !== rowId);
        this.markLayoutDirty();
    }

    onPaletteAddClick(ev) {
        const widgetType = ev.currentTarget.dataset.widgetType;
        this.addWidgetToLastRow(widgetType);
    }

    addWidgetToLastRow(widgetType) {
        const rows = this.layoutRows;
        if (!rows.length) {
            return;
        }
        this.addWidgetToRow(rows[rows.length - 1].id, widgetType);
    }

    onAddWidgetSelect(ev) {
        const rowId = ev.currentTarget.dataset.rowId;
        const widgetType = ev.target.value;
        ev.target.value = "";
        if (widgetType) {
            this.addWidgetToRow(rowId, widgetType);
        }
    }

    onMoveLayoutRowUp(ev) {
        this.moveLayoutRow(ev.currentTarget.dataset.rowId, -1);
    }

    onMoveLayoutRowDown(ev) {
        this.moveLayoutRow(ev.currentTarget.dataset.rowId, 1);
    }

    onRemoveLayoutRow(ev) {
        this.removeLayoutRow(ev.currentTarget.dataset.rowId);
    }

    onRemoveLayoutCol(ev) {
        const { rowId, colId } = ev.currentTarget.dataset;
        this.removeLayoutCol(rowId, colId);
    }

    addWidgetToRow(rowId, widgetType) {
        if (!widgetType) {
            return;
        }
        if (this.usedLayoutWidgetTypes.has(widgetType)) {
            this.notification.add(_t("That widget is already on the page."), {
                type: "warning",
            });
            return;
        }
        const row = this.layoutRows.find((r) => r.id === rowId);
        if (!row) {
            return;
        }
        const used = (row.cols || []).reduce((s, c) => s + (c.span || 0), 0);
        const span = Math.min(12, Math.max(3, 12 - used)) || 12;
        if (used + span > 12) {
            this.notification.add(_t("This row is full (max 12 columns)."), {
                type: "warning",
            });
            return;
        }
        row.cols.push({
            id: this._newId("c"),
            span,
            widget: { type: widgetType },
        });
        this.markLayoutDirty();
    }

    onColSpanChange(ev) {
        const { rowId, colId } = ev.currentTarget.dataset;
        this.setColSpan(rowId, colId, ev.target.value);
    }

    setColSpan(rowId, colId, span) {
        const row = this.layoutRows.find((r) => r.id === rowId);
        const col = row?.cols?.find((c) => c.id === colId);
        if (!col) {
            return;
        }
        col.span = Number(span);
        this.markLayoutDirty();
    }

    removeLayoutCol(rowId, colId) {
        const row = this.layoutRows.find((r) => r.id === rowId);
        if (!row) {
            return;
        }
        row.cols = (row.cols || []).filter((c) => c.id !== colId);
        this.markLayoutDirty();
    }

    moveLayoutRow(rowId, delta) {
        const rows = this.layoutRows;
        const idx = rows.findIndex((r) => r.id === rowId);
        const next = idx + delta;
        if (idx < 0 || next < 0 || next >= rows.length) {
            return;
        }
        [rows[idx], rows[next]] = [rows[next], rows[idx]];
        this.markLayoutDirty();
    }

    async resetLayout() {
        const defLayout = await this.orm.call(
            "dashboard.blueprint",
            "studio_default_layout",
            []
        );
        this.state.layoutDraft = defLayout;
        this.markLayoutDirty();
    }

    async saveLayout() {
        if (!this.state.layoutDirty || this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_write_layout",
                [[this.blueprintId], this.state.layoutDraft]
            );
            this.state.payload = payload;
            this.state.layoutDraft = JSON.parse(JSON.stringify(payload.layout));
            this.state.layoutDirty = false;
            this.notification.add(_t("Layout saved"), { type: "success" });
            await this.loadPreview();
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Layout save failed"),
                { type: "danger" }
            );
        } finally {
            this.state.saving = false;
        }
    }

    async clearCustomLayout() {
        this.state.saving = true;
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_write_layout",
                [[this.blueprintId], false]
            );
            this.state.payload = payload;
            this.state.layoutDraft = JSON.parse(JSON.stringify(payload.layout));
            this.state.layoutDirty = false;
            this.notification.add(_t("Reset to classic card layout"), { type: "info" });
        } finally {
            this.state.saving = false;
        }
    }

    async loadSamples(term) {
        this.state.sampleQuery = term || "";
        const samples = await this.orm.call(
            "dashboard.blueprint",
            "studio_sample_records",
            [[this.blueprintId], term || "", 20]
        );
        this.state.catalogs.samples = samples;
        if (!this.state.sampleId && samples.length) {
            this.state.sampleId = samples[0].id;
        }
    }

    async loadPreview() {
        this.state.previewLoading = true;
        try {
            const preview = await this.orm.call(
                "dashboard.blueprint",
                "studio_preview_payload",
                [[this.blueprintId], this.state.sampleId || false]
            );
            this.state.preview = preview;
            if (preview?.res_id) {
                this.state.sampleId = preview.res_id;
            }
        } catch (_err) {
            this.state.preview = null;
        } finally {
            this.state.previewLoading = false;
        }
    }

    async onSampleQueryInput(ev) {
        await this.loadSamples(ev.target.value);
    }

    async onSampleSelect(ev) {
        const raw = ev.target.value;
        await this.selectSample(raw ? Number(raw) : false);
    }

    async selectSample(sampleId) {
        this.state.sampleId = sampleId;
        await this.loadPreview();
    }

    async loadCatalogs() {
        const bp = this.blueprintId;
        const [hostFields, icons] = await Promise.all([
            this.orm.call("dashboard.blueprint", "studio_model_fields", [[bp], null, null]),
            this.orm.call("dashboard.blueprint", "studio_header_icons", [[bp]]),
        ]);
        let graphFields = hostFields;
        const graphModel = this.state.payload?.graph_model;
        if (graphModel && graphModel !== this.state.payload?.host_model) {
            graphFields = await this.orm.call(
                "dashboard.blueprint",
                "studio_model_fields",
                [[bp], graphModel, null]
            );
        }
        let graphDateFields = [];
        let graphFieldRecords = [];
        let graphMeasureFields = [];
        if (graphModel) {
            graphFieldRecords = await this.orm.searchRead(
                "ir.model.fields",
                [["model", "=", graphModel]],
                ["id", "name", "field_description", "ttype", "store"],
                { order: "field_description", limit: 500 }
            );
            graphFieldRecords = graphFieldRecords.map((f) => ({
                id: f.id,
                name: f.name,
                string: f.field_description || f.name,
                field_description: f.field_description,
                ttype: f.ttype,
                store: f.store,
            }));
            graphMeasureFields = graphFieldRecords.filter(
                (f) =>
                    f.store !== false &&
                    ["integer", "float", "monetary"].includes(f.ttype)
            );
            graphDateFields = graphFieldRecords
                .filter((f) => f.ttype === "date" || f.ttype === "datetime")
                .map((f) => ({
                    id: f.id,
                    name: f.name,
                    string: f.string,
                }));
        }
        this.state.catalogs.hostFields = hostFields;
        this.state.catalogs.graphFields = graphFields;
        this.state.catalogs.graphFieldRecords = graphFieldRecords;
        this.state.catalogs.graphMeasureFields = graphMeasureFields;
        this.state.catalogs.graphDateFields = graphDateFields;
        this.state.catalogs.icons = icons;
        await this.refreshConditionCatalog();
        await this.searchActions("");
        await this.refreshLinkPathCatalogs();
    }

    async refreshConditionCatalog() {
        const bp = this.blueprintId;
        if (!bp) {
            this.state.catalogs.conditions = [];
            return;
        }
        const model =
            this.state.editor?.compute_model ||
            this.selectedSlot?.compute_model ||
            null;
        try {
            this.state.catalogs.conditions = await this.orm.call(
                "dashboard.blueprint",
                "studio_condition_catalog",
                [[bp]],
                { model: model || null }
            );
        } catch {
            this.state.catalogs.conditions = [];
        }
    }

    get selectedConditions() {
        const ids = this.state.editor.condition_ids || [];
        const byId = Object.fromEntries(
            (this.state.catalogs.conditions || []).map((c) => [c.id, c])
        );
        return ids.map((id) => byId[id] || { id, name: `#${id}`, model: "" });
    }

    _touchConditionIds(ids) {
        this.state.editor.condition_ids = [...ids];
        this.markDirty();
    }

    linkExistingConditions() {
        const model = this.state.editor.compute_model || false;
        const domain = model ? [["model", "=", model]] : [];
        const already = new Set(this.state.editor.condition_ids || []);
        this.dialog.add(SelectCreateDialog, {
            title: _t("Link conditions"),
            resModel: "dashboard.condition",
            domain,
            multiSelect: true,
            noCreate: true,
            onSelected: async (resIds) => {
                const next = [...(this.state.editor.condition_ids || [])];
                for (const id of resIds || []) {
                    if (!already.has(id) && !next.includes(id)) {
                        next.push(id);
                    }
                }
                this._touchConditionIds(next);
                await this.refreshConditionCatalog();
            },
        });
    }

    openNewCondition() {
        const model = this.state.editor.compute_model || false;
        const context = {};
        if (model) {
            context.default_model = model;
        }
        this.dialog.add(FormViewDialog, {
            title: _t("New condition"),
            resModel: "dashboard.condition",
            resId: false,
            context,
            onRecordSaved: async (record) => {
                const id = record.resId;
                if (id && !(this.state.editor.condition_ids || []).includes(id)) {
                    this._touchConditionIds([
                        ...(this.state.editor.condition_ids || []),
                        id,
                    ]);
                }
                await this.refreshConditionCatalog();
            },
        });
    }

    editCondition(conditionId) {
        this.dialog.add(FormViewDialog, {
            title: _t("Edit condition"),
            resModel: "dashboard.condition",
            resId: conditionId,
            onRecordSaved: async () => {
                await this.refreshConditionCatalog();
            },
        });
    }

    removeCondition(conditionId) {
        this._touchConditionIds(
            (this.state.editor.condition_ids || []).filter((id) => id !== conditionId)
        );
    }

    async refreshLinkPathCatalogs() {
        const graphModel = this.state.payload?.graph_model;
        if (!graphModel) {
            this.state.linkPathHopFields = [];
            return;
        }
        const segments = (this.state.editor.graph_data_field || "")
            .split(".")
            .filter(Boolean);
        const hopCount = Math.max(1, segments.length + (this.state.linkPathExtraHop ? 1 : 0));
        const catalogs = [];
        let model = graphModel;
        for (let i = 0; i < hopCount; i++) {
            if (!model) {
                catalogs.push([]);
                continue;
            }
            const fields = await this.orm.call(
                "dashboard.blueprint",
                "studio_model_fields",
                [[this.blueprintId], model, ["many2one"]]
            );
            catalogs.push(fields);
            const seg = segments[i];
            if (seg) {
                const sel = fields.find((f) => f.name === seg);
                model = sel?.relation || false;
            } else {
                model = false;
            }
        }
        this.state.linkPathHopFields = catalogs;
    }

    async searchActions(term) {
        this.state.actionQuery = term;
        const actions = await this.orm.call(
            "dashboard.blueprint",
            "studio_search_actions",
            [[this.blueprintId], term || "", 25]
        );
        this.state.catalogs.actions = actions;
    }

    selectZone(zoneId) {
        if (this.state.dirty) {
            // Soft discard when switching zones keeps UX fluid; Publish still required for live.
            this.state.dirty = false;
        }
        this.state.zone = zoneId;
        this.state.selectedSlotId = null;
        this.state.selectedHeaderId = null;
        this._syncEditorFromSelection();
        if (zoneId === "config") {
            this.state.linkPathExtraHop = false;
            this.refreshLinkPathCatalogs();
        }
    }

    selectSlot(slotId) {
        this.state.selectedSlotId = slotId;
        this._syncEditorFromSelection();
        this.state.dirty = false;
    }

    selectHeader(headerId) {
        this.state.selectedHeaderId = headerId;
        this._syncEditorFromSelection();
        this.state.dirty = false;
    }

    _syncEditorFromSelection() {
        const ed = EMPTY_EDITOR();
        const p = this.state.payload;
        if (!p) {
            this.state.editor = ed;
            return;
        }
        if (this.state.zone === "primary" || this.state.zone === "config") {
            ed.primary_button_label = p.primary_button_label || "";
            ed.primary_action_xmlid = p.primary_action_xmlid || "";
            ed.primary_action_context = p.primary_action_context || "{}";
            ed.contextRows = rowsFromContextRaw(
                this.state.zone === "primary" ? ed.primary_action_context : "{}"
            );
            ed.graph_caption = p.graph_caption || "";
            ed.graph_measure = p.graph_measure || "";
            ed.graph_groupby = p.graph_groupby || "";
            ed.graph_groupby_field_ids = [...(p.graph_groupby_field_ids || [])];
            ed.graph_measure_field_id = p.graph_measure_field_id || false;
            ed.graph_measure_aggregator = p.graph_measure_aggregator || "sum";
            ed.graph_data_field = p.graph_data_field || "";
            ed.graph_domain = p.graph_domain != null ? p.graph_domain : "[]";
            ed.period_field_id = p.period_field_id || false;
            ed.closed_period_field_id = p.closed_period_field_id || false;
            ed.include_child_records = Boolean(p.include_child_records);
            this.state.editor = ed;
            this.state.contextGroupHits = {};
            this.state.contextGroupQuery = {};
            this.state.linkPathExtraHop = false;
            this.refreshLinkPathCatalogs();
            this._hydrateEditorGroupLabels();
            return;
        }
        if (this.state.zone === "header") {
            const item = this.selectedHeader;
            if (item) {
                this.state.selectedHeaderId = item.id;
                ed.kind = item.kind || "subtitle";
                ed.alignment = item.alignment || "left";
                ed.field_names = item.field_names || "";
                ed.icon = item.icon || "";
            }
            ed.header_title_field = p.header_title_field || "";
            ed.header_image_field = p.header_image_field || "";
            ed.header_image_style = p.header_image_style || "avatar";
            this.state.editor = ed;
            return;
        }
        const slot = this.selectedSlot;
        if (slot) {
            this.state.selectedSlotId = slot.id;
            ed.label = slot.label || "";
            ed.label_plural = slot.label_plural || "";
            ed.icon = slot.icon || "";
            ed.style = slot.style || "default";
            ed.show_if_zero = Boolean(slot.show_if_zero);
            ed.action_xmlid = slot.action_xmlid || "";
            ed.action_method = slot.action_method || "";
            ed.action_model = slot.action_model || "";
            ed.amount_field = slot.amount_field || "";
            ed.count_field = slot.count_field || "";
            ed.compute_model = slot.compute_model || "";
            ed.relate_field = slot.relate_field || "";
            ed.compute_domain = slot.compute_domain || "[]";
            ed.value_mode = slot.value_mode || "count";
            ed.module_depends = slot.module_depends || "";
            ed.condition_ids = [...(slot.condition_ids || [])];
            ed.contextRows = rowsFromContextRaw(slot.action_context || "{}");
        }
        this.state.editor = ed;
        this.state.contextGroupHits = {};
        this.state.contextGroupQuery = {};
        this._hydrateEditorGroupLabels();
        this.refreshConditionCatalog();
    }

    onEditorInput(field, ev) {
        const target = ev.target;
        let value = target.type === "checkbox" ? target.checked : target.value;
        if (field === "condition_ids") {
            value = Array.from(target.selectedOptions || []).map((o) => Number(o.value));
        }
        if (field === "period_field_id" || field === "closed_period_field_id") {
            value = value === "" || value == null ? false : Number(value);
        }
        this.state.editor[field] = value;
        this.markDirty();
        if (field === "compute_model") {
            this.refreshConditionCatalog();
        }
    }

    _touchContextRows() {
        this.state.editor.contextRows = [...(this.state.editor.contextRows || [])];
        this.markDirty();
    }

    async _hydrateEditorGroupLabels() {
        const rows = this.state.editor.contextRows || [];
        const xmlids = collectGroupXmlids(rows);
        if (!xmlids.length) {
            return;
        }
        try {
            const labels = await this.orm.call(
                "dashboard.blueprint",
                "studio_group_labels",
                [],
                { xmlids }
            );
            applyGroupLabels(rows, labels || {});
            this.state.editor.contextRows = [...rows];
        } catch {
            /* keep xmlids */
        }
    }

    onContextKeyInput(index, ev) {
        this.state.editor.contextRows[index].key = ev.target.value;
        this._touchContextRows();
    }

    onContextTypeChange(index, ev) {
        const row = this.state.editor.contextRows[index];
        row.valueType = ev.target.value;
        if (row.valueType === "group" && !(row.groupRules && row.groupRules.length)) {
            row.groupRules = [emptyGroupRule()];
        }
        this._touchContextRows();
    }

    onContextFixedInput(index, ev) {
        this.state.editor.contextRows[index].fixedValue = ev.target.value;
        this._touchContextRows();
    }

    onContextAsListChange(index, ev) {
        this.state.editor.contextRows[index].asList = ev.target.checked;
        this._touchContextRows();
    }

    onContextElseValueInput(index, ev) {
        this.state.editor.contextRows[index].elseValue = ev.target.value;
        this._touchContextRows();
    }

    onContextRuleValueInput(rowIndex, ruleIndex, ev) {
        this.state.editor.contextRows[rowIndex].groupRules[ruleIndex].value =
            ev.target.value;
        this._touchContextRows();
    }

    _contextRuleKey(rowIndex, ruleIndex) {
        return `${rowIndex}:${ruleIndex}`;
    }

    getContextGroupHits(rowIndex, ruleIndex) {
        return this.state.contextGroupHits[this._contextRuleKey(rowIndex, ruleIndex)] || [];
    }

    async onContextGroupSearchInput(rowIndex, ruleIndex, ev) {
        const term = ev.target.value;
        const key = this._contextRuleKey(rowIndex, ruleIndex);
        this.state.contextGroupQuery[key] = term;
        this.state.editor.contextRows[rowIndex].groupRules[ruleIndex].groupLabel = term;
        this._touchContextRows();
        if (!term) {
            this.state.contextGroupHits[key] = [];
            return;
        }
        try {
            const hits = await this.orm.call(
                "dashboard.blueprint",
                "studio_search_groups",
                [],
                { term, limit: 12 }
            );
            this.state.contextGroupHits[key] = hits || [];
        } catch {
            this.state.contextGroupHits[key] = [];
        }
    }

    pickContextGroup(rowIndex, ruleIndex, hit) {
        const key = this._contextRuleKey(rowIndex, ruleIndex);
        const rule = this.state.editor.contextRows[rowIndex].groupRules[ruleIndex];
        rule.groupXmlid = hit.xmlid;
        rule.groupLabel = hit.name;
        this.state.contextGroupQuery[key] = hit.name;
        this.state.contextGroupHits[key] = [];
        this._touchContextRows();
    }

    addContextGroupRule(rowIndex) {
        this.state.editor.contextRows[rowIndex].groupRules.push(emptyGroupRule());
        this._touchContextRows();
    }

    removeContextGroupRule(rowIndex, ruleIndex) {
        const rules = this.state.editor.contextRows[rowIndex].groupRules;
        rules.splice(ruleIndex, 1);
        if (!rules.length) {
            rules.push(emptyGroupRule());
        }
        this._touchContextRows();
    }

    addContextRow() {
        this.state.editor.contextRows.push(createEmptyContextRow());
        this._touchContextRows();
    }

    removeContextRow(index) {
        this.state.editor.contextRows.splice(index, 1);
        if (!this.state.editor.contextRows.length) {
            this.state.editor.contextRows.push(createEmptyContextRow());
        }
        this._touchContextRows();
    }

    async onLinkPathHopChange(hopIndex, ev) {
        const name = ev.target.value;
        let segments = (this.state.editor.graph_data_field || "")
            .split(".")
            .filter((s, i, arr) => s || i < arr.length - 1);
        while (segments.length <= hopIndex) {
            segments.push("");
        }
        if (name) {
            segments[hopIndex] = name;
            segments = segments.slice(0, hopIndex + 1);
        } else {
            segments = segments.slice(0, hopIndex);
        }
        this.state.editor.graph_data_field = segments.filter(Boolean).join(".");
        this.state.linkPathExtraHop = false;
        this.markDirty();
        await this.refreshLinkPathCatalogs();
    }

    async addLinkPathHop() {
        if (!this.canAddLinkPathHop) {
            return;
        }
        this.state.linkPathExtraHop = true;
        await this.refreshLinkPathCatalogs();
    }

    async removeLinkPathHop() {
        const segments = (this.state.editor.graph_data_field || "")
            .split(".")
            .filter(Boolean);
        if (!segments.length) {
            return;
        }
        segments.pop();
        this.state.editor.graph_data_field = segments.join(".");
        this.state.linkPathExtraHop = false;
        this.markDirty();
        await this.refreshLinkPathCatalogs();
    }

    onGroupByPick(ev) {
        const raw = ev.target.value;
        ev.target.value = "";
        if (!raw) {
            return;
        }
        const id = Number(raw);
        const ids = this.state.editor.graph_groupby_field_ids || [];
        if (ids.includes(id)) {
            return;
        }
        this.state.editor.graph_groupby_field_ids = [...ids, id];
        this.markDirty();
    }

    removeGroupByField(fieldId) {
        const id = Number(fieldId);
        this.state.editor.graph_groupby_field_ids = (
            this.state.editor.graph_groupby_field_ids || []
        ).filter((i) => i !== id);
        this.markDirty();
    }

    moveGroupByField(fieldId, delta) {
        const ids = [...(this.state.editor.graph_groupby_field_ids || [])];
        const idx = ids.indexOf(Number(fieldId));
        const next = idx + delta;
        if (idx < 0 || next < 0 || next >= ids.length) {
            return;
        }
        [ids[idx], ids[next]] = [ids[next], ids[idx]];
        this.state.editor.graph_groupby_field_ids = ids;
        this.markDirty();
    }

    onMeasureFieldChange(ev) {
        const raw = ev.target.value;
        if (!raw || raw === "__count") {
            this.state.editor.graph_measure_field_id = false;
            this.state.editor.graph_measure_aggregator = false;
        } else {
            this.state.editor.graph_measure_field_id = Number(raw);
            if (!this.state.editor.graph_measure_aggregator) {
                this.state.editor.graph_measure_aggregator = "sum";
            }
        }
        this.markDirty();
    }

    onMeasureAggregatorChange(ev) {
        this.state.editor.graph_measure_aggregator = ev.target.value || "sum";
        this.markDirty();
    }

    onQuickPickHeaderField(ev) {
        const value = ev.target.value;
        ev.target.value = "";
        if (!value || !this.selectedHeader) {
            return;
        }
        this._appendHeaderFieldName(this.selectedHeader.id, value);
    }

    _joinHeaderFieldNames(names) {
        return names.join(", ");
    }

    _appendHeaderFieldName(headerId, fieldName) {
        const header = (this.state.payload?.headers || []).find((h) => h.id === headerId);
        if (!header) {
            return;
        }
        const names = this._parseHeaderFieldNames(header.field_names);
        if (names.includes(fieldName)) {
            return;
        }
        names.push(fieldName);
        this.updateHeaderItem(headerId, "field_names", this._joinHeaderFieldNames(names));
    }

    removeHeaderFieldFromLine(headerId, fieldName) {
        const header = (this.state.payload?.headers || []).find((h) => h.id === headerId);
        if (!header) {
            return;
        }
        const names = this._parseHeaderFieldNames(header.field_names).filter((n) => n !== fieldName);
        this.updateHeaderItem(headerId, "field_names", this._joinHeaderFieldNames(names));
    }

    onHeaderFieldPick(headerId, ev) {
        const value = ev.target.value;
        ev.target.value = "";
        if (!value) {
            return;
        }
        this._appendHeaderFieldName(headerId, value);
    }

    async updateHeaderBlueprint(field, value) {
        let clean = value;
        if (field === "header_image_field" || field === "header_title_field") {
            clean = value || false;
        }
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_write_blueprint",
                [[this.blueprintId], { [field]: clean }]
            );
            await this.applyPayload(payload, false);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Header settings update failed"),
                { type: "danger" }
            );
            await this.loadPayload();
        }
    }

    async updateHeaderItem(headerId, field, value) {
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_write_header_item",
                [[this.blueprintId], headerId, { [field]: value }]
            );
            await this.applyPayload(payload, false);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Header line update failed"),
                { type: "danger" }
            );
            await this.loadPayload();
        }
    }

    selectHeaderRow(headerId) {
        this.state.selectedHeaderId = headerId;
    }

    onActionQueryInput(ev) {
        this.searchActions(ev.target.value);
    }

    pickAction(xmlid) {
        if (this.state.zone === "primary") {
            this.state.editor.primary_action_xmlid = xmlid;
        } else {
            this.state.editor.action_xmlid = xmlid;
        }
        this.markDirty();
    }

    async applyPayload(payload, selectCreated = true) {
        this.state.payload = payload;
        if (selectCreated && payload.created_slot_id) {
            this.state.selectedSlotId = payload.created_slot_id;
        }
        if (selectCreated && payload.created_header_id) {
            this.state.selectedHeaderId = payload.created_header_id;
        }
        if (payload.layout) {
            this.state.layoutDraft = JSON.parse(JSON.stringify(payload.layout));
        }
        this._syncSetupFromPayload(payload);
        this._syncEditorFromSelection();
        this.state.dirty = false;
        await this.loadPreview();
    }

    onSetupMenuNameInput(ev) {
        this.state.setup.menu_name = ev.target.value;
        this.markSetupDirty();
    }

    onSetupMenuSequenceInput(ev) {
        this.state.setup.menu_sequence = parseInt(ev.target.value, 10) || 0;
        this.markSetupDirty();
    }

    dismissSetupBanner() {
        this.state.setupBanner = null;
    }

    clearSetupResults(kind) {
        if (kind) {
            this.state.setupResults[kind] = [];
            return;
        }
        this.state.setupResults = {
            host: [],
            menu: [],
            module: [],
            share: [],
            company: [],
        };
    }

    onSetupSearchFocus(ev) {
        const kind = ev.currentTarget.dataset.kind;
        for (const key of Object.keys(this.state.setupResults)) {
            if (key !== kind) {
                this.state.setupResults[key] = [];
            }
        }
    }

    onSetupSearchBlur(ev) {
        const kind = ev.currentTarget.dataset.kind;
        const picker = ev.currentTarget.closest(".o_ds_setup_picker");
        this._setupBlurTimers = this._setupBlurTimers || {};
        clearTimeout(this._setupBlurTimers[kind]);
        this._setupBlurTimers[kind] = setTimeout(() => {
            const active = document.activeElement;
            if (picker && active && picker.contains(active)) {
                return;
            }
            this.clearSetupResults(kind);
        }, 180);
    }

    async onSetupSearchInput(ev) {
        const kind = ev.currentTarget.dataset.kind;
        const term = ev.target.value;
        this.state.setupQuery[kind] = term;
        const methodMap = {
            host: "studio_search_models",
            menu: "studio_search_menus",
            module: "studio_search_modules",
            share: "studio_search_share_blueprints",
            company: "studio_search_companies",
        };
        const method = methodMap[kind];
        if (!method) {
            return;
        }
        const rows = await this.orm.call("dashboard.blueprint", method, [
            [this.blueprintId],
            term,
            20,
        ]);
        this.state.setupResults[kind] = rows || [];
    }

    pickSetupHost(ev) {
        if (!this.state.payload?.host_editable) {
            return;
        }
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        const name = ev.currentTarget.dataset.name || "";
        this.state.setup.host_model_id = id;
        this.state.setup.host_model_label = name;
        this.state.setupQuery.host = "";
        this.state.setupResults.host = [];
        this.markSetupDirty();
    }

    pickSetupMenu(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        const name = ev.currentTarget.dataset.name || "";
        this.state.setup.menu_parent_id = id;
        this.state.setup.menu_parent_name = name;
        this.state.setupQuery.menu = "";
        this.state.setupResults.menu = [];
        this.markSetupDirty();
    }

    clearSetupMenuParent() {
        this.state.setup.menu_parent_id = false;
        this.state.setup.menu_parent_name = "";
        this.markSetupDirty();
    }

    pickSetupCompany(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        const name = ev.currentTarget.dataset.name || "";
        this.state.setup.company_id = id;
        this.state.setup.company_name = name;
        this.state.setupQuery.company = "";
        this.state.setupResults.company = [];
        this.markSetupDirty();
    }

    clearSetupCompany() {
        this.state.setup.company_id = false;
        this.state.setup.company_name = "";
        this.markSetupDirty();
    }

    pickSetupModule(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        const name = ev.currentTarget.dataset.name || "";
        if (this.state.setup.module_ids.includes(id)) {
            return;
        }
        this.state.setup.module_ids.push(id);
        this.state.setup.module_names.push(name);
        this.state.setupQuery.module = "";
        this.state.setupResults.module = [];
        this.markSetupDirty();
    }

    removeSetupModule(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        const idx = this.state.setup.module_ids.indexOf(id);
        if (idx >= 0) {
            this.state.setup.module_ids.splice(idx, 1);
            this.state.setup.module_names.splice(idx, 1);
            this.markSetupDirty();
        }
    }

    pickSetupShare(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        const name = ev.currentTarget.dataset.name || "";
        if (this.state.setup.share_link_ids.includes(id)) {
            return;
        }
        this.state.setup.share_link_ids.push(id);
        this.state.setup.share_link_names.push(name);
        this.state.setupQuery.share = "";
        this.state.setupResults.share = [];
        this.markSetupDirty();
    }

    removeSetupShare(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        const idx = this.state.setup.share_link_ids.indexOf(id);
        if (idx >= 0) {
            this.state.setup.share_link_ids.splice(idx, 1);
            this.state.setup.share_link_names.splice(idx, 1);
            this.markSetupDirty();
        }
    }

    async saveSetup() {
        if (!this.state.payload || this.state.saving || !this.state.setupDirty) {
            return;
        }
        const setup = this.state.setup;
        const hostChanged =
            setup.host_model_id &&
            setup.host_model_id !== this.state.payload.host_model_id;
        if (hostChanged && this.state.payload.host_editable) {
            const confirmed = await new Promise((resolve) => {
                this.dialog.add(ConfirmationDialog, {
                    title: _t("Change host model?"),
                    body: _t(
                        "Changing the host model may invalidate header fields, host-based KPI/total fields, and share links. Invalid references will be cleared on save."
                    ),
                    confirm: () => resolve(true),
                    cancel: () => resolve(false),
                    confirmLabel: _t("Change host"),
                });
            });
            if (!confirmed) {
                return;
            }
        }
        this.state.saving = true;
        try {
            const vals = {
                menu_name: setup.menu_name || false,
                menu_parent_id: setup.menu_parent_id || false,
                menu_sequence: setup.menu_sequence,
                company_id: setup.company_id || false,
                module_ids: setup.module_ids || [],
                share_link_ids: setup.share_link_ids || [],
            };
            if (this.state.payload.host_editable) {
                vals.host_model_id = setup.host_model_id || false;
            }
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_write_blueprint",
                [[this.blueprintId], vals]
            );
            const cleanup = payload.setup_cleanup_count || 0;
            await this.applyPayload(payload, false);
            await this.loadCatalogs();
            await this.loadSamples("");
            if (cleanup > 0) {
                this.state.setupBanner = { count: cleanup };
            }
            this.notification.add(_t("Setup saved"), { type: "success" });
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Save failed"),
                { type: "danger" }
            );
        } finally {
            this.state.saving = false;
        }
    }

    async saveCurrent() {
        if (this.state.studioMode === "setup") {
            await this.saveSetup();
            return;
        }
        if (!this.state.payload || this.state.saving || !this.state.dirty) {
            return;
        }
        this.state.saving = true;
        try {
            let payload;
            const ed = this.state.editor;
            if (this.state.zone === "primary" || this.state.zone === "config") {
                const vals =
                    this.state.zone === "primary"
                        ? {
                              primary_button_label: ed.primary_button_label,
                              primary_action_xmlid: ed.primary_action_xmlid,
                              primary_action_context: serializeContextRows(
                                  ed.contextRows || []
                              ),
                              graph_caption: ed.graph_caption,
                          }
                        : {
                              graph_caption: ed.graph_caption,
                              graph_groupby_field_ids: ed.graph_groupby_field_ids || [],
                              graph_measure_field_id: ed.graph_measure_field_id || false,
                              graph_measure_aggregator: ed.graph_measure_field_id
                                  ? ed.graph_measure_aggregator || "sum"
                                  : false,
                              graph_data_field: ed.graph_data_field || false,
                              graph_domain: ed.graph_domain || "[]",
                              period_field_id: ed.period_field_id || false,
                              closed_period_field_id: ed.closed_period_field_id || false,
                              include_child_records: Boolean(ed.include_child_records),
                          };
                payload = await this.orm.call(
                    "dashboard.blueprint",
                    "studio_write_blueprint",
                    [[this.blueprintId], vals]
                );
            } else if (this.state.zone === "header" && this.selectedHeader) {
                payload = await this.orm.call(
                    "dashboard.blueprint",
                    "studio_write_header_item",
                    [
                        [this.blueprintId],
                        this.selectedHeader.id,
                        {
                            kind: ed.kind,
                            alignment: ed.alignment,
                            field_names: ed.field_names,
                            icon: ed.icon || false,
                            separator: ed.separator || false,
                        },
                    ]
                );
            } else if (this.selectedSlot) {
                const vals = {
                    label: ed.label,
                    label_plural: ed.label_plural,
                    icon: ed.icon || false,
                    style: ed.style || "default",
                    show_if_zero: ed.show_if_zero,
                    action_xmlid: ed.action_xmlid || false,
                    action_method: ed.action_method || false,
                    action_model: ed.action_model || false,
                    amount_field: ed.amount_field || false,
                    count_field: ed.count_field || false,
                    compute_model: ed.compute_model || false,
                    relate_field: ed.relate_field || false,
                    compute_domain: ed.compute_domain || "[]",
                    value_mode: ed.value_mode || "count",
                    module_depends: ed.module_depends || false,
                    condition_ids: ed.condition_ids || [],
                    action_context: serializeContextRows(ed.contextRows || []),
                    name: ed.label || this.selectedSlot.name,
                };
                payload = await this.orm.call(
                    "dashboard.blueprint",
                    "studio_write_slot",
                    [[this.blueprintId], this.selectedSlot.id, vals]
                );
            }
            if (payload) {
                await this.applyPayload(payload, false);
                this.notification.add(_t("Saved"), { type: "success" });
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error.message || _t("Save failed"), {
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    _defaultSectionForZone() {
        if (this.state.zone === "kpis") {
            return "kpi";
        }
        if (this.state.zone === "totals") {
            return "button_box";
        }
        if (this.state.zone === "shortcuts") {
            return "bottom";
        }
        if (this.state.zone === "manage") {
            return this.state.manageSection || "menu_views";
        }
        return null;
    }

    openDomainEditor() {
        const resModel =
            this.state.editor.compute_model || this.state.payload?.host_model || "res.partner";
        this.dialog.add(DomainSelectorDialog, {
            resModel,
            domain: this.state.editor.compute_domain || "[]",
            title: _t("Filter domain"),
            onConfirm: (domain) => {
                this.state.editor.compute_domain = domain;
                this.markDirty();
            },
        });
    }

    openGraphDomainEditor() {
        const resModel =
            this.state.payload?.graph_model ||
            this.state.payload?.host_model ||
            "res.partner";
        this.dialog.add(DomainSelectorDialog, {
            resModel,
            domain: this.state.editor.graph_domain || "[]",
            title: _t("Custom Filter"),
            onConfirm: (domain) => {
                this.state.editor.graph_domain = domain;
                this.markDirty();
            },
        });
    }

    onDragStart(slotId, ev) {
        this._dragSlotId = slotId;
        if (ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", String(slotId));
        }
    }

    async onDropSlot(targetId, ev) {
        ev.preventDefault();
        const sourceId = this._dragSlotId || Number(ev.dataTransfer?.getData("text/plain"));
        this._dragSlotId = null;
        if (!sourceId || sourceId === targetId) {
            return;
        }
        const section = this.slotsForZone.find((s) => s.id === sourceId)?.section;
        if (!section) {
            return;
        }
        const ids = this.slotsForZone.map((s) => s.id);
        const from = ids.indexOf(sourceId);
        const to = ids.indexOf(targetId);
        if (from < 0 || to < 0) {
            return;
        }
        ids.splice(from, 1);
        ids.splice(to, 0, sourceId);
        const payload = await this.orm.call(
            "dashboard.blueprint",
            "studio_reorder_slots",
            [[this.blueprintId], section, ids]
        );
        await this.applyPayload(payload, false);
    }

    onDragOver(ev) {
        ev.preventDefault();
        if (ev.dataTransfer) {
            ev.dataTransfer.dropEffect = "move";
        }
    }

    _renderPreviewChart() {
        const canvas = this.previewChartRef.el;
        if (!canvas || typeof Chart === "undefined") {
            return;
        }
        const raw = this.state.preview?.graph_json;
        if (!raw) {
            if (this._previewChart) {
                this._previewChart.destroy();
                this._previewChart = null;
            }
            return;
        }
        let data;
        try {
            data = typeof raw === "string" ? JSON.parse(raw) : raw;
        } catch (_e) {
            return;
        }
        const values = data.values || data.data || [];
        const labels = [];
        const nums = [];
        for (const row of values.slice(0, 12)) {
            if (typeof row === "object" && row) {
                labels.push(row.label || row.x || row.name || "");
                nums.push(Number(row.value || row.count || row.y || 0));
            } else {
                labels.push("");
                nums.push(Number(row) || 0);
            }
        }
        if (this._previewChart) {
            this._previewChart.destroy();
        }
        const type = this.state.preview?.graph_type === "line" ? "line" : "bar";
        this._previewChart = new Chart(canvas, {
            type,
            data: {
                labels,
                datasets: [
                    {
                        data: nums,
                        backgroundColor: "rgba(15, 118, 110, 0.65)",
                        borderColor: "#0f766e",
                        borderWidth: 1,
                        tension: 0.3,
                        fill: type === "line",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: { display: false, beginAtZero: true },
                },
            },
        });
    }

    async addItem() {
        this.state.saving = true;
        try {
            if (this.state.zone === "header") {
                const payload = await this.orm.call(
                    "dashboard.blueprint",
                    "studio_create_header_item",
                    [[this.blueprintId], { kind: "subtitle", field_names: "" }]
                );
                await this.applyPayload(payload);
                this.notification.add(_t("Header line added"), { type: "success" });
                return;
            }
            const section = this._defaultSectionForZone();
            if (!section) {
                return;
            }
            const label =
                this.state.zone === "kpis"
                    ? _t("New KPI")
                    : this.state.zone === "totals"
                      ? _t("New total")
                      : this.state.zone === "shortcuts"
                        ? _t("New shortcut")
                        : _t("New menu item");
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_create_slot",
                [[this.blueprintId], section, { label, label_plural: label }]
            );
            await this.applyPayload(payload);
            this.notification.add(_t("Item added"), { type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error.message || _t("Add failed"), {
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    async removeSelected() {
        if (this.state.zone === "header" && this.selectedHeader) {
            if (!confirm(_t("Remove this header line?"))) {
                return;
            }
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_unlink_header_item",
                [[this.blueprintId], this.selectedHeader.id]
            );
            this.state.selectedHeaderId = null;
            await this.applyPayload(payload);
            return;
        }
        if (!this.selectedSlot) {
            return;
        }
        if (!confirm(_t("Remove this item from the card?"))) {
            return;
        }
        const payload = await this.orm.call(
            "dashboard.blueprint",
            "studio_unlink_slot",
            [[this.blueprintId], this.selectedSlot.id]
        );
        this.state.selectedSlotId = null;
        await this.applyPayload(payload);
        this.notification.add(_t("Item removed"), { type: "info" });
    }

    async moveSelected(delta) {
        if (this.state.zone === "header") {
            const ids = (this.state.payload.headers || []).map((h) => h.id);
            const idx = ids.indexOf(this.selectedHeader?.id);
            if (idx < 0) {
                return;
            }
            const next = idx + delta;
            if (next < 0 || next >= ids.length) {
                return;
            }
            [ids[idx], ids[next]] = [ids[next], ids[idx]];
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_reorder_headers",
                [[this.blueprintId], ids]
            );
            await this.applyPayload(payload, false);
            return;
        }
        const section = this.selectedSlot?.section;
        if (!section) {
            return;
        }
        const ids = this.slotsForZone.map((s) => s.id);
        const idx = ids.indexOf(this.selectedSlot.id);
        const next = idx + delta;
        if (idx < 0 || next < 0 || next >= ids.length) {
            return;
        }
        [ids[idx], ids[next]] = [ids[next], ids[idx]];
        const payload = await this.orm.call(
            "dashboard.blueprint",
            "studio_reorder_slots",
            [[this.blueprintId], section, ids]
        );
        await this.applyPayload(payload, false);
    }

    _scopeResModel() {
        return (
            this.state.payload?.graph_model ||
            this.state.payload?.host_model ||
            "res.partner"
        );
    }

    async addScope() {
        this.state.saving = true;
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_create_scope",
                [
                    [this.blueprintId],
                    {
                        name: _t("New scope"),
                        mode: "include",
                        domain: "[]",
                        default_on: false,
                    },
                ]
            );
            await this.applyPayload(payload);
            this.notification.add(_t("Scope added"), { type: "success" });
        } catch (error) {
            this.notification.add(error?.data?.message || error.message || _t("Add scope failed"), {
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    async updateScope(scopeId, field, value) {
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_write_scope",
                [[this.blueprintId], scopeId, { [field]: value }]
            );
            await this.applyPayload(payload, false);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Scope update failed"),
                { type: "danger" }
            );
            await this.loadPayload();
        }
    }

    onScopeFieldBlur(scopeId, field, ev) {
        let value = ev.target.value;
        const scope = (this.state.payload.scopes || []).find((s) => s.id === scopeId);
        if (!scope) {
            return;
        }
        if (field === "name") {
            value = (value || "").trim();
            if (!value) {
                ev.target.value = scope.name || "";
                return;
            }
            if (scope.name === value) {
                return;
            }
            this.updateScope(scopeId, field, value);
            return;
        }
        if (field === "description") {
            const next = value || false;
            if ((scope.description || "") === (value || "")) {
                return;
            }
            this.updateScope(scopeId, field, next);
            return;
        }
        if (field === "domain") {
            value = (value || "").trim() || "[]";
            if ((scope.domain || "[]") === value) {
                return;
            }
            this.updateScope(scopeId, field, value);
        }
    }

    openScopeDomainEditor(scopeId) {
        const scope = (this.state.payload.scopes || []).find((s) => s.id === scopeId);
        if (!scope) {
            return;
        }
        this.dialog.add(DomainSelectorDialog, {
            resModel: this._scopeResModel(),
            domain: scope.domain || "[]",
            title: _t("Scope filter"),
            onConfirm: (domain) => {
                this.updateScope(scopeId, "domain", domain);
            },
        });
    }

    async removeScope(scopeId) {
        if (!confirm(_t("Remove this scope from the dashboard?"))) {
            return;
        }
        this.state.saving = true;
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_unlink_scope",
                [[this.blueprintId], scopeId]
            );
            await this.applyPayload(payload, false);
            this.notification.add(_t("Scope removed"), { type: "info" });
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Remove scope failed"),
                { type: "danger" }
            );
        } finally {
            this.state.saving = false;
        }
    }

    async reorderScopes(orderedIds) {
        const payload = await this.orm.call(
            "dashboard.blueprint",
            "studio_reorder_scopes",
            [[this.blueprintId], orderedIds]
        );
        await this.applyPayload(payload, false);
    }

    async removeHeaderLine(headerId) {
        if (!confirm(_t("Remove this header line?"))) {
            return;
        }
        this.state.saving = true;
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_unlink_header_item",
                [[this.blueprintId], headerId]
            );
            if (this.state.selectedHeaderId === headerId) {
                this.state.selectedHeaderId = null;
            }
            await this.applyPayload(payload, false);
            this.notification.add(_t("Header line removed"), { type: "info" });
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Remove header line failed"),
                { type: "danger" }
            );
        } finally {
            this.state.saving = false;
        }
    }

    onDragStartHeader(headerId, ev) {
        this._dragHeaderId = headerId;
        if (ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", String(headerId));
        }
    }

    async onDropHeader(targetId, ev) {
        ev.preventDefault();
        const sourceId = this._dragHeaderId || Number(ev.dataTransfer?.getData("text/plain"));
        this._dragHeaderId = null;
        if (!sourceId || sourceId === targetId) {
            return;
        }
        const ids = (this.state.payload.headers || []).map((h) => h.id);
        const from = ids.indexOf(sourceId);
        const to = ids.indexOf(targetId);
        if (from < 0 || to < 0) {
            return;
        }
        ids.splice(from, 1);
        ids.splice(to, 0, sourceId);
        const payload = await this.orm.call(
            "dashboard.blueprint",
            "studio_reorder_headers",
            [[this.blueprintId], ids]
        );
        await this.applyPayload(payload, false);
    }

    async moveHeaderLine(headerId, delta) {
        const ids = (this.state.payload.headers || []).map((h) => h.id);
        const idx = ids.indexOf(headerId);
        const next = idx + delta;
        if (idx < 0 || next < 0 || next >= ids.length) {
            return;
        }
        [ids[idx], ids[next]] = [ids[next], ids[idx]];
        const payload = await this.orm.call(
            "dashboard.blueprint",
            "studio_reorder_headers",
            [[this.blueprintId], ids]
        );
        await this.applyPayload(payload, false);
    }

    onDragStartScope(scopeId, ev) {
        this._dragScopeId = scopeId;
        if (ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", String(scopeId));
        }
    }

    async onDropScope(targetId, ev) {
        ev.preventDefault();
        const sourceId = this._dragScopeId || Number(ev.dataTransfer?.getData("text/plain"));
        this._dragScopeId = null;
        if (!sourceId || sourceId === targetId) {
            return;
        }
        const ids = (this.state.payload.scopes || []).map((s) => s.id);
        const from = ids.indexOf(sourceId);
        const to = ids.indexOf(targetId);
        if (from < 0 || to < 0) {
            return;
        }
        ids.splice(from, 1);
        ids.splice(to, 0, sourceId);
        try {
            await this.reorderScopes(ids);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Reorder failed"),
                { type: "danger" }
            );
        }
    }

    async moveScope(scopeId, delta) {
        const ids = (this.state.payload.scopes || []).map((s) => s.id);
        const idx = ids.indexOf(scopeId);
        const next = idx + delta;
        if (idx < 0 || next < 0 || next >= ids.length) {
            return;
        }
        [ids[idx], ids[next]] = [ids[next], ids[idx]];
        try {
            await this.reorderScopes(ids);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Reorder failed"),
                { type: "danger" }
            );
        }
    }

    async publish() {
        await this.orm.call("dashboard.blueprint", "action_publish", [[this.blueprintId]]);
        await this.loadPayload();
        this.notification.add(_t("Published — live card updated"), { type: "success" });
    }

    async unpublish() {
        await this.orm.call("dashboard.blueprint", "action_unpublish", [[this.blueprintId]]);
        await this.loadPayload();
        this.notification.add(_t("Unpublished"), { type: "warning" });
    }

    async discard() {
        await this.loadPayload();
        await this.loadCatalogs();
        this.notification.add(_t("Changes discarded"), { type: "info" });
    }

    async openAdvanced() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Advanced blueprint"),
            res_model: "dashboard.blueprint",
            res_id: this.blueprintId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    sectionBadge(section) {
        return (
            {
                menu_views: "Views",
                menu_new: "New",
                menu_reports: "Reports",
            }[section] || section
        );
    }

    formatItemCount(item) {
        if (!item) {
            return "—";
        }
        if (item.count != null) {
            return item.count;
        }
        if (item.amount != null) {
            return item.amount;
        }
        return "—";
    }
}

registry.category("actions").add("dashboard_engine.studio", DashboardStudioAction);
