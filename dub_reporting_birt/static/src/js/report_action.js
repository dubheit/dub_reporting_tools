/** @odoo-module **/

import {download} from "@web/core/network/download";
import {registry} from "@web/core/registry";
import {user} from "@web/core/user";

// Client-side handler for report_type === "birt". Without it the web client
// does not know how to execute a BIRT report action triggered from the
// standard Print menu (it only handles qweb-pdf/html/text natively), so the
// action silently does nothing. This mirrors the Carbone handler: it builds
// the /report/birt/<name>/<docids> URL and streams it through the
// /report/download controller (overridden server-side for BIRT).
registry
    .category("ir.actions.report handlers")
    .add("birt_handler", async function (action, options, env) {
        if (action.report_type !== "birt") {
            return Promise.resolve(false);
        }
        let url = `/report/birt/${action.report_name}`;
        const actionContext = action.context || {};
        if (actionContext.active_ids) {
            url += `/${actionContext.active_ids.join(",")}`;
        }
        env.services.ui.block();
        try {
            // The BIRT /report/download override reads requestcontent[1] as
            // an options dict and pulls options.get('data'); docids travel in
            // the URL. Keep the report_type in the URL ("birt") for routing.
            await download({
                url: "/report/download",
                data: {
                    data: JSON.stringify([url, {data: action.data || {}}]),
                    context: JSON.stringify(user.context),
                },
            });
        } finally {
            env.services.ui.unblock();
        }
        const onClose = options.onClose;
        if (action.close_on_report_download) {
            return env.services.action.doAction(
                {type: "ir.actions.act_window_close"},
                {onClose}
            );
        } else if (onClose) {
            onClose();
        }
        return Promise.resolve(true);
    });
