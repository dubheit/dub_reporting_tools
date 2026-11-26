/** @odoo-module **/

import {
    Component,
    onWillStart,
    useExternalListener,
    useRef,
    useState,
    useSubEnv,
} from "@odoo/owl";
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
// The fit to width leaves room around the sheet like the form views:
// at most as wide as a form sheet, with its side padding
const FIT_MAX_WIDTH = 1534;
const FIT_PADDING = 16;

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
            // HTML preview zoom in %, null to fit the viewer width
            zoom: this.params?.zoom || null,
            fitZoom: 100,
            foldable: false,
            // number of folded groups: drives the expand / collapse button
            folded: 0,
        });
        this.foldRows = [];
        this.folded = new Set();
        this.iframe = useRef("iframe");
        useExternalListener(window, "resize", () => this.applyZoom());
        onWillStart(() => this.params && this.ensureWizard());
    }

    get contentUrl() {
        return `/report/birt/viewer/${this.params.model}/${this.state.resId}`;
    }

    get iframeSrc() {
        const url = `${this.contentUrl}?fmt=${this.state.format}`;
        if (this.state.format === "pdf") {
            return `${PDFJS_VIEWER}?file=${encodeURIComponent(url)}#zoom=page-width`;
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
     * pdf.js has its own zoom and opens at the page width: this one applies
     * to the HTML preview only, on the iframe document (same origin, scripts
     * stay sandboxed). The preview fits the viewer width until a button
     * moves the zoom by one step; the middle button goes back to the fit.
     */
    setZoom(direction) {
        let zoom = null;
        if (direction) {
            const current = this.state.zoom || this.state.fitZoom;
            const steps = direction > 0 ? ZOOM_STEPS : [...ZOOM_STEPS].reverse();
            zoom = steps.find((step) => (step - current) * direction > 0) ?? steps.at(-1);
        }
        this.state.zoom = zoom;
        this.params.zoom = zoom;
        getViewerParams(this.params);
        this.applyZoom();
    }

    applyZoom() {
        const doc = this.state.format === "html" && this.iframe.el?.contentDocument;
        if (!doc?.body) {
            return;
        }
        const sheetWidth = this.fitSheet(doc.body);
        if (!this.state.zoom) {
            this.state.fitZoom = this.computeFitZoom(doc, sheetWidth);
        }
        doc.body.style.zoom = `${this.state.zoom || this.state.fitZoom}%`;
    }

    /**
     * Narrow the sheet of a new document to the natural width of the report
     * and return it. The report tables are 100% wide around columns sized
     * in mm: laid out at its max-content width, the body gives the natural
     * width. Without it a portrait report stretches up to the landscape
     * sheet of the preview style and fills the viewer, leaving no margin.
     */
    fitSheet(body) {
        if (!body.dataset.sheetWidth) {
            body.style.zoom = "";
            body.style.width = "max-content";
            const width = body.getBoundingClientRect().width;
            body.style.width = "";
            if (width) {
                body.style.maxWidth = `${width}px`;
            }
            body.dataset.sheetWidth = width;
        }
        return Number(body.dataset.sheetWidth);
    }

    /**
     * Zoom making the report sheet as wide as a form sheet would be in the
     * viewer, within the zoom steps.
     */
    computeFitZoom(doc, sheetWidth) {
        if (!sheetWidth) {
            return 100;
        }
        const width =
            Math.min(doc.documentElement.clientWidth, FIT_MAX_WIDTH) - 2 * FIT_PADDING;
        const zoom = Math.floor((width / sheetWidth) * 100);
        return Math.max(ZOOM_STEPS[0], Math.min(ZOOM_STEPS.at(-1), zoom));
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
