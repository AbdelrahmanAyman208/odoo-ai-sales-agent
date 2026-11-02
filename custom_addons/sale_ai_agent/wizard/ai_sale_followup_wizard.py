import html
import re
from odoo import api, fields, models


class AiSaleFollowupWizard(models.TransientModel):
    _name = 'ai.sale.followup.wizard'
    _description = 'AI Follow-up Email Wizard'

    order_id = fields.Many2one('sale.order', string='Sale Order / Quotation')
    lead_id = fields.Many2one('crm.lead', string='CRM Opportunity')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    tone = fields.Selection(
        selection=[
            ('professional', 'Professional & Direct'),
            ('friendly', 'Warm & Casual'),
            ('urgent', 'Gentle Urgency (Expiry / Inventory)'),
            ('value_driven', 'Value & ROI Focused'),
        ],
        string='Tone of Voice',
        default='professional',
        required=True,
    )
    custom_instructions = fields.Text(
        string='Custom Instructions',
    )
    email_subject = fields.Char(string='Subject', default='Following up on our quotation')
    email_body = fields.Html(string='Email Body', default='<p>Drafting follow-up email...</p>')

    def action_generate_draft(self):
        self.ensure_one()
        Service = self.env['ai.agent.service']

        # Construct contextual prompt
        customer_name = self.partner_id.name or 'Valued Customer'
        user_name = self.env.user.name or 'Sales Team'

        context_info = []
        if self.order_id:
            context_info.append(f"Quotation/Order Reference: {self.order_id.name}")
            context_info.append(f"Order Total: {self.order_id.amount_total} {self.order_id.currency_id.name}")
            context_info.append(f"Order Date: {self.order_id.date_order}")
            lines = [f"- {l.product_id.display_name} (Qty: {l.product_uom_qty}, Price: {l.price_unit})" for l in self.order_id.order_line]
            if lines:
                context_info.append("Products Ordered:\n" + "\n".join(lines))

        if self.lead_id:
            context_info.append(f"Opportunity: {self.lead_id.name}")
            context_info.append(f"Expected Revenue: {self.lead_id.expected_revenue}")
            context_info.append(f"Stage: {self.lead_id.stage_id.name if self.lead_id.stage_id else 'New'}")

        instructions_text = f"Custom Instructions: {self.custom_instructions}" if self.custom_instructions else ""

        prompt = (
            f"Draft a sales follow-up email to customer '{customer_name}' from sales rep '{user_name}'.\n"
            f"Tone: {self.tone}.\n"
            f"{instructions_text}\n"
            f"Context:\n" + "\n".join(context_info) + "\n\n"
            "Format the email with a clear, compelling subject line and an engaging, well-spaced HTML body. "
            "Write ONLY the email body in HTML format (using <p>, <ul>, <li>, <strong> tags) with no markdown ticks."
        )

        messages = [
            {"role": "system", "content": "You are a top-performing B2B sales copywriter who writes concise, high-converting follow-up emails."},
            {"role": "user", "content": prompt},
        ]

        # Call LLM
        res = Service.call_llm_raw(messages)
        content = res.get('content', '')

        # Extract subject and body
        subject = f"Following up on {self.order_id.name if self.order_id else self.lead_id.name or 'our discussion'}"
        body_html = ""

        # Parse subject line if model outputted "Subject: ..."
        subject_match = re.search(r'(?:Subject|SUBJECT):\s*(.*?)(?:\n|<br|\r)', content)
        if subject_match:
            subject = subject_match.group(1).strip()
            # Remove subject from body
            content = content.replace(subject_match.group(0), "")

        # Clean markdown or HTML wraps
        content = content.replace("```html", "").replace("```", "").strip()
        if not content.startswith("<"):
            # Format plain text to HTML paragraphs
            paragraphs = [f"<p>{html.escape(p.strip())}</p>" for p in content.split("\n\n") if p.strip()]
            body_html = "".join(paragraphs)
        else:
            body_html = content

        self.write({
            'email_subject': subject,
            'email_body': body_html,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ai.sale.followup.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_send_email(self):
        self.ensure_one()
        target_record = self.order_id or self.lead_id

        if not target_record:
            raise models.UserError("No related quotation or lead found to send email.")

        # Post message to chatter and send to partner
        msg = target_record.message_post(
            body=self.email_body,
            subject=self.email_subject,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.partner_id.id],
        )

        # Log action
        self.env['ai.agent.log'].sudo().create({
            'name': f"Follow-up Email Sent: {self.email_subject}",
            'user_id': self.env.user.id,
            'source': 'followup_wizard',
            'model_name': target_record._name,
            'res_id': target_record.id,
            'prompt': f"Tone: {self.tone}; Instructions: {self.custom_instructions}",
            'response': f"Subject: {self.email_subject}\n\n{self.email_body}",
            'status': 'success',
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Email Sent Successfully!',
                'message': f"Follow-up email has been posted to {target_record.display_name} chatter and sent to {self.partner_id.name}.",
                'type': 'success',
                'sticky': False,
            },
        }
