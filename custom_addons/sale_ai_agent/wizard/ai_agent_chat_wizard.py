import html
import json
from odoo import api, fields, models


class AiAgentChat(models.TransientModel):
    _name = 'ai.agent.chat'
    _description = 'AI Agent Chat Assistant'

    user_message = fields.Text(string='Message')
    history_json = fields.Text(string='History Data', default='[]')
    chat_html = fields.Html(string='Chat History', compute='_compute_chat_html', readonly=True)
    last_order_id = fields.Many2one('sale.order', string='Latest Generated Quotation')
    last_po_id = fields.Many2one('purchase.order', string='Latest Generated Purchase Order')
    last_product_id = fields.Many2one('product.template', string='Latest Created Product')

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
                    '<h4 style="font-weight: 600; color: #343a40;">AI Agent Ready</h4>'
                    '<p style="max-width: 540px; margin: 0 auto; font-size: 14px; line-height: 1.6;">'
                    'I can create sales quotes, purchase orders (RFQs), broadcast quote requests to all suppliers, analyze offers to find the best deal, and build composite products with bill of materials.'
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
                    # Parse simple markdown headings / bold / bullets
                    formatted_content = html.escape(content).replace("\n", "<br/>")
                    formatted_content = formatted_content.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
                    # simple bold replace
                    import re
                    formatted_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted_content)

                    tool_badges = ""
                    if tools:
                        badges_list = []
                        for t in tools:
                            t_name = t.get('tool')
                            badges_list.append(f'<span style="display: inline-block; background: #e3f2fd; color: #0d47a1; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px; margin-right: 4px;">⚡ Tool: {html.escape(t_name)}</span>')
                        tool_badges = f'<div style="margin-bottom: 8px;">{"".join(badges_list)}</div>'

                    html_parts.append(
                        '<div style="align-self: flex-start; max-width: 85%; background: #ffffff; color: #212529; padding: 12px 16px; border-radius: 16px 16px 16px 4px; border: 1px solid #dee2e6; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">'
                        '<div style="font-weight: 600; font-size: 11px; color: #6c757d; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">'
                        '<span style="background: #28a745; width: 8px; height: 8px; border-radius: 50%; display: inline-block;"></span> Sales AI Agent'
                        '</div>'
                        f'{tool_badges}'
                        f'<div style="font-size: 14px; line-height: 1.5;">{formatted_content}</div>'
                        '</div>'
                    )

            html_parts.append('</div>')
            rec.chat_html = "".join(html_parts)

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

        # Run agent loop
        Service = self.env['ai.agent.service']
        cfg = Service._get_config()

        messages_for_llm = [{"role": "system", "content": cfg['system_prompt']}]
        for h in history:
            messages_for_llm.append({"role": h['role'], "content": h['content']})

        result = Service.run_agent_turn(messages_for_llm, source='chat_agent')

        executed_tools = result.get('executed_tools', [])
        response_text = result.get('content', '')

        # Check if an order, PO, or product was created in this turn
        for et in executed_tools:
            res_dict = et.get('result', {})
            if isinstance(res_dict, dict):
                if res_dict.get('order_id'):
                    self.last_order_id = res_dict.get('order_id')
                if res_dict.get('po_id'):
                    self.last_po_id = res_dict.get('po_id')
                if res_dict.get('product_tmpl_id'):
                    self.last_product_id = res_dict.get('product_tmpl_id')

        # Append assistant message to local history
        history.append({
            "role": "assistant",
            "content": response_text,
            "tools_called": executed_tools,
        })

        self.write({
            'history_json': json.dumps(history),
            'user_message': False,
        })

        return self._reload_view()

    def action_quick_pipeline(self):
        self.user_message = "Summarize the CRM sales pipeline with stages and top opportunities."
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

    def action_quick_tracking(self):
        self.user_message = "Enable lot tracking on product 4 steel legs with reorder safety stock rules."
        return self.action_send_message()

    def action_quick_create_tracked_product(self):
        self.user_message = "Create product Ergonomic Standing Desk Pro with sales price $450 and enable Track Inventory."
        return self.action_send_message()

    def action_quick_end_to_end_usecase(self):
        self.user_message = "Execute complete End-to-End Use Case: Create composite desk, sales quotation for Azure Interior, and supplier purchase order with RFQ analysis."
        return self.action_send_message()

    def action_view_order(self):
        self.ensure_one()
        if not self.last_order_id:
            raise models.UserError("No recent quotation has been created in this session.")
        return {
            'name': self.last_order_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.last_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_po(self):
        self.ensure_one()
        if not self.last_po_id:
            raise models.UserError("No recent purchase order has been created in this session.")
        return {
            'name': self.last_po_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.last_po_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_product(self):
        self.ensure_one()
        if not self.last_product_id:
            raise models.UserError("No recent product has been created in this session.")
        return {
            'name': self.last_product_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': self.last_product_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_reset_chat(self):
        self.write({
            'history_json': '[]',
            'user_message': False,
            'last_order_id': False,
            'last_po_id': False,
            'last_product_id': False,
        })
        return self._reload_view()

    def _reload_view(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ai.agent.chat',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
