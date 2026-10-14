/** @odoo-module **/

import {Component, onWillStart, useState, useSubEnv} from "@odoo/owl";
import {browser} from "@web/core/browser/browser";
import {download} from "@web/core/network/download";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {useSetupAction} from "@web/search/action_hook";
import {Layout} from "@web/search/layout";
import {getDefaultConfig} from "@web/views/view";

const PDFJS_VIEWER = "/web/static/lib/pdfjs/web/viewer.html";
const STORAGE_KEY = "dub_reporting_birt.viewer";

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
        });
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
