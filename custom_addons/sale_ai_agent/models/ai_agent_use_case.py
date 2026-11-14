# -*- coding: utf-8 -*-
"""
Models for Use-Case-Driven Architecture:
ai.agent.use.case and ai.agent.task
"""
from odoo import api, fields, models


class AiAgentUseCase(models.Model):
    _name = 'ai.agent.use.case'
    _description = 'AI Agent Use Case'
    _order = 'id desc'

    name = fields.Char(string='Title', required=True)
    prompt = fields.Text(string='Original Prompt', required=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('planning', 'Planning'),
            ('running', 'Running'),
            ('done', 'Done'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        string='State',
        default='draft',
        required=True,
        index=True,
    )
    progress = fields.Integer(string='Progress %', default=0)
    user_id = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    started_at = fields.Datetime(string='Started At')
    finished_at = fields.Datetime(string='Finished At')
    summary = fields.Text(string='Summary')

    task_ids = fields.One2many('ai.agent.task', 'use_case_id', string='Tasks')
    approval_ids = fields.One2many('ai.agent.approval', 'use_case_id', string='Approvals')


class AiAgentTask(models.Model):
    _name = 'ai.agent.task'
    _description = 'AI Agent Plan Task'
    _order = 'sequence asc, id asc'

    use_case_id = fields.Many2one('ai.agent.use.case', string='Use Case', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    title = fields.Char(string='Task Title', required=True)
    tool_name = fields.Char(string='Tool Name', required=True)
    arguments_json = fields.Text(string='Arguments (JSON)', default='{}')
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('done', 'Done'),
            ('failed', 'Failed'),
            ('skipped', 'Skipped'),
        ],
        string='State',
        default='pending',
        required=True,
        index=True,
    )
    result_summary = fields.Text(string='Result Summary')
    res_model = fields.Char(string='Related Model')
    res_id = fields.Integer(string='Related Record ID')
    error_message = fields.Text(string='Error')
    duration = fields.Float(string='Duration (s)', default=0.0)

    approval_ids = fields.One2many('ai.agent.approval', 'task_id', string='Approvals')

