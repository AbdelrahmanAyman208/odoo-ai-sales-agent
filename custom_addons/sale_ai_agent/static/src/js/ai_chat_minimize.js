/** @odoo-module **/

/**
 * AI Operations Agent - Chatbot Minimize / Hide Bar Engine.
 * Allows users to minimize the AI chat wizard into a floating dock bar at any time
 * so they can freely interact with Odoo (Sales, Purchases, Inventory, MRP)
 * without losing chat history or having to close and re-open the wizard.
 */

function setupAiChatMinimize() {
    // Check if dialog is the AI Agent chat dialog
    function isAiChatDialog(dialogEl) {
        if (!dialogEl) return false;
        const titleEl = dialogEl.querySelector(".modal-title");
        const title = titleEl ? titleEl.textContent.trim().toLowerCase() : "";
        if (title.includes("ai agent") || title.includes("ai assistant") || title.includes("sales ai agent")) {
            return true;
        }
        if (dialogEl.querySelector("form[string='AI Assistant']") || dialogEl.querySelector(".o_ai_chat_container") || dialogEl.querySelector("[name='chat_html']")) {
            return true;
        }
        return false;
    }

    // Toggle minimize/restore
    function toggleMinimize(dialogEl, minimize) {
        if (!dialogEl) return;
        const isCurrentlyMinimized = dialogEl.classList.contains("o_ai_dialog_minimized");
        const shouldMinimize = typeof minimize === "boolean" ? minimize : !isCurrentlyMinimized;

        let dock = dialogEl.querySelector(".o_ai_minimized_dock");

        if (shouldMinimize) {
            dialogEl.classList.add("o_ai_dialog_minimized");

            // Create floating dock bar if not exists
            if (!dock) {
                dock = document.createElement("div");
                dock.className = "o_ai_minimized_dock";
                dock.innerHTML = `
                    <span class="o_ai_pulse_dot" title="AI Agent Active"></span>
                    <span class="o_ai_dock_title">🤖 AI Agent</span>
                    <span class="badge bg-primary text-white rounded-pill px-2 py-0" style="font-size: 10px;">Active</span>
                    <button type="button" class="o_ai_dock_btn o_ai_dock_btn_restore ms-1" title="Restore / Expand Chat">
                        <i class="fa fa-window-restore"></i>
                    </button>
                    <button type="button" class="o_ai_dock_btn o_ai_dock_btn_close" title="Close Chat">
                        <i class="fa fa-times"></i>
                    </button>
                `;

                dock.addEventListener("click", (e) => {
                    if (e.target.closest(".o_ai_dock_btn_close")) {
                        e.stopPropagation();
                        // Trigger standard close
                        toggleMinimize(dialogEl, false);
                        const closeBtn = dialogEl.querySelector(".modal-header .btn-close, .modal-footer button[special='cancel']");
                        if (closeBtn) closeBtn.click();
                        return;
                    }
                    // Restore chat on dock click or restore button click
                    toggleMinimize(dialogEl, false);
                });

                const modalContent = dialogEl.querySelector(".modal-content") || dialogEl.querySelector(".modal");
                if (modalContent) {
                    modalContent.appendChild(dock);
                }
            } else {
                dock.style.display = "flex";
            }
        } else {
            dialogEl.classList.remove("o_ai_dialog_minimized");
            if (dock) {
                dock.style.display = "none";
            }
            // Auto focus chat input
            setTimeout(() => {
                const input = dialogEl.querySelector("textarea[name='user_message'], input[name='user_message']");
                if (input) input.focus();
            }, 100);
        }
    }

    // Inject minimize button into modal header
    function injectMinimizeButton(dialogEl) {
        if (!dialogEl || dialogEl.dataset.aiMinimizeInjected === "true") return;

        const header = dialogEl.querySelector(".modal-header");
        const closeBtn = header ? header.querySelector(".btn-close") : null;
        if (!header || !closeBtn) return;

        dialogEl.dataset.aiMinimizeInjected = "true";

        const minBtn = document.createElement("button");
        minBtn.type = "button";
        minBtn.className = "o_ai_chat_minimize_btn";
        minBtn.title = "Hide / Minimize Chat (—)";
        minBtn.setAttribute("aria-label", "Minimize");
        minBtn.innerHTML = '<span class="o_ai_dash_icon"></span>';

        minBtn.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleMinimize(dialogEl, true);
        });

        header.insertBefore(minBtn, closeBtn);

        // Also bind any in-form hide buttons (.o_ai_chat_hide_btn)
        const inFormHideBtns = dialogEl.querySelectorAll(".o_ai_chat_hide_btn");
        inFormHideBtns.forEach((btn) => {
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                toggleMinimize(dialogEl, true);
            });
        });
    }

    // Observer to automatically detect when AI Chat modal is added to DOM
    const observer = new MutationObserver(() => {
        const dialogs = document.querySelectorAll(".o_dialog");
        dialogs.forEach((d) => {
            if (isAiChatDialog(d)) {
                injectMinimizeButton(d);
            }
        });
    });

    observer.observe(document.body, { childList: true, subtree: true });
}

// Initialize when web client assets are loaded
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupAiChatMinimize);
} else {
    setupAiChatMinimize();
}

