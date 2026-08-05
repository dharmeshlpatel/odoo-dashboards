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
    {
        id: "menu_views",
        label: "Views",
        help: _t("Browse / list screens in the card ⋮ menu."),
    },
    {
        id: "menu_new",
        label: "New",
        help: _t("Create / form actions in the card ⋮ menu."),
    },
    {
        id: "menu_reports",
        label: "Reports",
        help: _t("Report actions in the card ⋮ menu."),
    },
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
    {
        id: "header",
        label: "Header",
        icon: "fa-header",
        section: null,
        subtitle: "Title, image, and subtitle lines shown on the card",
    },
    {
        id: "primary",
        label: "Primary Button",
        icon: "fa-external-link-square",
        section: null,
        subtitle: "Left button label, action, and defaults (chart models live in Configuration)",
    },
    {
        id: "kpis",
        label: "KPIs",
        icon: "fa-tachometer",
        section: "kpi",
        subtitle: "Count badges shown in the KPI strip",
    },
    {
        id: "totals",
        label: "Totals",
        icon: "fa-calculator",
        section: "button_box",
        subtitle: "Currency/amount boxes shown below the chart",
    },
    {
        id: "shortcuts",
        label: "Shortcuts",
        icon: "fa-external-link",
        section: "bottom",
        subtitle: "Quick-action chips on the card",
    },
    {
        id: "manage",
        label: "Manage Menu",
        icon: "fa-bars",
        section: "menu",
        subtitle: "Actions in the ⋮ menu on the live card",
    },
    {
        id: "config",
        label: "Configuration",
        icon: "fa-cog",
        section: null,
        subtitle: "My Data, Graph Configuration (Chart Model Options, Group By, Measures, Data to Include), and Filters",
    },
];

const EMPTY_EDITOR = () => ({
    label: "",
    label_plural: "",
    icon: "",
    section: "",
    style: "default",
    style_mode: "static",
    show_if_zero: true,
    action_xmlid: "",
    action_method: "",
    action_model: "",
    amount_field: "",
    count_field: "",
    compute_model: "",
    compute_model_label: "",
    relate_field: "",
    compute_domain: "[]",
    value_mode: "count",
    amount_measure_field: "",
    amount_aggregator_type: "sum",
    module_depends: "",
    module_ids: [],
    module_names: [],
    condition_ids: [],
    kind: "subtitle",
    alignment: "left",
    field_names: "",
    primary_button_label: "",
    primary_action_xmlid: "",
    primary_action_context: "{}",
    contextRows: [],
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

/** Mirror dashboard.blueprint.slot._resolved_style(count, amount). */
function resolvedSlotStyle(style, styleMode, count, amount) {
    const base = style || "default";
    if ((styleMode || "static") !== "when_positive") {
        return base;
    }
    const positive = !!(count || amount);
    return positive ? base : "default";
}

const EMPTY_SETUP = () => ({
    host_model_id: false,
    host_model_label: "",
    menu_name: "",
    menu_parent_id: false,
    menu_parent_name: "",
    menu_sequence: 50,
    menu_group_ids: [],
    menu_group_names: [],
    group_id: false,
    group_name: "",
    menu_web_icon: "",
    menu_web_icon_data: false,
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
                visibility: "",
                hub_group: "",
            },
            setupResults: {
                host: [],
                menu: [],
                module: [],
                share: [],
                company: [],
                visibility: [],
                hub_group: [],
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
                slotMeasureFields: [],
                conditions: [],
                icons: [],
                actions: [],
                samples: [],
            },
            actionQuery: "",
            actionsShowAll: false,
            actionScopeLabel: "",
            actionScoped: true,
            variantPickerQuery: {},
            variantPickerResults: {},
            variantPickerScopeLabel: {},
            variantPickerShowAll: {},
            variantModelScopeLabel: {},
            variantModelShowAll: {},
            variantLinkPathHopFields: {},
            variantLinkPathExtraHop: {},
            sampleQuery: "",
            sampleId: null,
            preview: null,
            previewLoading: false,
            dirty: false,
            dirtyToken: 0,
            layoutDirty: false,
            loading: true,
            saving: false,
            linkPathHopFields: [],
            linkPathExtraHop: false,
            slotModelQuery: "",
            slotModelResults: [],
            slotModelShowAll: false,
            slotModelScopeLabel: "",
            slotModuleQuery: "",
            slotModuleResults: [],
            slotRelatePathHopFields: [],
            slotRelatePathExtraHop: false,
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

    get zoneSubtitle() {
        return this.zoneMeta.subtitle || _t("Full configuration for this block.");
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

    /** Manage menu only — items for one of Views / New / Reports. */
    slotsForManageSection(sectionId) {
        return this.slotsForZone.filter((s) => s.section === sectionId);
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
            const styleMode = ed.style_mode || item.style_mode || "static";
            return {
                ...item,
                label,
                label_plural: (ed.label_plural || "").trim() || item.label_plural,
                name: label,
                icon: ed.icon || item.icon,
                style: resolvedSlotStyle(
                    ed.style || item.style,
                    styleMode,
                    item.count,
                    item.amount
                ),
                style_mode: styleMode,
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
                label_plural: s.label_plural,
                name: s.name || s.label,
                icon: s.icon,
                count: null,
                style: s.style,
            }));
    }

    /**
     * Keep the card map aligned with the right-hand editor list.
     * Live preview may hide zero-value slots; merge fills those gaps.
     * Only this dashboard's configured slots are shown (not share-pool peers).
     */
    _mergeMapSlots(liveItems, section) {
        const configured = this._slotsFromPayload(section);
        const live = Array.isArray(liveItems) ? liveItems : [];
        if (!configured.length) {
            return configured;
        }
        if (!this.state.preview?.ok) {
            return configured;
        }
        const byKey = new Map();
        for (const item of live) {
            byKey.set(item.key ?? item.id, item);
        }
        return configured.map((cfg) => {
            const key = cfg.key ?? cfg.id;
            return byKey.has(key) ? byKey.get(key) : cfg;
        });
    }

    get kpisPreview() {
        const live = this.state.preview?.ok ? this.state.preview.slots?.kpis : null;
        return this._overlaySelectedSlot(this._mergeMapSlots(live, "kpi").slice(0, 8));
    }

    get totalsPreview() {
        const live = this.state.preview?.ok
            ? this.state.preview.slots?.button_box
            : null;
        return this._overlaySelectedSlot(
            this._mergeMapSlots(live, "button_box").slice(0, 6)
        );
    }

    get shortcutsPreview() {
        const live = this.state.preview?.ok ? this.state.preview.slots?.buttons : null;
        return this._overlaySelectedSlot(
            this._mergeMapSlots(live, "bottom").slice(0, 6)
        );
    }

    get manageViewsPreview() {
        const live = this.state.preview?.ok
            ? this.state.preview.slots?.menu?.views
            : null;
        return this._overlaySelectedSlot(
            this._mergeMapSlots(live, "menu_views").slice(0, 4)
        );
    }

    get manageNewPreview() {
        const live = this.state.preview?.ok
            ? this.state.preview.slots?.menu?.new
            : null;
        return this._overlaySelectedSlot(
            this._mergeMapSlots(live, "menu_new").slice(0, 4)
        );
    }

    get manageReportsPreview() {
        const live = this.state.preview?.ok
            ? this.state.preview.slots?.menu?.reports
            : null;
        return this._overlaySelectedSlot(
            this._mergeMapSlots(live, "menu_reports").slice(0, 4)
        );
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
        // Touch dirtyToken so OWL re-renders the toolbar Save button.
        void this.state.dirtyToken;
        if (this.state.studioMode === "setup") {
            return this.state.setupDirty;
        }
        if (this.state.studioMode === "layout") {
            return this.state.layoutDirty;
        }
        // Shared-slot writes are blocked in saveCurrent (toast), not here —
        // otherwise Configuration / Primary edits never enable Save when a
        // shared KPI happens to be selected in another zone.
        return Boolean(this.state.dirty);
    }

    get canDiscard() {
        void this.state.dirtyToken;
        return Boolean(
            this.state.dirty || this.state.layoutDirty || this.state.setupDirty
        );
    }

    get hasGraphVariants() {
        return Boolean((this.state.payload?.graph_variants || []).length);
    }

    get defaultGraphVariant() {
        const rows = this.state.payload?.graph_variants || [];
        return rows.find((v) => v.is_default) || rows[0] || null;
    }

    get restrictScopes() {
        return (this.state.payload?.scopes || []).filter((s) => s.mode === "restrict");
    }

    get includeScopes() {
        return (this.state.payload?.scopes || []).filter((s) => s.mode === "include");
    }

    _scopesByMode(mode) {
        return (this.state.payload?.scopes || []).filter((s) => s.mode === mode);
    }

    /**
     * Rebuild full scope id order after reordering only one mode's visible rows.
     * Other-mode scopes keep their relative slots in the global list.
     */
    _mergeScopeModeOrder(mode, orderedModeIds) {
        const all = this.state.payload?.scopes || [];
        let i = 0;
        return all.map((s) => {
            if (s.mode === mode) {
                return orderedModeIds[i++];
            }
            return s.id;
        });
    }

    _scopeModeOf(scopeId) {
        const scope = (this.state.payload?.scopes || []).find((s) => s.id === scopeId);
        return scope?.mode || null;
    }

    openConfigZone() {
        this.selectZone("config");
    }

    get selectedSlotOwned() {
        const slot = this.selectedSlot;
        if (!slot) {
            return true;
        }
        return slot.owned !== false;
    }

    get selectedActionLabel() {
        const xmlid = this.state.editor?.action_xmlid || "";
        if (!xmlid) {
            return "";
        }
        const hit = (this.state.catalogs?.actions || []).find((a) => a.xmlid === xmlid);
        return hit?.name || xmlid;
    }

    slotOwned(slot) {
        return Boolean(slot) && slot.owned !== false;
    }

    /** Open Studio for a shared item's source blueprint. */
    async openSourceStudio(blueprintId) {
        const id = Number(blueprintId);
        if (!id || id === this.blueprintId) {
            return;
        }
        if (!this._confirmDiscardIfDirty()) {
            return;
        }
        try {
            const action = await this.orm.call(
                "dashboard.blueprint",
                "action_open_studio",
                [[id]]
            );
            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Could not open source Studio"),
                { type: "danger" }
            );
        }
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

    get menuVisibilityChips() {
        const ids = this.state.setup.menu_group_ids || [];
        const names = this.state.setup.menu_group_names || [];
        return ids.map((id, i) => ({ id, name: names[i] || `#${id}` }));
    }

    get menuFullPathPreview() {
        const leaf =
            this.state.setup.menu_name ||
            this.state.payload?.menu_name ||
            this.state.payload?.name ||
            "";
        const parent =
            this.state.setup.menu_parent_name ||
            this.state.payload?.menu_parent_name ||
            "";
        if (parent && leaf) {
            return `${parent}/${leaf}`;
        }
        return this.state.payload?.menu_full_path || leaf || "";
    }

    get menuActionLabelPreview() {
        return this.state.payload?.menu_action_label || "";
    }

    markDirty() {
        this.state.dirty = true;
        // Force a state tick so toolbar Save (t-att-disabled) re-evaluates.
        this.state.dirtyToken = (this.state.dirtyToken || 0) + 1;
    }

    _confirmDiscardIfDirty() {
        if (!this.state.dirty) {
            return true;
        }
        if (
            confirm(
                _t("You have unsaved changes. Discard them and continue?")
            )
        ) {
            this.state.dirty = false;
            this.state.dirtyToken = (this.state.dirtyToken || 0) + 1;
            return true;
        }
        return false;
    }

    markSetupDirty() {
        this.state.setupDirty = true;
        this.state.dirtyToken = (this.state.dirtyToken || 0) + 1;
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
            menu_group_ids: [...(payload.menu_group_ids || [])],
            menu_group_names: [...(payload.menu_group_names || [])],
            group_id: payload.group_id || false,
            group_name: payload.group_name || "",
            menu_web_icon: payload.menu_web_icon || "",
            menu_web_icon_data: payload.menu_web_icon_data || false,
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
            visibility: [],
            hub_group: [],
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
        this.state.dirtyToken = (this.state.dirtyToken || 0) + 1;
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
        const res = await this.orm.call(
            "dashboard.blueprint",
            "studio_search_actions",
            [[this.blueprintId], term || "", 25, this.state.actionsShowAll || false]
        );
        this.state.catalogs.actions = res.actions || [];
        this.state.actionScopeLabel = res.scope_label || "";
        this.state.actionScoped = Boolean(res.scoped);
    }

    toggleActionsShowAll() {
        this.state.actionsShowAll = !this.state.actionsShowAll;
        this.searchActions(this.state.actionQuery || "");
    }

    selectZone(zoneId) {
        if (zoneId === this.state.zone) {
            // Re-clicking the same card-map zone must not wipe unsaved edits.
            return;
        }
        if (!this._confirmDiscardIfDirty()) {
            return;
        }
        this.state.zone = zoneId;
        this.state.selectedSlotId = null;
        this.state.selectedHeaderId = null;
        this._syncEditorFromSelection();
        if (zoneId === "config") {
            this.state.linkPathExtraHop = false;
            this.refreshLinkPathCatalogs();
            this.refreshAllVariantLinkPathCatalogs();
        }
    }

    selectSlot(slotId) {
        if (slotId === this.state.selectedSlotId) {
            return;
        }
        if (!this._confirmDiscardIfDirty()) {
            return;
        }
        this.state.selectedSlotId = slotId;
        this._syncEditorFromSelection();
    }

    selectHeader(headerId) {
        if (headerId === this.state.selectedHeaderId) {
            return;
        }
        if (!this._confirmDiscardIfDirty()) {
            return;
        }
        this.state.selectedHeaderId = headerId;
        this._syncEditorFromSelection();
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
            ed.section = slot.section || "";
            ed.style = slot.style || "default";
            ed.style_mode = slot.style_mode || "static";
            ed.show_if_zero = Boolean(slot.show_if_zero);
            ed.action_xmlid = slot.action_xmlid || "";
            ed.action_method = slot.action_method || "";
            ed.action_model = slot.action_model || "";
            ed.amount_field = slot.amount_field || "";
            ed.count_field = slot.count_field || "";
            ed.compute_model = slot.compute_model || "";
            ed.compute_model_label = slot.compute_model_label || "";
            ed.relate_field = slot.relate_field || "";
            ed.compute_domain = slot.compute_domain || "[]";
            ed.value_mode = slot.value_mode || "count";
            const [amtField, amtAgg] = (slot.amount_aggregator || "").split(":");
            ed.amount_measure_field = amtField || "";
            ed.amount_aggregator_type = amtAgg || "sum";
            ed.module_depends = slot.module_depends || "";
            ed.module_ids = [...(slot.module_ids || [])];
            ed.module_names = [...(slot.module_names || [])];
            ed.condition_ids = [...(slot.condition_ids || [])];
            ed.contextRows = rowsFromContextRaw(slot.action_context || "{}");
        }
        this.state.editor = ed;
        this.state.contextGroupHits = {};
        this.state.contextGroupQuery = {};
        this.state.slotModelQuery = "";
        this.state.slotModelResults = [];
        this.state.slotModuleQuery = "";
        this.state.slotModuleResults = [];
        this.state.slotRelatePathExtraHop = false;
        this._hydrateEditorGroupLabels();
        this.refreshConditionCatalog();
        this.refreshSlotRelatePathCatalogs();
        this.refreshSlotMeasureFields();
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
            this.refreshSlotRelatePathCatalogs();
            this.refreshSlotMeasureFields();
        }
        if (field === "value_mode") {
            this._onSlotValueModeChange(value);
        }
    }

    get slotShowsCount() {
        return ["count", "count_amount"].includes(
            this.state.editor.value_mode || "count"
        );
    }

    get slotShowsAmount() {
        return ["amount", "count_amount"].includes(
            this.state.editor.value_mode || "count"
        );
    }

    /** Numbered steps in the slot editor (Appearance → … → Availability). */
    get slotEditorHasFigureStep() {
        return ["kpis", "shortcuts", "totals"].includes(this.state.zone);
    }

    get slotEditorActionStep() {
        return this.slotEditorHasFigureStep ? "3" : "2";
    }

    get slotEditorAvailabilityStep() {
        return this.slotEditorHasFigureStep ? "4" : "3";
    }

    get slotAppearanceHelp() {
        const zone = this.state.zone;
        if (zone === "totals") {
            return _t("How this total box looks on the card.");
        }
        if (zone === "shortcuts") {
            return _t("How this shortcut chip looks on the card.");
        }
        if (zone === "manage") {
            return _t("How this manage-menu entry is labeled.");
        }
        return _t("How this KPI looks on the card.");
    }

    get slotFigureHelp() {
        if (this.state.zone === "shortcuts") {
            return _t(
                "Optional count/amount for this shortcut, which records feed it, and filters."
            );
        }
        return _t(
            "What number is shown, which records feed it, and how they are filtered."
        );
    }

    get slotHostFieldsHelp() {
        return _t(
            "Totals read fields from this card’s record (not a related model)."
        );
    }

    get slotItemsSectionTitle() {
        const zone = this.state.zone;
        if (zone === "totals") {
            return _t("Totals in this Block");
        }
        if (zone === "shortcuts") {
            return _t("Shortcuts in this Block");
        }
        if (zone === "manage") {
            return _t("Menu Items");
        }
        return _t("KPIs in this Block");
    }

    get slotItemsSectionHelp() {
        const zone = this.state.zone;
        if (zone === "manage") {
            return _t(
                "Items in Views / New / Reports. Pick a section above before Add."
            );
        }
        if (zone === "totals") {
            return _t("Amount/count boxes under the chart. Select one to edit below.");
        }
        if (zone === "shortcuts") {
            return _t("Quick-action chips on the card. Select one to edit below.");
        }
        return _t("KPI badges on the card. Select one to edit below.");
    }

    get slotClickActionHelp() {
        const zone = this.state.zone;
        if (zone === "manage") {
            return _t("What opens when the user picks this menu entry.");
        }
        if (zone === "shortcuts") {
            return _t("What opens when the user clicks this shortcut.");
        }
        if (zone === "totals") {
            return _t("What opens when the user clicks this total box.");
        }
        return _t("What opens when the user clicks this KPI.");
    }

    get slotValueModeHelp() {
        const mode = this.state.editor.value_mode || "count";
        if (mode === "amount") {
            return _t(
                "Shows a total from the amount field. Set the source records and the amount below."
            );
        }
        if (mode === "count_amount") {
            return _t(
                "Shows how many records match, plus a total from the amount field."
            );
        }
        return _t(
            "Shows how many source records match the filters. No amount field is used."
        );
    }

    _onSlotValueModeChange(mode) {
        if (mode === "count") {
            this.state.editor.amount_measure_field = "";
            this.state.editor.amount_aggregator_type = "sum";
        }
    }

    _slotAmountAggregatorValue() {
        const field = (this.state.editor.amount_measure_field || "").trim();
        if (!field || !this.slotShowsAmount) {
            return false;
        }
        const agg = this.state.editor.amount_aggregator_type || "sum";
        return `${field}:${agg}`;
    }

    async refreshSlotMeasureFields() {
        const model = this.state.editor?.compute_model;
        if (!model) {
            this.state.catalogs.slotMeasureFields = [];
            return;
        }
        try {
            this.state.catalogs.slotMeasureFields = await this.orm.call(
                "dashboard.blueprint",
                "studio_model_fields",
                [[this.blueprintId], model, ["integer", "float", "monetary"]]
            );
        } catch {
            this.state.catalogs.slotMeasureFields = [];
        }
    }

    get slotModuleChips() {
        const ids = this.state.editor.module_ids || [];
        const names = this.state.editor.module_names || [];
        return ids.map((id, i) => ({ id, name: names[i] || `#${id}` }));
    }

    get slotRelatePathRows() {
        const segments = (this.state.editor.relate_field || "")
            .split(".")
            .filter(Boolean);
        const count = Math.max(
            1,
            segments.length + (this.state.slotRelatePathExtraHop ? 1 : 0)
        );
        const rows = [];
        for (let i = 0; i < count; i++) {
            rows.push({
                index: i,
                value: segments[i] || "",
                options: this.state.slotRelatePathHopFields[i] || [],
                showSep: i < count - 1,
            });
        }
        return rows;
    }

    get canAddSlotRelatePathHop() {
        if (this.state.slotRelatePathExtraHop) {
            return false;
        }
        const segments = (this.state.editor.relate_field || "")
            .split(".")
            .filter(Boolean);
        if (!segments.length) {
            return false;
        }
        const lastIdx = segments.length - 1;
        const opts = this.state.slotRelatePathHopFields[lastIdx] || [];
        const sel = opts.find((f) => f.name === segments[lastIdx]);
        return Boolean(sel?.relation);
    }

    get canRemoveSlotRelatePathHop() {
        return Boolean(
            (this.state.editor.relate_field || "").split(".").filter(Boolean).length
        );
    }

    async onSlotComputeModelSearch(ev) {
        const term = ev?.target?.value ?? this.state.slotModelQuery;
        this.state.slotModelQuery = term;
        const res = await this.orm.call(
            "dashboard.blueprint",
            "studio_search_chart_models",
            [
                [this.blueprintId],
                term || "",
                20,
                Boolean(this.state.slotModelShowAll),
            ]
        );
        this.state.slotModelResults = res.models || [];
        this.state.slotModelScopeLabel = res.scope_label || "";
    }

    toggleSlotModelsShowAll() {
        this.state.slotModelShowAll = !this.state.slotModelShowAll;
        this.onSlotComputeModelSearch();
    }

    pickSlotComputeModel(row) {
        const model = (row?.model || "").trim();
        if (!model) {
            return;
        }
        this.state.editor.compute_model = model;
        this.state.editor.compute_model_label = row.name || model;
        this.state.slotModelQuery = "";
        this.state.slotModelResults = [];
        this.state.editor.relate_field = "";
        this.state.editor.amount_measure_field = "";
        this.state.slotRelatePathExtraHop = false;
        this.markDirty();
        this.refreshConditionCatalog();
        this.refreshSlotRelatePathCatalogs();
        this.refreshSlotMeasureFields();
    }

    clearSlotComputeModel() {
        this.state.editor.compute_model = "";
        this.state.editor.compute_model_label = "";
        this.state.editor.relate_field = "";
        this.state.editor.amount_measure_field = "";
        this.state.slotRelatePathExtraHop = false;
        this.state.slotRelatePathHopFields = [];
        this.state.catalogs.slotMeasureFields = [];
        this.markDirty();
        this.refreshConditionCatalog();
    }

    async onSlotModuleSearch(ev) {
        const term = ev?.target?.value ?? this.state.slotModuleQuery;
        this.state.slotModuleQuery = term;
        const rows = await this.orm.call(
            "dashboard.blueprint",
            "studio_search_modules",
            [[this.blueprintId], term || "", 20]
        );
        this.state.slotModuleResults = rows || [];
    }

    onSlotModuleSearchBlur() {
        clearTimeout(this._slotModuleBlurTimer);
        this._slotModuleBlurTimer = setTimeout(() => {
            this.state.slotModuleResults = [];
        }, 180);
    }

    pickSlotModule(row) {
        const id = Number(row?.id);
        if (!id || (this.state.editor.module_ids || []).includes(id)) {
            this.state.slotModuleQuery = "";
            this.state.slotModuleResults = [];
            return;
        }
        this.state.editor.module_ids = [...(this.state.editor.module_ids || []), id];
        this.state.editor.module_names = [
            ...(this.state.editor.module_names || []),
            row.name || row.technical || `#${id}`,
        ];
        this.state.slotModuleQuery = "";
        this.state.slotModuleResults = [];
        this.markDirty();
    }

    removeSlotModule(moduleId) {
        const id = Number(moduleId);
        const idx = (this.state.editor.module_ids || []).indexOf(id);
        if (idx < 0) {
            return;
        }
        this.state.editor.module_ids = this.state.editor.module_ids.filter(
            (x) => x !== id
        );
        this.state.editor.module_names = this.state.editor.module_names.filter(
            (_n, i) => i !== idx
        );
        this.markDirty();
    }

    async refreshSlotRelatePathCatalogs() {
        const computeModel = this.state.editor?.compute_model;
        if (!computeModel) {
            this.state.slotRelatePathHopFields = [];
            return;
        }
        const segments = (this.state.editor.relate_field || "")
            .split(".")
            .filter(Boolean);
        const hopCount = Math.max(
            1,
            segments.length + (this.state.slotRelatePathExtraHop ? 1 : 0)
        );
        const catalogs = [];
        let model = computeModel;
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
        this.state.slotRelatePathHopFields = catalogs;
    }

    async onSlotRelatePathHopChange(hopIndex, ev) {
        const name = ev.target.value;
        let segments = (this.state.editor.relate_field || "")
            .split(".")
            .filter(Boolean);
        while (segments.length <= hopIndex) {
            segments.push("");
        }
        if (name) {
            segments[hopIndex] = name;
            segments = segments.slice(0, hopIndex + 1);
        } else {
            segments = segments.slice(0, hopIndex);
        }
        this.state.editor.relate_field = segments.filter(Boolean).join(".");
        this.state.slotRelatePathExtraHop = false;
        this.markDirty();
        await this.refreshSlotRelatePathCatalogs();
    }

    async addSlotRelatePathHop() {
        if (!this.canAddSlotRelatePathHop) {
            return;
        }
        this.state.slotRelatePathExtraHop = true;
        await this.refreshSlotRelatePathCatalogs();
    }

    async removeSlotRelatePathHop() {
        const segments = (this.state.editor.relate_field || "")
            .split(".")
            .filter(Boolean);
        if (!segments.length) {
            return;
        }
        segments.pop();
        this.state.editor.relate_field = segments.join(".");
        this.state.slotRelatePathExtraHop = false;
        this.markDirty();
        await this.refreshSlotRelatePathCatalogs();
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
        this._touchContextRows();
    }

    async updateConfigBlueprint(field, value) {
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_write_blueprint",
                [[this.blueprintId], { [field]: value || false }]
            );
            await this.applyStudioMutation(payload);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Config update failed"),
                { type: "danger" }
            );
            await this.loadPayload();
        }
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
            await this.applyStudioMutation(payload);
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
            await this.applyStudioMutation(payload);
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

    async applyPayload(payload, selectCreated = true, options = {}) {
        // Immediate RPC helpers (scopes, variants, header rows) also land here.
        // If the admin already has Content edits pending, do not wipe the editor
        // or clear dirty — that left Save/Discard permanently disabled.
        const resetEditor =
            options.resetEditor !== undefined
                ? Boolean(options.resetEditor)
                : !this.state.dirty;
        this.state.payload = payload;
        if (selectCreated && payload.created_slot_id) {
            this.state.selectedSlotId = payload.created_slot_id;
        }
        if (selectCreated && payload.created_header_id) {
            this.state.selectedHeaderId = payload.created_header_id;
        }
        if (selectCreated && payload.created_graph_variant_id) {
            // no selection UI yet; payload refresh is enough
        }
        if (payload.layout && (!this.state.layoutDirty || options.resetEditor)) {
            this.state.layoutDraft = JSON.parse(JSON.stringify(payload.layout));
        }
        if (!this.state.setupDirty || options.resetEditor) {
            this._syncSetupFromPayload(payload);
        }
        if (resetEditor) {
            this._syncEditorFromSelection();
            this.state.dirty = false;
        }
        this.state.dirtyToken = (this.state.dirtyToken || 0) + 1;
        if (this.state.zone === "config") {
            await this.refreshAllVariantLinkPathCatalogs();
        }
        await this.loadPreview();
    }

    /**
     * Payload from an immediate studio_* create / write / unlink / reorder RPC.
     * Those already hit the DB; keep Save/Discard active so any change lights the toolbar.
     */
    async applyStudioMutation(payload, selectCreated = false) {
        await this.applyPayload(payload, selectCreated);
        this.markDirty();
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
            visibility: [],
            hub_group: [],
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
            visibility: "studio_search_visibility_groups",
            hub_group: "studio_search_hub_groups",
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

    pickSetupVisibilityGroup(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        const name = ev.currentTarget.dataset.name || "";
        if (!id || this.state.setup.menu_group_ids.includes(id)) {
            this.state.setupQuery.visibility = "";
            this.state.setupResults.visibility = [];
            return;
        }
        this.state.setup.menu_group_ids = [...this.state.setup.menu_group_ids, id];
        this.state.setup.menu_group_names = [
            ...this.state.setup.menu_group_names,
            name,
        ];
        this.state.setupQuery.visibility = "";
        this.state.setupResults.visibility = [];
        this.markSetupDirty();
    }

    removeSetupVisibilityGroup(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        const idx = this.state.setup.menu_group_ids.indexOf(id);
        if (idx >= 0) {
            this.state.setup.menu_group_ids.splice(idx, 1);
            this.state.setup.menu_group_names.splice(idx, 1);
            this.markSetupDirty();
        }
    }

    onSetupMenuWebIconInput(ev) {
        this.state.setup.menu_web_icon = ev.target.value;
        this.markSetupDirty();
    }

    onSetupMenuWebIconFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) {
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const raw = String(reader.result || "");
            const base64 = raw.includes(",") ? raw.split(",")[1] : raw;
            this.state.setup.menu_web_icon_data = base64;
            this.markSetupDirty();
        };
        reader.readAsDataURL(file);
    }

    clearSetupMenuWebIconImage() {
        this.state.setup.menu_web_icon_data = false;
        this.markSetupDirty();
    }

    clearSetupMenuParent() {
        this.state.setup.menu_parent_id = false;
        this.state.setup.menu_parent_name = "";
        this.markSetupDirty();
    }

    pickSetupHubGroup(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        const name = ev.currentTarget.dataset.name || "";
        this.state.setup.group_id = id;
        this.state.setup.group_name = name;
        this.state.setupQuery.hub_group = "";
        this.state.setupResults.hub_group = [];
        this.markSetupDirty();
    }

    clearSetupHubGroup() {
        this.state.setup.group_id = false;
        this.state.setup.group_name = "";
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
                menu_group_ids: setup.menu_group_ids || [],
                group_id: setup.group_id || false,
                menu_web_icon: setup.menu_web_icon || false,
                menu_web_icon_data: setup.menu_web_icon_data || false,
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
            this.state.setupDirty = false;
            await this.applyPayload(payload, false, { resetEditor: true });
            await this.loadCatalogs();
            await this.loadSamples("");
            if (cleanup > 0) {
                this.state.setupBanner = { count: cleanup };
            }
            this.notification.add(_t("Dashboard settings saved"), { type: "success" });
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
                if (!this.selectedSlotOwned) {
                    this.notification.add(
                        _t("Shared item — edit it on its source dashboard, or unlink the pack in Setup."),
                        { type: "warning" }
                    );
                    return;
                }
                const vals = {
                    label: ed.label,
                    label_plural: ed.label_plural,
                    icon: ed.icon || false,
                    style: ed.style || "default",
                    style_mode: ed.style_mode || "static",
                    show_if_zero: ed.show_if_zero,
                    action_xmlid: ed.action_xmlid || false,
                    ...(this.state.zone === "manage" && ed.section
                        ? { section: ed.section }
                        : {}),
                    action_method: ed.action_method || false,
                    action_model: ed.action_model || false,
                    amount_field: ed.amount_field || false,
                    count_field: ed.count_field || false,
                    compute_model: ed.compute_model || false,
                    relate_field: ed.relate_field || false,
                    compute_domain: ed.compute_domain || "[]",
                    value_mode: ed.value_mode || "count",
                    amount_aggregator: this._slotAmountAggregatorValue(),
                    module_ids: ed.module_ids || [],
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
                await this.applyPayload(payload, false, { resetEditor: true });
                this.notification.add(_t("Saved"), { type: "success" });
            } else if (this.state.dirty) {
                // Structure-only changes already persisted via studio_* RPCs.
                this.state.dirty = false;
                this.state.dirtyToken = (this.state.dirtyToken || 0) + 1;
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
        const slot = this.slotsForZone.find((s) => s.id === slotId);
        if (slot && slot.owned === false) {
            ev.preventDefault();
            this._dragSlotId = null;
            return;
        }
        this._dragSlotId = slotId;
        if (ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", String(slotId));
        }
    }

    /** Owned slots in a section (shared pack rows are not on this blueprint). */
    _ownedSectionSlots(section) {
        return this.slotsForZone.filter(
            (s) => s.section === section && s.owned !== false
        );
    }

    async onDropSlot(targetId, ev) {
        ev.preventDefault();
        const sourceId = this._dragSlotId || Number(ev.dataTransfer?.getData("text/plain"));
        this._dragSlotId = null;
        if (!sourceId || sourceId === targetId) {
            return;
        }
        const source = this.slotsForZone.find((s) => s.id === sourceId);
        const target = this.slotsForZone.find((s) => s.id === targetId);
        if (!source || !target || source.owned === false || target.owned === false) {
            this.notification.add(
                _t("Shared items cannot be reordered here. Reorder them on their source dashboard."),
                { type: "warning" }
            );
            return;
        }
        if (source.section !== target.section) {
            return;
        }
        const section = source.section;
        const ids = this._ownedSectionSlots(section).map((s) => s.id);
        const from = ids.indexOf(sourceId);
        const to = ids.indexOf(targetId);
        if (from < 0 || to < 0) {
            return;
        }
        ids.splice(from, 1);
        ids.splice(to, 0, sourceId);
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_reorder_slots",
                [[this.blueprintId], section, ids]
            );
            await this.applyStudioMutation(payload);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Reorder failed"),
                { type: "danger" }
            );
        }
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

    async addManageItem(sectionId) {
        this.state.manageSection = sectionId;
        return this.addItem(sectionId);
    }

    async addItem(sectionOverride = null) {
        this.state.saving = true;
        try {
            if (this.state.zone === "header") {
                const payload = await this.orm.call(
                    "dashboard.blueprint",
                    "studio_create_header_item",
                    [[this.blueprintId], { kind: "subtitle", field_names: "" }]
                );
                await this.applyStudioMutation(payload, true);
                this.notification.add(_t("Header line added"), { type: "success" });
                return;
            }
            const section = sectionOverride || this._defaultSectionForZone();
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
                        : section === "menu_views"
                          ? _t("New view")
                          : section === "menu_new"
                            ? _t("New create action")
                            : section === "menu_reports"
                              ? _t("New report")
                              : _t("New menu item");
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_create_slot",
                [[this.blueprintId], section, { label, label_plural: label }]
            );
            await this.applyStudioMutation(payload, true);
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
            await this.applyStudioMutation(payload, true);
            return;
        }
        if (!this.selectedSlot) {
            return;
        }
        if (this.selectedSlot.owned === false) {
            this.notification.add(
                _t("Shared item — remove it on its source dashboard, or unlink the pack in Setup."),
                { type: "warning" }
            );
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
        await this.applyStudioMutation(payload, true);
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
            await this.applyStudioMutation(payload);
            return;
        }
        if (!this.selectedSlotOwned || !this.selectedSlot) {
            this.notification.add(
                _t("Shared items cannot be reordered here. Reorder them on their source dashboard."),
                { type: "warning" }
            );
            return;
        }
        await this.moveSlot(this.selectedSlot.id, delta);
    }

    /**
     * Delegated clicks for Items in this block (avoids nested drag/select
     * handlers swallowing up/down/delete).
     */
    onItemListClick(ev) {
        const listEl = ev.currentTarget;
        const actionEl = ev.target.closest?.("[data-slot-action]");
        if (!actionEl || !listEl?.contains(actionEl)) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        const slotId = Number(actionEl.getAttribute("data-slot-id"));
        const action = actionEl.getAttribute("data-slot-action");
        if (!slotId || !action) {
            return;
        }
        if (action === "select") {
            this.selectSlot(slotId);
            return;
        }
        if (action === "up") {
            this.moveSlot(slotId, -1);
            return;
        }
        if (action === "down") {
            this.moveSlot(slotId, 1);
            return;
        }
        if (action === "remove") {
            this.removeSlot(slotId);
        }
    }

    async moveSlot(slotId, delta) {
        const slot = this.slotsForZone.find((s) => s.id === slotId);
        if (!slot) {
            return;
        }
        if (slot.owned === false) {
            this.notification.add(
                _t("Shared items cannot be reordered here. Reorder them on their source dashboard."),
                { type: "warning" }
            );
            return;
        }
        const section = slot.section;
        if (!section) {
            return;
        }
        const ids = this._ownedSectionSlots(section).map((s) => s.id);
        const idx = ids.indexOf(slotId);
        const next = idx + delta;
        if (idx < 0 || next < 0 || next >= ids.length) {
            return;
        }
        [ids[idx], ids[next]] = [ids[next], ids[idx]];
        this.state.selectedSlotId = slotId;
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_reorder_slots",
                [[this.blueprintId], section, ids]
            );
            await this.applyStudioMutation(payload);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Reorder failed"),
                { type: "danger" }
            );
        }
    }

    async removeSlot(slotId) {
        const slot = this.slotsForZone.find((s) => s.id === slotId);
        if (!slot) {
            return;
        }
        if (slot.owned === false) {
            this.notification.add(
                _t("Shared item — remove it on its source dashboard, or unlink the pack in Setup."),
                { type: "warning" }
            );
            return;
        }
        if (!confirm(_t("Remove this item from the card?"))) {
            return;
        }
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_unlink_slot",
                [[this.blueprintId], slotId]
            );
            if (this.state.selectedSlotId === slotId) {
                this.state.selectedSlotId = null;
            }
            await this.applyStudioMutation(payload);
            this.notification.add(_t("Item removed"), { type: "info" });
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Remove failed"),
                { type: "danger" }
            );
        }
    }

    _scopeResModel() {
        return (
            this.state.payload?.graph_model ||
            this.state.payload?.host_model ||
            "res.partner"
        );
    }

    async addScope(mode = "include") {
        const cleanMode = mode === "restrict" ? "restrict" : "include";
        const name =
            cleanMode === "restrict" ? _t("My Data") : _t("Data to Include");
        this.state.saving = true;
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_create_scope",
                [
                    [this.blueprintId],
                    {
                        name,
                        mode: cleanMode,
                        domain: "[]",
                        default_on: false,
                    },
                ]
            );
            await this.applyStudioMutation(payload, true);
            this.notification.add(
                cleanMode === "restrict"
                    ? _t("My Data scope added")
                    : _t("Data to Include scope added"),
                { type: "success" }
            );
        } catch (error) {
            this.notification.add(error?.data?.message || error.message || _t("Add scope failed"), {
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    async addGraphVariant() {
        this.state.saving = true;
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_create_graph_variant",
                [[this.blueprintId], {}]
            );
            await this.applyStudioMutation(payload, true);
            this.notification.add(_t("Chart Model Option added"), { type: "success" });
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Add chart model option failed"),
                { type: "danger" }
            );
        } finally {
            this.state.saving = false;
        }
    }

    async setDefaultGraphVariant(variantId) {
        this.state.saving = true;
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_set_default_graph_variant",
                [[this.blueprintId], variantId]
            );
            await this.applyStudioMutation(payload);
            this.notification.add(_t("Default chart model updated"), { type: "success" });
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Set default failed"),
                { type: "danger" }
            );
            await this.loadPayload();
        } finally {
            this.state.saving = false;
        }
    }

    async updateGraphVariant(variantId, field, value) {
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_write_graph_variant",
                [[this.blueprintId], variantId, { [field]: value }]
            );
            await this.applyStudioMutation(payload);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Chart Model Option update failed"),
                { type: "danger" }
            );
            await this.loadPayload();
        }
    }

    _variantPickerKey(variantId, kind) {
        return `${variantId}:${kind}`;
    }

    variantPickerQuery(variantId, kind) {
        return this.state.variantPickerQuery[this._variantPickerKey(variantId, kind)] || "";
    }

    variantPickerResults(variantId, kind) {
        return this.state.variantPickerResults[this._variantPickerKey(variantId, kind)] || [];
    }

    variantPickerScopeLabel(variantId) {
        return this.state.variantPickerScopeLabel[variantId] || "";
    }

    variantPickerShowAll(variantId) {
        return Boolean(this.state.variantPickerShowAll[variantId]);
    }

    clearVariantPicker(variantId, kind) {
        const key = this._variantPickerKey(variantId, kind);
        this.state.variantPickerQuery[key] = "";
        this.state.variantPickerResults[key] = [];
        if (kind === "action") {
            this.state.variantPickerScopeLabel[variantId] = "";
        }
    }

    onVariantPickerBlur(variantId, kind, ev) {
        const picker = ev.currentTarget.closest(".o_ds_variant_picker");
        this._variantPickerBlurTimers = this._variantPickerBlurTimers || {};
        const key = this._variantPickerKey(variantId, kind);
        clearTimeout(this._variantPickerBlurTimers[key]);
        this._variantPickerBlurTimers[key] = setTimeout(() => {
            const active = document.activeElement;
            if (picker && active && picker.contains(active)) {
                return;
            }
            this.clearVariantPicker(variantId, kind);
        }, 180);
    }

    variantModelScopeLabel(variantId) {
        return this.state.variantModelScopeLabel[variantId] || "";
    }

    variantModelShowAll(variantId) {
        return Boolean(this.state.variantModelShowAll[variantId]);
    }

    async onVariantModelSearch(variantId, ev) {
        const term = ev?.target?.value ?? this.variantPickerQuery(variantId, "model");
        const key = this._variantPickerKey(variantId, "model");
        this.state.variantPickerQuery[key] = term;
        const res = await this.orm.call(
            "dashboard.blueprint",
            "studio_search_chart_models",
            [
                [this.blueprintId],
                term || "",
                20,
                Boolean(this.state.variantModelShowAll[variantId]),
            ]
        );
        this.state.variantPickerResults[key] = res.models || [];
        this.state.variantModelScopeLabel[variantId] = res.scope_label || "";
    }

    toggleVariantModelsShowAll(variantId) {
        this.state.variantModelShowAll[variantId] = !this.state.variantModelShowAll[variantId];
        this.onVariantModelSearch(variantId);
    }

    async pickVariantModel(variantId, row) {
        const model = (row?.model || "").trim();
        if (!model) {
            return;
        }
        const variant = (this.state.payload.graph_variants || []).find((v) => v.id === variantId);
        this.clearVariantPicker(variantId, "model");
        if (variant && variant.graph_model === model) {
            return;
        }
        await this.updateGraphVariant(variantId, "graph_model", model);
        await this.refreshVariantLinkPathCatalogs(variantId);
    }

    variantLinkPathRows(variantId) {
        const variant = (this.state.payload?.graph_variants || []).find((v) => v.id === variantId);
        const segments = (variant?.graph_data_field || "").split(".").filter(Boolean);
        const extra = Boolean(this.state.variantLinkPathExtraHop[variantId]);
        const count = Math.max(1, segments.length + (extra ? 1 : 0));
        const catalogs = this.state.variantLinkPathHopFields[variantId] || [];
        const rows = [];
        for (let i = 0; i < count; i++) {
            rows.push({
                index: i,
                value: segments[i] || "",
                options: catalogs[i] || [],
                showSep: i < count - 1,
            });
        }
        return rows;
    }

    canAddVariantLinkPathHop(variantId) {
        if (this.state.variantLinkPathExtraHop[variantId]) {
            return false;
        }
        const variant = (this.state.payload?.graph_variants || []).find((v) => v.id === variantId);
        const segments = (variant?.graph_data_field || "").split(".").filter(Boolean);
        if (!segments.length) {
            return false;
        }
        const lastIdx = segments.length - 1;
        const opts = (this.state.variantLinkPathHopFields[variantId] || [])[lastIdx] || [];
        const sel = opts.find((f) => f.name === segments[lastIdx]);
        return Boolean(sel?.relation);
    }

    canRemoveVariantLinkPathHop(variantId) {
        const variant = (this.state.payload?.graph_variants || []).find((v) => v.id === variantId);
        return Boolean((variant?.graph_data_field || "").split(".").filter(Boolean).length);
    }

    async refreshVariantLinkPathCatalogs(variantId) {
        const variant = (this.state.payload?.graph_variants || []).find((v) => v.id === variantId);
        if (!variant?.graph_model) {
            this.state.variantLinkPathHopFields[variantId] = [];
            return;
        }
        const segments = (variant.graph_data_field || "").split(".").filter(Boolean);
        const hopCount = Math.max(
            1,
            segments.length + (this.state.variantLinkPathExtraHop[variantId] ? 1 : 0)
        );
        const catalogs = [];
        let model = variant.graph_model;
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
        this.state.variantLinkPathHopFields[variantId] = catalogs;
    }

    async refreshAllVariantLinkPathCatalogs() {
        const ids = (this.state.payload?.graph_variants || []).map((v) => v.id);
        await Promise.all(ids.map((id) => this.refreshVariantLinkPathCatalogs(id)));
    }

    async onVariantLinkPathHopChange(variantId, hopIndex, ev) {
        const name = ev.target.value;
        const variant = (this.state.payload?.graph_variants || []).find((v) => v.id === variantId);
        if (!variant) {
            return;
        }
        let segments = (variant.graph_data_field || "").split(".").filter(Boolean);
        while (segments.length <= hopIndex) {
            segments.push("");
        }
        if (name) {
            segments[hopIndex] = name;
            segments = segments.slice(0, hopIndex + 1);
        } else {
            segments = segments.slice(0, hopIndex);
        }
        const path = segments.filter(Boolean).join(".");
        this.state.variantLinkPathExtraHop[variantId] = false;
        await this.updateGraphVariant(variantId, "graph_data_field", path || false);
        await this.refreshVariantLinkPathCatalogs(variantId);
    }

    async addVariantLinkPathHop(variantId) {
        if (!this.canAddVariantLinkPathHop(variantId)) {
            return;
        }
        this.state.variantLinkPathExtraHop[variantId] = true;
        await this.refreshVariantLinkPathCatalogs(variantId);
    }

    async removeVariantLinkPathHop(variantId) {
        const variant = (this.state.payload?.graph_variants || []).find((v) => v.id === variantId);
        if (!variant) {
            return;
        }
        const segments = (variant.graph_data_field || "").split(".").filter(Boolean);
        if (!segments.length) {
            return;
        }
        segments.pop();
        this.state.variantLinkPathExtraHop[variantId] = false;
        await this.updateGraphVariant(
            variantId,
            "graph_data_field",
            segments.join(".") || false
        );
        await this.refreshVariantLinkPathCatalogs(variantId);
    }

    async onVariantActionSearch(variantId, graphModel, ev) {
        const term = ev?.target?.value ?? this.variantPickerQuery(variantId, "action");
        const key = this._variantPickerKey(variantId, "action");
        this.state.variantPickerQuery[key] = term;
        const res = await this.orm.call(
            "dashboard.blueprint",
            "studio_search_actions",
            [
                [this.blueprintId],
                term || "",
                25,
                Boolean(this.state.variantPickerShowAll[variantId]),
                graphModel || false,
            ]
        );
        this.state.variantPickerResults[key] = res.actions || [];
        this.state.variantPickerScopeLabel[variantId] = res.scope_label || "";
    }

    toggleVariantActionsShowAll(variantId, graphModel) {
        this.state.variantPickerShowAll[variantId] = !this.state.variantPickerShowAll[variantId];
        this.onVariantActionSearch(variantId, graphModel);
    }

    async pickVariantAction(variantId, act) {
        const xmlid = (act?.xmlid || "").trim();
        if (!xmlid) {
            return;
        }
        const variant = (this.state.payload.graph_variants || []).find((v) => v.id === variantId);
        this.clearVariantPicker(variantId, "action");
        if (variant && variant.primary_action_xmlid === xmlid) {
            return;
        }
        await this.updateGraphVariant(variantId, "primary_action_xmlid", xmlid);
    }

    onGraphVariantFieldBlur(variantId, field, ev) {
        let value = ev.target.value;
        const variant = (this.state.payload.graph_variants || []).find((v) => v.id === variantId);
        if (!variant) {
            return;
        }
        if (field === "primary_button_label") {
            value = (value || "").trim();
            if (!value) {
                ev.target.value = variant.primary_button_label || "";
                return;
            }
            if (variant.primary_button_label === value) {
                return;
            }
            this.updateGraphVariant(variantId, field, value);
        }
    }

    async removeGraphVariant(variantId) {
        if (!confirm(_t("Remove this chart model option?"))) {
            return;
        }
        this.state.saving = true;
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_unlink_graph_variant",
                [[this.blueprintId], variantId]
            );
            await this.applyStudioMutation(payload);
            this.notification.add(_t("Chart Model Option removed"), { type: "info" });
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Remove chart model option failed"),
                { type: "danger" }
            );
        } finally {
            this.state.saving = false;
        }
    }

    async reorderGraphVariants(orderedIds) {
        const payload = await this.orm.call(
            "dashboard.blueprint",
            "studio_reorder_graph_variants",
            [[this.blueprintId], orderedIds]
        );
        await this.applyStudioMutation(payload);
    }

    onDragStartGraphVariant(variantId, ev) {
        this._dragGraphVariantId = variantId;
        if (ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", String(variantId));
        }
    }

    async onDropGraphVariant(targetId, ev) {
        ev.preventDefault();
        const sourceId =
            this._dragGraphVariantId || Number(ev.dataTransfer?.getData("text/plain"));
        this._dragGraphVariantId = null;
        if (!sourceId || sourceId === targetId) {
            return;
        }
        const ids = (this.state.payload.graph_variants || []).map((v) => v.id);
        const from = ids.indexOf(sourceId);
        const to = ids.indexOf(targetId);
        if (from < 0 || to < 0) {
            return;
        }
        ids.splice(from, 1);
        ids.splice(to, 0, sourceId);
        try {
            await this.reorderGraphVariants(ids);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Reorder failed"),
                { type: "danger" }
            );
        }
    }

    async moveGraphVariant(variantId, delta) {
        const ids = (this.state.payload.graph_variants || []).map((v) => v.id);
        const idx = ids.indexOf(variantId);
        const next = idx + delta;
        if (idx < 0 || next < 0 || next >= ids.length) {
            return;
        }
        [ids[idx], ids[next]] = [ids[next], ids[idx]];
        try {
            await this.reorderGraphVariants(ids);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Reorder failed"),
                { type: "danger" }
            );
        }
    }

    async updateScope(scopeId, field, value) {
        try {
            const payload = await this.orm.call(
                "dashboard.blueprint",
                "studio_write_scope",
                [[this.blueprintId], scopeId, { [field]: value }]
            );
            await this.applyStudioMutation(payload);
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
            await this.applyStudioMutation(payload);
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
        await this.applyStudioMutation(payload);
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
            await this.applyStudioMutation(payload);
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
        await this.applyStudioMutation(payload);
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
        await this.applyStudioMutation(payload);
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
        const mode = this._scopeModeOf(sourceId);
        if (!mode || mode !== this._scopeModeOf(targetId)) {
            return;
        }
        const modeIds = this._scopesByMode(mode).map((s) => s.id);
        const from = modeIds.indexOf(sourceId);
        const to = modeIds.indexOf(targetId);
        if (from < 0 || to < 0) {
            return;
        }
        modeIds.splice(from, 1);
        modeIds.splice(to, 0, sourceId);
        try {
            await this.reorderScopes(this._mergeScopeModeOrder(mode, modeIds));
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Reorder failed"),
                { type: "danger" }
            );
        }
    }

    async moveScope(scopeId, delta) {
        const mode = this._scopeModeOf(scopeId);
        if (!mode) {
            return;
        }
        const modeIds = this._scopesByMode(mode).map((s) => s.id);
        const idx = modeIds.indexOf(scopeId);
        const next = idx + delta;
        if (idx < 0 || next < 0 || next >= modeIds.length) {
            return;
        }
        [modeIds[idx], modeIds[next]] = [modeIds[next], modeIds[idx]];
        try {
            await this.reorderScopes(this._mergeScopeModeOrder(mode, modeIds));
        } catch (error) {
            this.notification.add(
                error?.data?.message || error.message || _t("Reorder failed"),
                { type: "danger" }
            );
        }
    }

    async publish() {
        const p = this.state.payload || {};
        const liveLeaf = p.generated_menu_leaf || "";
        const nextName = p.menu_name || "";
        const liveParent = p.generated_menu_parent_id || false;
        const nextParent = p.menu_parent_id || false;
        const menuWouldChange =
            Boolean(liveLeaf) &&
            (nextName !== liveLeaf || nextParent !== liveParent);
        if (menuWouldChange) {
            const fromLabel = p.generated_menu_name || liveLeaf;
            const toParent = p.menu_parent_name || _t("(no parent)");
            const toLabel = nextName
                ? `${toParent} / ${nextName}`
                : toParent;
            const confirmed = await new Promise((resolve) => {
                this.dialog.add(ConfirmationDialog, {
                    title: _t("Publish menu change?"),
                    body: _t(
                        "Publish will rename/move the menu entry from '%s' to '%s'. Continue?"
                    )
                        .replace("%s", fromLabel)
                        .replace("%s", toLabel),
                    confirm: () => resolve(true),
                    cancel: () => resolve(false),
                    confirmLabel: _t("Publish"),
                });
            });
            if (!confirmed) {
                return;
            }
        }
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
