/** @odoo-module **/

import {Component, onWillStart, useRef, useState, useSubEnv} from "@odoo/owl";
import {browser} from "@web/core/browser/browser";
import {download} from "@web/core/network/download";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {useSetupAction} from "@web/search/action_hook";
import {Layout} from "@web/search/layout";
import {getDefaultConfig} from "@web/views/view";

const PDFJS_VIEWER = "/web/static/lib/pdfjs/web/viewer.html";
const STORAGE_KEY = "dub_reporting_birt.viewer";
const ZOOM_STEPS = [50, 67, 75, 80, 90, 100, 110, 125, 150, 175, 200];

/**
 * The router does not keep client action params in the URL: remember them
 * in the tab session so a page reload can show the report again.
 */
function getViewerParams(params) {
    try {
        if (params?.model) {
            browser.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(params));
            return params;
        }
        return JSON.parse(browser.sessionStorage.getItem(STORAGE_KEY));
    } catch {
        return params?.model ? params : null;
    }
}

// On-screen viewer of a BIRT report rendered from a wizard: HTML preview or
// PDF (pdf.js), format switch, download and "Edit parameters" which reopens
// the wizard. Server side: dub.birt.report.wizard.mixin.
export class BirtViewer extends Component {
    static template = "dub_reporting_birt.BirtViewer";
    static components = {Layout};
    static props = ["*"];

    setup() {
        useSubEnv({config: {...getDefaultConfig(), ...this.env.config}});
        useSetupAction();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.ui = useService("ui");
        this.params = getViewerParams(this.props.action.params);
        if (this.params?.name) {
            this.env.config.setDisplayName(this.params.name);
        }
        this.state = useState({
            format: this.params?.format || "pdf",
            resId: false,
            loading: true,
            zoom: this.params?.zoom || 100,
            foldable: false,
            // number of folded groups: drives the expand / collapse button
            folded: 0,
        });
        this.foldRows = [];
        this.folded = new Set();
        this.iframe = useRef("iframe");
        onWillStart(() => this.params && this.ensureWizard());
    }

    get contentUrl() {
        return `/report/birt/viewer/${this.params.model}/${this.state.resId}`;
    }

    get iframeSrc() {
        const url = `${this.contentUrl}?fmt=${this.state.format}`;
        if (this.state.format === "pdf") {
            return `${PDFJS_VIEWER}?file=${encodeURIComponent(url)}`;
        }
        return url;
    }

    /**
     * The wizard is transient: recreate it from the stored values if the
     * vacuum removed it while the viewer was open.
     */
    async ensureWizard() {
        this.state.resId = await this.orm.call(
            this.params.model,
            "birt_viewer_ensure",
            [this.state.resId || this.params.res_id, this.params.values]
        );
        this.params.res_id = this.state.resId;
        getViewerParams(this.params);
    }

    async switchFormat(format) {
        await this.ensureWizard();
        this.state.loading = true;
        this.state.format = format;
    }

    async editParameters() {
        await this.ensureWizard();
        const action = await this.orm.call(this.params.model, "action_birt_reopen", [
            [this.state.resId],
            this.state.format,
        ]);
        await this.actionService.doAction(action);
    }

    async download() {
        await this.ensureWizard();
        this.ui.block();
        try {
            await download({
                url: this.contentUrl,
                data: {fmt: "pdf", download: 1},
            });
        } finally {
            this.ui.unblock();
        }
    }

    onIframeLoad() {
        this.state.loading = false;
        this.applyZoom();
        // pdf.js: static document, no drilldown nor folding
        const doc = this.state.format === "html" ? this.iframe.el?.contentDocument : null;
        doc?.addEventListener("click", (ev) => this.onReportClick(ev));
        this.setupFolding(doc);
    }

    onReportClick(ev) {
        const link = ev.target.closest?.('a[href^="odoo-drill:"]');
        if (link) {
            ev.preventDefault();
            return this.drilldown(link);
        }
        const header = ev.target.closest?.('tr[id^="h|"]');
        if (header) {
            this.toggleFold(header.id.slice(2));
        }
    }

    /**
     * Template hyperlinks "odoo-drill:?key=...&..." open an Odoo action
     * (see dub.birt.report.wizard.mixin.birt_drilldown).
     */
    async drilldown(link) {
        const query = link.getAttribute("href").split("?")[1] || "";
        const values = Object.fromEntries(new URLSearchParams(query));
        await this.ensureWizard();
        const action = await this.orm.call(this.params.model, "birt_drilldown", [
            [this.state.resId],
            values,
        ]);
        if (action) {
            await this.actionService.doAction(action);
        }
    }

    /**
     * Groups the template marks with row bookmarks (rendered as the row id):
     * "h|<keys>|" group header, "t|<keys>|" group footer, "d|<keys>|<n>"
     * detail, <keys> being the group keys from the outer group in, joined
     * by "|". Folding a group hides its rows but keeps its header and its
     * footer, which carries the totals.
     */
    setupFolding(doc) {
        const rows = doc ? doc.querySelectorAll('tr[id^="h|"], tr[id^="t|"], tr[id^="d|"]') : [];
        this.foldRows = [...rows].map((el) => {
            const parts = el.id.slice(2).split("|");
            if (el.id[0] !== "d") {
                parts.pop();
            }
            const ancestors = [];
            for (let i = 1; i < parts.length; i++) {
                ancestors.push(`${parts.slice(0, i).join("|")}|`);
            }
            return {el, ancestors};
        });
        for (const {el} of this.foldRows) {
            if (el.id[0] === "h") {
                const caret = doc.createElement("span");
                caret.className = "o_birt_fold";
                el.cells[0]?.prepend(caret);
            }
        }
        this.folded = new Set();
        this.state.folded = 0;
        this.state.foldable = this.foldRows.some(({el}) => el.id[0] === "h");
    }

    toggleFold(key) {
        if (!this.folded.delete(key)) {
            this.folded.add(key);
        }
        this.applyFolding();
    }

    foldAll(fold) {
        this.folded = new Set(
            fold
                ? this.foldRows.filter(({el}) => el.id[0] === "h").map(({el}) => el.id.slice(2))
                : []
        );
        this.applyFolding();
    }

    applyFolding() {
        this.state.folded = this.folded.size;
        for (const {el, ancestors} of this.foldRows) {
            el.classList.toggle("o_birt_folded", ancestors.some((key) => this.folded.has(key)));
            if (el.id[0] === "h") {
                el.classList.toggle("o_birt_fold_closed", this.folded.has(el.id.slice(2)));
            }
        }
    }

    /**
     * pdf.js has its own zoom: this one applies to the HTML preview only,
     * on the iframe document (same origin, scripts stay sandboxed).
     */
    setZoom(direction) {
        const current = ZOOM_STEPS.indexOf(this.state.zoom);
        const index = direction ? current + direction : ZOOM_STEPS.indexOf(100);
        this.state.zoom = ZOOM_STEPS[Math.max(0, Math.min(ZOOM_STEPS.length - 1, index))];
        this.params.zoom = this.state.zoom;
        getViewerParams(this.params);
        this.applyZoom();
    }

    applyZoom() {
        const body = this.state.format === "html" && this.iframe.el?.contentDocument?.body;
        if (body) {
            body.style.zoom = `${this.state.zoom}%`;
        }
    }
}

registry.category("actions").add("dub_reporting_birt.viewer_main", BirtViewer);

// Entry point: a report printed from a wizard reopened through "Edit
// parameters" replaces the viewer it comes from, so the breadcrumbs don't
// grow at every reprint.
registry.category("actions").add("dub_reporting_birt.viewer", (env, action) =>
    env.services.action.doAction(
        {...action, tag: "dub_reporting_birt.viewer_main"},
        {stackPosition: action.params.replace ? "replaceCurrentAction" : undefined}
    )
);
