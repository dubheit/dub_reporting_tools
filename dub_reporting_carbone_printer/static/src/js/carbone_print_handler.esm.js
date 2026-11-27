/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import {markup} from "@odoo/owl";
import {escape} from "@web/core/utils/strings";
import {registry} from "@web/core/registry";

function notifyPrinterIssue(env, action, printerName) {
    // Declared up front so the translation engine detects them.
    const terms = {
        the_report: _t("The report"),
        couldnt_be_printed: _t(
            "couldn't be printed. Click on the button below to download it"
        ),
        issue_on: _t("Issue on"),
    };
    const notificationRemove = env.services.notification.add(
        markup(
            `<p>${terms.the_report} <strong>${escape(action.name)}</strong> ${terms.couldnt_be_printed}</p>`
        ),
        {
            title: `${terms.issue_on} ${printerName}`,
            type: "warning",
            sticky: true,
            buttons: [
                {
                    name: _t("Print"),
                    primary: true,
                    icon: "fa-print",
                    onClick: async () => {
                        await env.services.action.doAction(
                            {type: "ir.actions.report", ...action},
                            {
                                additionalContext: {
                                    force_print_to_client: true,
                                    must_skip_send_to_printer: true,
                                },
                            }
                        );
                        notificationRemove();
                    },
                },
            ],
        }
    );
}

/**
 * Send Carbone reports to the printer when the print action is "server".
 * Returning true lets the action service close the window itself, so this
 * handler must not close it nor call onClose.
 */
async function carbonePrintHandler(action, options, env) {
    const ctx = action.context || {};
    if (ctx.force_print_to_client) {
        return false;
    }
    const activeIds = ctx.active_ids || [];
    if (action.report_type !== "carbone" || !action.id || !activeIds.length) {
        return false;
    }
    const orm = env.services.orm;
    env.services.ui.block();
    try {
        let printAction;
        try {
            printAction = await orm.call(
                "ir.actions.report",
                "print_action_for_report_name",
                [action.report_name],
                {context: {force_print_to_client: ctx.force_print_to_client}}
            );
        } catch (error) {
            // Cannot tell where to print: let the download handlers take over.
            console.warn("Carbone print: cannot resolve the print action", error);
            return false;
        }
        if (!printAction || printAction.action !== "server") {
            return false;
        }
        if (printAction.printer_exception) {
            notifyPrinterIssue(env, action, printAction.printer_name);
            return true;
        }
        let result = false;
        try {
            result = await orm.call(
                "ir.actions.report",
                "print_document_client_action",
                [action.id, activeIds, action.data]
            );
        } catch (error) {
            console.warn("Carbone print: the print request failed", error);
            result = false;
        }
        if (result && result.download) {
            // Not printable (format, mode, no records): download as usual.
            if (result.message) {
                env.services.notification.add(result.message, {type: "warning"});
            }
            return false;
        }
        if (result) {
            env.services.notification.add(_t("Successfully sent to printer!"), {
                type: "success",
            });
            return true;
        }
        // Same notifications as the CUPS report handler of the printing addon.
        env.services.notification.add(_t("Could not sent to printer!"), {
            type: "danger",
        });
        notifyPrinterIssue(env, action, printAction.printer_name);
        return true;
    } finally {
        env.services.ui.unblock();
    }
}

registry
    .category("ir.actions.report handlers")
    .add("dub_carbone_print_handler", carbonePrintHandler, {sequence: 5});
