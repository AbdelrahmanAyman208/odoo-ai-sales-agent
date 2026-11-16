# -*- coding: utf-8 -*-
"""
AI Agent Chat Wizard (Phase 13, Global Decisions 7 & 8).
Features:
- Local capabilities question interceptor (zero LLM token consumption).
- Modern clean chat UI without bulky persistent panels.
- Collapsible Capabilities modal / helper.
- Inline T2 approval routing cards.
- Transient conversational state.

Complexity:
- Time: O(H) where H is history length.
- Space: O(H) transient state.
"""
import html
import json
import re
from odoo import api, fields, models
from ..tools.base import get_capabilities_panel_data
from ..services.capabilities import get_system_capabilities


class AiAgentChat(models.TransientModel):
    _name = 'ai.agent.chat'
    _description = 'AI Agent Chat Assistant'

    user_message = fields.Text(string='Message')
    history_json = fields.Text(string='History Data', default='[]')
    chat_html = fields.Html(string='Chat History', compute='_compute_chat_html', readonly=True)
    last_order_id = fields.Many2one('sale.order', string='Latest Generated Quotation')
    last_po_id = fields.Many2one('purchase.order', string='Latest Generated Purchase Order')
    last_product_id = fields.Many2one('product.template', string='Latest Created Product')
    last_approval_id = fields.Many2one('ai.agent.approval', string='Latest Pending Approval')

    @api.depends('history_json')
    def _compute_chat_html(self):
        for rec in self:
            history = []
            if rec.history_json:
                try:
                    history = json.loads(rec.history_json)
                except Exception:
                    history = []

            html_parts = [
                '<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; display: flex; flex-direction: column; gap: 14px; max-height: 480px; overflow-y: auto; padding: 12px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e9ecef;">'
            ]

            if not history:
                html_parts.append(
                    '<div style="text-align: center; color: #6c757d; padding: 30px 10px;">'
                    '<div style="font-size: 32px; margin-bottom: 8px;">🤖</div>'
                    '<h4 style="font-weight: 600; color: #343a40;">AI Operations Agent Ready</h4>'
                    '<p style="max-width: 540px; margin: 0 auto; font-size: 14px; line-height: 1.6;">'
                    'I am your Junior Odoo Implementer across Sales, Purchase, Inventory, Manufacturing, CRM, Projects, and Loyalty. '
                    'How can I help you streamline operations today?'
                    '</p>'
                    '</div>'
                )

            for msg in history:
                role = msg.get('role')
                content = msg.get('content', '')
                tools = msg.get('tools_called', [])

                if role == 'user':
                    html_parts.append(
                        '<div style="align-self: flex-end; max-width: 80%; background: #007bff; color: #fff; padding: 10px 14px; border-radius: 16px 16px 4px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">'
                        f'<div style="font-weight: 600; font-size: 11px; margin-bottom: 3px; opacity: 0.85;">You</div>'
                        f'<div style="font-size: 14px; white-space: pre-wrap; line-height: 1.4;">{html.escape(content)}</div>'
                        '</div>'
                    )
                elif role == 'assistant':
                    formatted_content = self._format_markdown_html(content)

                    tool_badges = ""
                    approval_card_html = ""
                    if tools:
                        badges_list = []
                        for t in tools:
                            t_name = t.get('tool')
                            t_result = t.get('result', {})
                            status_icon = "✅" if t_result.get('success') else "❌"
                            badges_list.append(
                                f'<span style="display: inline-block; background: #e3f2fd; color: #0d47a1; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px; margin-right: 4px;">'
                                f'{status_icon} {html.escape(t_name)}'
                                f'</span>'
                            )
                            # Inline approval card for T2 interceptions
                            if t_result.get('approval_required') and t_result.get('approval_id'):
                                a_id = t_result['approval_id']
                                a_name = html.escape(str(t_result.get('approval_name', '')))
                                a_msg = html.escape(str(t_result.get('message', '')))
                                a_total = t_result.get('total_amount', 0)
                                a_curr = html.escape(str(t_result.get('currency', '')))
                                approval_card_html += (
                                    '<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 10px 14px; margin-top: 8px;">'
                                    '<div style="font-weight: 700; font-size: 13px; color: #856404; margin-bottom: 4px;">'
                                    '<span style="margin-right: 4px;">🛡️</span> Human Approval Required (T2)</div>'
                                    f'<div style="font-size: 12px; color: #856404; margin-bottom: 6px;">{a_msg}</div>'
                                    f'<div style="font-size: 12px; color: #664d03;"><strong>Approval:</strong> {a_name} &bull; '
                                    f'<strong>Total:</strong> {a_curr} {a_total:,.2f}</div>'
                                    f'<div style="margin-top: 8px;">'
                                    f'<a href="/web#id={a_id}&model=ai.agent.approval&view_type=form" '
                                    f'target="_blank" style="display: inline-block; background: #e2a403; color: #fff; '
                                    f'text-decoration: none; padding: 4px 10px; border-radius: 4px; font-weight: 600; font-size: 12px;">'
                                    f'Review &amp; Confirm &rarr;</a>'
                                    f'</div>'
                                    '</div>'
                                )

                        if badges_list:
                            tool_badges = (
                                '<div style="margin-bottom: 6px; display: flex; flex-wrap: wrap; gap: 4px;">'
                                + "".join(badges_list) +
                                '</div>'
                            )

                    html_parts.append(
                        '<div style="align-self: flex-start; max-width: 85%; background: #ffffff; color: #212529; padding: 12px 16px; border-radius: 16px 16px 16px 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid #e9ecef;">'
                        '<div style="font-weight: 600; font-size: 11px; margin-bottom: 4px; color: #6c757d;">AI Agent</div>'
                        f'{tool_badges}'
                        f'<div style="font-size: 14px; line-height: 1.5;">{formatted_content}</div>'
                        f'{approval_card_html}'
                        '</div>'
                    )

            html_parts.append('</div>')
            rec.chat_html = "".join(html_parts)

    def _format_markdown_html(self, text: str) -> str:
        if not text:
            return ""
        escaped = html.escape(text)
        escaped = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', escaped)
        escaped = re.sub(r'\*(.*?)\*', r'<em>\1</em>', escaped)
        escaped = re.sub(r'`(.*?)`', r'<code style="background: #f1f3f5; padding: 2px 4px; border-radius: 4px; font-size: 12px;">\1</code>', escaped)
        escaped = re.sub(r'^\s*[-*]\s+(.*)$', r'&bull; \1<br/>', escaped, flags=re.MULTILINE)
        escaped = escaped.replace('\n', '<br/>')
        return escaped

    # ── Local Zero-Token Capabilities Handler (Phase 13) ───────────────────

    def _handle_local_capabilities_query(self, user_msg: str):
        """
        Detects generic 'who are you' / 'what can you do' queries and responds locally
        from tool registry metadata with ZERO LLM API tokens consumed.
        """
        clean = (user_msg or '').strip().lower()
        patterns = [
            "who are you", "what can you do", "help", "capabilities", "what do you do",
            "من انت", "من أنت", "ماذا تستطيع", "ماذا تفعل", "مساعدة", "قدرات"
        ]
        if not any(p in clean for p in patterns) or len(clean) > 50:
            return None

        # Build response from registry & system capabilities
        caps = get_system_capabilities(self.env)
        panel = get_capabilities_panel_data(self.env)

        is_arabic = any(ord(c) >= 0x0600 and ord(c) <= 0x06FF for c in user_msg)

        if is_arabic:
            response = (
                f"**أنا مساعد العمليات والذكاء الاصطناعي في أودو 20 ({caps['edition']} Edition).**\n\n"
                f"أعمل كمنفذ متكامل للمهام عبر كافة الأقسام:\n"
            )
            for d_key, d_info in panel.items():
                response += f"- **{d_info['label']}**: {d_info['description']}\n"
            response += "\n*يمكنك كتابة طلبك باللغة الطبيعية أو استخدام الأزرار السريعة بالأعلى.*"
        else:
            response = (
                f"**I am your AI Operations Agent in Odoo 20 ({caps['edition']} Edition).**\n\n"
                f"I act as your autonomous Junior Odoo Implementer across all key business domains:\n"
            )
            for d_key, d_info in panel.items():
                response += f"- **{d_info['label']}**: {d_info['description']}\n"
            response += "\n*Simply describe what you want to achieve or click any quick action above.*"

        return response

    # ── Chat execution flow ──────────────────────────────────────────────

    def action_send_message(self):
        self.ensure_one()
        msg_text = (self.user_message or '').strip()
        if not msg_text:
            return self._reload_view()

        history = []
        if self.history_json:
            try:
                history = json.loads(self.history_json)
            except Exception:
                history = []

        # Add user message to history
        history.append({
            "role": "user",
            "content": msg_text,
        })

        # Local Zero-Token capabilities check (Phase 13)
        local_reply = self._handle_local_capabilities_query(msg_text)
        if local_reply:
            history.append({
                "role": "assistant",
                "content": local_reply,
                "tools_called": [],
            })
            self.write({
                'history_json': json.dumps(history, default=str),
                'user_message': False,
            })
            return self._reload_view()

        # Build messages for LLM — system prompt is handled inside run_agent_turn
        messages_for_llm = []
        for h in history:
            if h.get('role') in ('user', 'assistant'):
                messages_for_llm.append({"role": h['role'], "content": h['content']})

        # Sliding window: keep last 20 messages max
        if len(messages_for_llm) > 20:
            messages_for_llm = messages_for_llm[-20:]

        Service = self.env['ai.agent.service']
        result = Service.run_agent_turn(messages_for_llm, source='chat_agent')

        executed_tools = result.get('executed_tools', [])
        response_text = result.get('content', '')

        # Track created records from tool results
        for et in executed_tools:
            res_dict = et.get('result', {})
            if isinstance(res_dict, dict):
                if res_dict.get('order_id') and res_dict.get('order_name', '').startswith('S'):
                    self.last_order_id = res_dict['order_id']
                elif res_dict.get('po_id'):
                    self.last_po_id = res_dict['po_id']
                if res_dict.get('product_tmpl_id'):
                    self.last_product_id = res_dict['product_tmpl_id']
                if res_dict.get('approval_id'):
                    self.last_approval_id = res_dict['approval_id']

        # Append assistant message to local history
        history.append({
            "role": "assistant",
            "content": response_text,
            "tools_called": executed_tools,
        })

        self.write({
            'history_json': json.dumps(history, default=str),
            'user_message': False,
        })

        return self._reload_view()

    # ── Quick actions ──────────────────────────────────────────────

    def action_quick_pipeline(self):
        self.user_message = "Summarize the CRM sales pipeline with stages, expected revenue, and win rate."
        return self.action_send_message()

    def action_quick_quote(self):
        self.user_message = "Create a draft quotation for Azure Interior for 2 Desks and 4 Chairs."
        return self.action_send_message()

    def action_quick_send_rfq(self):
        self.user_message = "Send price quotation request for Desk to all suppliers."
        return self.action_send_message()

    def action_quick_analyze_offers(self):
        self.user_message = "Analyze supplier offers for Desk and show the analyzed form with the best offer."
        return self.action_send_message()

    def action_quick_composite_desk(self):
        self.user_message = "Create product Executive Desk that consists of Table Top, 4 Steel Legs, and Hardware Fasteners Kit."
        return self.action_send_message()

    def action_quick_replenishment(self):
        self.user_message = "Scan inventory for products below safety stock and execute automated replenishment orders for low-stock items."
        return self.action_send_message()

    def action_quick_crm_lead_gen(self):
        self.user_message = "Create a new CRM lead for TechCorp, contact Sarah Jenkins (sarah@techcorp.com), expected revenue $45,000."
        return self.action_send_message()

    def action_quick_loyalty_promo(self):
        self.user_message = "Create a 15% promotional discount program for Summer Clearance with minimum order $100."
        return self.action_send_message()

    def action_quick_project_task(self):
        self.user_message = "Create a project 'Office Renovation' and add a task 'Design Layout' with deadline next week."
        return self.action_send_message()

    def action_quick_end_to_end_usecase(self):
        self.user_message = (
            "Execute complete end-to-end use case: "
            "1. Check system configuration, "
            "2. Create BOM for Executive Conference Desk (1 Oak Table Top + 4 Heavy Duty Steel Legs), "
            "3. Create sales quotation for Deco Addict for 20 desks with 5% discount, "
            "4. Check stock availability across locations, "
            "5. Compare vendor offers for components, "
            "6. Create RFQ for cheapest vendor, "
            "7. Create manufacturing order for 20 desks, "
            "8. Initiate T2 confirmation for the quotation and RFQ."
        )
        return self.action_send_message()

    def action_reset_chat(self):
        self.ensure_one()
        self.write({
            'history_json': '[]',
            'user_message': False,
            'last_order_id': False,
            'last_po_id': False,
            'last_product_id': False,
            'last_approval_id': False,
        })
        return self._reload_view()

    # ── Record navigation ──────────────────────────────────────────────

    def action_view_order(self):
        self.ensure_one()
        if not self.last_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': 'Draft Quotation',
            'res_model': 'sale.order',
            'res_id': self.last_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_po(self):
        self.ensure_one()
        if not self.last_po_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Order / RFQ',
            'res_model': 'purchase.order',
            'res_id': self.last_po_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_product(self):
        self.ensure_one()
        if not self.last_product_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': 'Product',
            'res_model': 'product.template',
            'res_id': self.last_product_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_approval(self):
        self.ensure_one()
        if not self.last_approval_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pending Approval',
            'res_model': 'ai.agent.approval',
            'res_id': self.last_approval_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_approval_target(self):
        self.ensure_one()
        if not self.last_approval_id:
            return
        return self.last_approval_id.action_open_target_record()

    def _reload_view(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'AI Operations Assistant',
            'res_model': 'ai.agent.chat',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
