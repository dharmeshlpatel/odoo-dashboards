/** @odoo-module **/

import { Component, onWillStart, onPatched, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { DomainSelectorDialog } from "@web/core/domain_selector_dialog/domain_selector_dialog";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const MANAGE_SECTIONS = [
    { id: "menu_views", label: "Views" },
    { id: "menu_new", label: "New" },
    { id: "menu_reports", label: "Reports" },
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
    kind: "left",
    field_names: "",
    primary_button_label: "",
    primary_action_xmlid: "",
    graph_caption: "",
    graph_measure: "",
    graph_groupby: "",
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
        this.previewChartRef = useRef("previewChart");
        this._previewChart = null;
        this._dragSlotId = null;
        this.state = useState({
            zone: "kpis",
            payload: null,
            selectedSlotId: null,
            selectedHeaderId: null,
            manageSection: "menu_views",
            editor: EMPTY_EDITOR(),
            catalogs: {
                hostFields: [],
                graphFields: [],
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
            loading: true,
            saving: false,
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

    get kpisPreview() {
        const live = this.state.preview?.slots?.kpis;
        if (this.state.preview?.ok && live) {
            return live.slice(0, 6);
        }
        return (this.state.payload?.slots || []).filter((s) => s.section === "kpi").slice(0, 5);
    }

    get totalsPreview() {
        const live = this.state.preview?.slots?.button_box;
        if (this.state.preview?.ok && live) {
            return live.slice(0, 4);
        }
        return (this.state.payload?.slots || [])
            .filter((s) => s.section === "button_box")
            .slice(0, 4);
    }

    get shortcutsPreview() {
        const live = this.state.preview?.slots?.buttons;
        if (this.state.preview?.ok && live) {
            return live.slice(0, 5);
        }
        return (this.state.payload?.slots || []).filter((s) => s.section === "bottom").slice(0, 5);
    }

    get previewTitle() {
        return this.state.preview?.title || this.state.payload?.name || "Dashboard";
    }

    get previewPrimaryLabel() {
        return (
            this.state.preview?.primary_label ||
            this.state.payload?.primary_button_label ||
            "Open"
        );
    }

    get previewGraphCaption() {
        return this.state.preview?.graph_caption || this.state.payload?.graph_caption || "Analysis";
    }

    get previewGraphBars() {
        const bars = this.state.preview?.graph_bars;
        if (bars && bars.length) {
            return bars;
        }
        return [40, 70, 55, 85, 45, 62];
    }

    get previewHeaderLines() {
        if (this.state.preview?.ok) {
            return (this.state.preview.header_lines || []).slice(0, 3);
        }
        return (this.state.payload?.headers || []).slice(0, 2).map((h) => ({
            id: h.id,
            icon: h.icon,
            text: h.field_names || "",
        }));
    }

    get hasLivePreview() {
        return Boolean(this.state.preview?.ok);
    }

    get canStructureEdit() {
        return ["kpis", "totals", "shortcuts", "manage", "header"].includes(this.state.zone);
    }

    get canSave() {
        if (this.state.zone === "config") {
            return this.state.dirty;
        }
        return this.state.dirty;
    }

    markDirty() {
        this.state.dirty = true;
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
            this._syncEditorFromSelection();
            this.state.dirty = false;
            await this.loadPreview();
        } finally {
            this.state.loading = false;
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

    async selectSample(sampleId) {
        this.state.sampleId = sampleId;
        await this.loadPreview();
    }

    async loadCatalogs() {
        const bp = this.blueprintId;
        const [hostFields, conditions, icons] = await Promise.all([
            this.orm.call("dashboard.blueprint", "studio_model_fields", [[bp], null, null]),
            this.orm.call("dashboard.blueprint", "studio_condition_catalog", [[bp]]),
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
        this.state.catalogs.hostFields = hostFields;
        this.state.catalogs.graphFields = graphFields;
        this.state.catalogs.conditions = conditions;
        this.state.catalogs.icons = icons;
        await this.searchActions("");
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
            ed.graph_caption = p.graph_caption || "";
            ed.graph_measure = p.graph_measure || "";
            ed.graph_groupby = p.graph_groupby || "";
            this.state.editor = ed;
            return;
        }
        if (this.state.zone === "header") {
            const item = this.selectedHeader;
            if (item) {
                this.state.selectedHeaderId = item.id;
                ed.kind = item.kind || "left";
                ed.field_names = item.field_names || "";
                ed.icon = item.icon || "";
            }
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
        }
        this.state.editor = ed;
    }

    onEditorInput(field, ev) {
        const target = ev.target;
        let value = target.type === "checkbox" ? target.checked : target.value;
        if (field === "condition_ids") {
            value = Array.from(target.selectedOptions || []).map((o) => Number(o.value));
        }
        this.state.editor[field] = value;
        this.markDirty();
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
        this._syncEditorFromSelection();
        this.state.dirty = false;
        await this.loadPreview();
    }

    async saveCurrent() {
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
                              graph_caption: ed.graph_caption,
                          }
                        : {
                              graph_measure: ed.graph_measure,
                              graph_groupby: ed.graph_groupby,
                              graph_caption: ed.graph_caption,
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
                            field_names: ed.field_names,
                            icon: ed.icon || false,
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
                    [[this.blueprintId], { kind: "left", field_names: "email" }]
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

    async toggleScope(scopeId, checked) {
        const payload = await this.orm.call(
            "dashboard.blueprint",
            "studio_write_scope",
            [[this.blueprintId], scopeId, { default_on: checked }]
        );
        await this.applyPayload(payload, false);
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
