/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AiChatPanel extends Component {
    static template = "sale_ai_agent.AiChatPanel";

    setup() {
        this.orm = useService("orm");
        this.rpc = useService("rpc");
        this.messageListRef = useRef("messageList");

        this.state = useState({
            isCapabilitiesOpen: false,
            messages: [],
            inputValue: "",
            isSending: false,
            statusText: "",
        });

        this.capabilities = [];

        onMounted(async () => {
            await this.loadCapabilities();
        });
    }

    async loadCapabilities() {
        try {
            const data = await this.orm.call("ai.sales.tools", "get_tool_definitions", []);
            // Group tools into capabilities domains
            const domains = {
                sales: { name: "sales", label: "Sales / المبيعات", description: "Quotations, orders & pricing", examples: ["Create quotation for Azure Interior for 2 Desks", "Check quotation details S00015"] },
                purchase: { name: "purchase", label: "Purchase / المشتريات", description: "RFQs, supplier offers & procurement", examples: ["Create RFQ for Apex Supplies for 10 Tops", "Compare vendor offers for Desk Pro"] },
                inventory: { name: "inventory", label: "Inventory / المخازن", description: "Live stock on hand, replenishment & routes", examples: ["How many units of Chair do we have in stock?", "Check low stock items and replenish"] },
                mrp: { name: "mrp", label: "Manufacturing / التصنيع", description: "Bills of materials & manufacturing orders", examples: ["Create BOM for Desk with 1 Top and 4 Legs", "Create MO for 10 units of Desk"] },
                crm: { name: "crm", label: "CRM / العلاقات", description: "Pipeline health & opportunities", examples: ["What is the status of our sales pipeline?"] },
            };
            this.capabilities = Object.values(domains);
        } catch (e) {
            console.error("Failed loading capabilities", e);
        }
    }

    toggleCapabilities() {
        this.state.isCapabilitiesOpen = !this.state.isCapabilitiesOpen;
    }

    setInputText(text) {
        this.state.inputValue = text;
    }

    onInputKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    async sendMessage() {
        const text = this.state.inputValue.trim();
        if (!text || this.state.isSending) return;

        this.state.inputValue = "";
        this.state.isSending = true;
        this.state.statusText = "Processing request...";

        // Append user turn to sliding client window O(k)
        this.state.messages.push({ role: "user", content: text });
        this.scrollToBottom();

        try {
            // Keep sliding window of last 6 turns
            const windowMessages = this.state.messages.slice(-6);

            const response = await this.orm.call("ai.agent.service", "run_agent_turn", [], {
                messages: windowMessages,
                source: "chat_panel",
            });

            const content = response.content || "Completed.";
            const executedTools = response.executed_tools || [];

            // Detect any pending T2 approval
            const t2Approval = executedTools.find(
                (t) => t.result && t.result.approval_required
            );

            this.state.messages.push({
                role: "assistant",
                content: content,
                approval: t2Approval ? t2Approval.result : null,
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
            if (this.messageListRef.el) {
                this.messageListRef.el.scrollTop = this.messageListRef.el.scrollHeight;
            }
        });
    }
}

registry.category("actions").add("sale_ai_agent.chat_action", AiChatPanel);

