/** @odoo-module **/

import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";

/**
 * Base Report Action Handler
 * 
 * This module provides common functionality for custom report action handlers.
 * Specific reporting engine modules should register their own handlers that
 * can use these utilities.
 */

const reportActionRegistry = registry.category("ir.actions.report handlers");

/**
 * Block UI with loading message
 * @param {string} message - Loading message to display
 */
export function blockUI(message = "Generating report...") {
    // TODO: Implement proper UI blocking with spinner
    console.log(`[Report] ${message}`);
}

/**
 * Unblock UI
 */
export function unblockUI() {
    // TODO: Implement proper UI unblocking
    console.log("[Report] UI unblocked");
}

/**
 * Handle download errors
 * @param {Error} error - Error object
 * @param {Object} env - Odoo environment
 */
export function handleDownloadError(error, env) {
    console.error("[Report] Download error:", error);
    
    const notification = env.services.notification;
    notification.add(
        error.message || "Failed to generate report. Please try again.",
        {
            type: "danger",
            title: "Report Error",
        }
    );
}

/**
 * Download report using standard download utility
 * @param {Object} action - Report action object
 * @param {Object} env - Odoo environment
 * @returns {Promise}
 */
export async function downloadReport(action, env) {
    blockUI("Generating report...");
    
    try {
        await download({
            url: action.url || `/report/${action.report_type}/${action.report_name}/${action.context.active_ids.join(',')}`,
            data: action.data || {},
        });
        
        unblockUI();
    } catch (error) {
        unblockUI();
        handleDownloadError(error, env);
        throw error;
    }
}

/**
 * Example handler registration (to be overridden by specific engines)
 * 
 * reportActionRegistry.add("engine_name", async (action, options, env) => {
 *     return downloadReport(action, env);
 * });
 */

console.log("[dub_reporting_base] Report action utilities loaded");
