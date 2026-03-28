/** @odoo-module **/

import {download} from "@web/core/network/download";
import {registry} from "@web/core/registry";
import {user} from "@web/core/user";

registry
    .category("ir.actions.report handlers")
    .add("carbone_handler", async function (action, options, env) {
        if (action.report_type === "carbone") {
            const type = action.report_type;
            let url = `/report/${type}/${action.report_name}`;
            const actionContext = action.context || {};
            if (action.data && JSON.stringify(action.data) !== "{}") {
                const action_options = encodeURIComponent(JSON.stringify(action.data));
                const context = encodeURIComponent(JSON.stringify(actionContext));
                url += `?options=${action_options}&context=${context}`;
            } else {
                if (actionContext.active_ids) {
                    url += `/${actionContext.active_ids.join(",")}`;
                }
                if (type === "carbone") {
                    const context = encodeURIComponent(
                        JSON.stringify(user.context)
                    );
                    url += `?context=${context}`;
                }
            }
            env.services.ui.block();
            try {
                // Check async mode via dedicated endpoint
                let docidsStr = '';
                if (action.data && JSON.stringify(action.data) !== "{}") {
                    // not supported for async starter for now; fallback to download
                } else if (actionContext.active_ids) {
                    docidsStr = actionContext.active_ids.join(",");
                }
                const asyncResp = await fetch("/carbone/start_async", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ reportname: action.report_name, docids: docidsStr }),
                });
                const isJson = asyncResp.headers.get("content-type")?.includes("application/json");
                if (isJson) {
                    const result = await asyncResp.json();
                    if (result.action) {
                        await env.services.action.doAction(result.action);
                        return true;
                    }
                    if (result.sync) {
                        // proceed to normal download
                    } else {
                        // got JSON but not sync => treat as handled
                        return true;
                    }
                }
                if (!asyncResp.ok) {
                    env.services.notification.add("Async start failed", { type: "danger" });
                    return true;
                }
                // Sync mode - trigger normal download
                await download({
                    url: "/report/download",
                    data: {
                        data: JSON.stringify([url, action.report_type]),
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
        }
        return Promise.resolve(false);
    });