/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { loadJS } from "@web/core/assets";

class CarboneStudioAction extends Component {
    static template = "dub_reporting_carbone.CarboneStudioAction";
    static props = {
        action: Object,
        actionId: { type: [Number, Boolean], optional: true },
        updateActionState: { type: Function, optional: true },
        className: { type: String, optional: true },
        "*": true,
    };

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.containerRef = useRef("studioContainer");

        onMounted(() => {
            this.initStudio();
        });
    }

    async initStudio() {
        const params = this.props.action.params || this.props.action.context || {};
        const templateId = params.template_id;
        const templateExtension = params.template_extension || 'docx';
        const accessToken = params.access_token || '';
        const sampleData = params.sample_data || {};

        if (!templateId) {
            this.notification.add("Session expired. Redirecting to reports...", { type: "warning" });
            setTimeout(() => {
                this.action.doAction({
                    type: 'ir.actions.act_window',
                    res_model: 'ir.actions.report',
                    views: [[false, 'list'], [false, 'form']],
                    target: 'current',
                    domain: [['report_type', '=', 'carbone']],
                });
            }, 1500);
            return;
        }

        if (!accessToken) {
            this.notification.add("Carbone API token not configured.", { type: "danger" });
            setTimeout(() => this.action.doAction({ type: "ir.actions.act_window_close" }), 2000);
            return;
        }

        await this.loadStudioScript();

        const container = this.containerRef.el;
        if (!container) return;

        const existingStudio = document.querySelector('carbone-studio');
        if (existingStudio) existingStudio.remove();

        await new Promise(resolve => setTimeout(resolve, 100));

        const studio = document.createElement('carbone-studio');
        studio.style.width = '100%';
        studio.style.height = 'calc(100vh - 60px)';
        studio.style.display = 'block';
        container.appendChild(studio);

        studio.setConfig({ token: accessToken });

        const templateFile = { templateId, extension: templateExtension };
        const options = {
            data: sampleData,
            complement: {},
            enum: {},
            translations: {},
            lang: 'it-it',
            timezone: 'Europe/Rome',
            currencySource: 'EUR',
            currencyTarget: null,
        };

        studio.addEventListener('connected', () => console.log('Carbone Studio: Connected'));
        studio.addEventListener('disconnected', () => console.log('Carbone Studio: Disconnected'));

        studio.addEventListener('template:loaded', () => {
            setTimeout(() => {
                if (studio.renderPreview) studio.renderPreview();
            }, 300);
        });

        studio.addEventListener('template:updated', async (e) => {
            const dataURI = e.detail?.dataURI;
            if (!dataURI || !params.report_id) return;

            try {
                this.notification.add("Saving template to Odoo...", { type: "info" });
                await rpc('/web/dataset/call_kw/ir.actions.report/action_save_template_from_studio', {
                    model: 'ir.actions.report',
                    method: 'action_save_template_from_studio',
                    args: [[params.report_id], dataURI, templateExtension],
                    kwargs: {},
                });
                this.notification.add("Template saved to Odoo!", { type: "success" });
            } catch (err) {
                this.notification.add("Failed to save: " + err.message, { type: "danger" });
            }
        });

        await new Promise(resolve => setTimeout(resolve, 500));
        studio.openTemplate(templateFile, options);

        let attempts = 0;
        const pollInterval = setInterval(() => {
            attempts++;
            if (studio.renderPreview && typeof studio.renderPreview === 'function') {
                clearInterval(pollInterval);
                studio.renderPreview();
            } else if (attempts >= 20) {
                clearInterval(pollInterval);
            }
        }, 500);
    }

    async loadStudioScript() {
        if (window.customElements && window.customElements.get('carbone-studio')) {
            return;
        }

        const res = await rpc("/carbone_config/studio_params");
        if (!res.js_url) {
            this.notification.add("Carbone Studio JS URL not configured in Settings.", { type: "danger" });
            throw new Error("Missing Studio JS URL");
        }

        await loadJS(res.js_url);
        if (window.customElements) {
            await window.customElements.whenDefined('carbone-studio');
        }
    }

    onClose() {
        const params = this.props.action.params || {};
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'ir.actions.report',
            res_id: params.report_id,
            views: [[false, 'form']],
            target: 'current',
        });
    }
}

registry.category("actions").add("carbone_studio_editor", CarboneStudioAction);
