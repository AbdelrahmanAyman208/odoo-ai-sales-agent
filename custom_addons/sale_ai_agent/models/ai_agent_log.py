from odoo import fields, models


class AiAgentLog(models.Model):
    _name = 'ai.agent.log'
    _description = 'AI Agent Action Log'
    _order = 'create_date desc'

    name = fields.Char(string='Action Summary', required=True)
    user_id = fields.Many2one('res.users', string='Triggered By', default=lambda self: self.env.user, required=True)
    source = fields.Selection(
        selection=[
            ('followup_wizard', 'Quotation / Lead Follow-up Wizard'),
            ('chat_agent', 'Sales AI Chat Assistant'),
            ('tool_execution', 'Direct Tool Invocation'),
        ],
        string='Source',
        default='chat_agent',
        required=True,
    )
    model_name = fields.Char(string='Related Model')
    res_id = fields.Integer(string='Related Record ID')
    prompt = fields.Text(string='Input Prompt / Query')
    response = fields.Text(string='AI Response')
    tools_called = fields.Text(string='Tools Called (JSON/Details)')
    status = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('warning', 'Warning / Partial'),
            ('error', 'Error'),
        ],
        string='Status',
        default='success',
    )
    execution_time = fields.Float(string='Execution Time (s)')
    error_message = fields.Text(string='Error Details')
