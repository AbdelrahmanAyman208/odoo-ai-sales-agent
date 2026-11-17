/** @odoo-module **/

import { Component, proxy, signal } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AiFloatingWidget extends Component {
    static template = "sale_ai_agent.AiFloatingWidget";

    messageList = signal.ref();

    setup() {
        this.orm = useService("orm");
        try {
            this.actionService = useService("action");
        } catch (e) {
            this.actionService = null;
        }

        this.state = proxy({
            isOpen: false,
            isMinimized: false,
            messages: [
                {
                    role: "assistant",
                    content: "Hello! I am your AI Operations Assistant. Ask me to plan and execute tasks across Sales, Purchase, Inventory, MRP, Quality, or CRM -- and I will remain right here while you navigate through any Odoo module!",
                }
            ],
            inputValue: "",
            isSending: false,
            statusText: "",
        });
    }

    toggleOpen() {
        this.state.isOpen = !this.state.isOpen;
        if (this.state.isOpen) {
            this.state.isMinimized = false;
            this.scrollToBottom();
        }
    }

    toggleMinimize(ev) {
        if (ev) ev.stopPropagation();
        this.state.isMinimized = !this.state.isMinimized;
    }

    closeChat(ev) {
        if (ev) ev.stopPropagation();
        this.state.isOpen = false;
        this.state.isMinimized = false;
    }

    onInputKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    async sendMessage() {
        const text = (this.state.inputValue || "").trim();
        if (!text || this.state.isSending) return;

        this.state.inputValue = "";
        this.state.isSending = true;
        this.state.statusText = "Thinking & Executing...";

        this.state.messages.push({ role: "user", content: text });
        this.scrollToBottom();

        try {
            const windowMessages = this.state.messages.slice(-6).map(m => ({
                role: m.role,
                content: m.content
            }));

            // Detect current viewed model and ID safely
            let currentModel = null;
            let currentId = null;
            try {
                const currentController = this.actionService && this.actionService.currentController;
                if (currentController && currentController.props) {
                    currentModel = currentController.props.resModel;
                    currentId = currentController.props.resId;
                }
            } catch (err) {
                // Non-blocking fallback
            }

            const response = await this.orm.call("ai.agent.service", "run_agent_turn", [], {
                messages: windowMessages,
                source: "floating_chat",
                model_name: currentModel || null,
                res_id: currentId ? parseInt(currentId, 10) : null,
            });

            const content = response.content || "Done.";
            this.state.messages.push({
                role: "assistant",
                content: content,
            });
        } catch (error) {
            this.state.messages.push({
                role: "assistant",
                content: `Error: ${error.message || "Failed to communicate with agent."}`,
            });
        } finally {
            this.state.isSending = false;
            this.state.statusText = "";
            this.scrollToBottom();
        }
    }

    scrollToBottom() {
        window.requestAnimationFrame(() => {
            const el = this.messageList();
            if (el) {
                el.scrollTop = el.scrollHeight;
            }
        });
    }
}

const aiFloatingSystrayItem = {
    Component: AiFloatingWidget,
};

registry.category("systray").add("sale_ai_agent.floating_widget", aiFloatingSystrayItem, { sequence: 10 });
