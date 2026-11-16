# -*- coding: utf-8 -*-
"""
Models for Learning System (Addendum 5 v2 & Phase 15).
Includes:
- ai.agent.feedback: Explicit/implicit user feedback (thumbs up/down, retries, undo, rejections)
- ai.agent.lesson: Reviewed lessons from structured failure/fix pairs
- ai.agent.example: Verified success use case examples
- ai.agent.profile.entry: Learned company/user defaults (e.g. default warehouse, terms)
"""
import re
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_PII_PATTERNS = [
    re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),  # Email
    re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),  # Phone
    re.compile(r'[$€£]\s*\d+(?:,\d{3})*(?:\.\d{2})?'),  # Amounts with currency
]

def sanitize_lesson_text(text: str) -> str:
    """Rejects lesson text containing PII (emails, phone numbers, explicit amounts)."""
    if not text:
        return ""
    for pat in _PII_PATTERNS:
        if pat.search(text):
            raise ValidationError("Sanitizer rejected lesson text: contains PII (email, phone, or monetary amount).")
    return text.strip()


class AiAgentFeedback(models.Model):
    _name = 'ai.agent.feedback'
    _description = 'AI Agent Feedback'
    _order = 'id desc'

    use_case_id = fields.Many2one('ai.agent.use.case', string='Use Case', ondelete='cascade', index=True)
    task_id = fields.Many2one('ai.agent.task', string='Task', ondelete='cascade', index=True)
    signal = fields.Selection([
        ('thumbs_up', 'Thumbs Up'),
        ('thumbs_down', 'Thumbs Down'),
        ('retry', 'Task Retried'),
        ('undo', 'Undo Requested'),
        ('rejection', 'Approval Rejected'),
        ('correction', 'User Corrected Plan'),
    ], string='Feedback Signal', required=True, index=True)
    reason = fields.Text(string='Reason / Note')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user, required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)


class AiAgentLesson(models.Model):
    _name = 'ai.agent.lesson'
    _description = 'AI Agent Reviewed Lesson'
    _order = 'support_count desc, id desc'

    domain = fields.Char(string='Domain', required=True, index=True)
    trigger = fields.Char(string='Trigger Condition', required=True, index=True)
    guidance = fields.Text(string='Guidance (Imperative)', required=True)
    type = fields.Selection([
        ('spec_fix', 'Specification Fix'),
        ('tool_arg_fix', 'Tool Argument Fix'),
        ('config_gotcha', 'Configuration Gotcha'),
        ('business_rule', 'Business Rule'),
        ('user_preference', 'User Preference'),
    ], string='Lesson Type', default='spec_fix', required=True)
    scope = fields.Selection([
        ('company', 'Company-Specific'),
        ('user', 'User-Specific'),
        ('global', 'Global Template'),
    ], string='Scope', default='company', required=True)
    state = fields.Selection([
        ('candidate', 'Candidate'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('retired', 'Retired'),
    ], string='State', default='candidate', required=True, index=True)
    support_count = fields.Integer(string='Support Count', default=1)
    evidence_use_case_ids = fields.Many2many('ai.agent.use.case', string='Evidence Use Cases')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    last_used = fields.Datetime(string='Last Used')

    @api.constrains('guidance')
    def _check_guidance_sanitized(self):
        for rec in self:
            if rec.guidance:
                sanitize_lesson_text(rec.guidance)
                if len(rec.guidance) > 500:
                    raise ValidationError("Guidance text exceeds maximum cap of 500 characters.")


class AiAgentExample(models.Model):
    _name = 'ai.agent.example'
    _description = 'AI Agent Verified Example'
    _order = 'quality_score desc, id desc'

    use_case_id = fields.Many2one('ai.agent.use.case', string='Source Use Case', required=True, ondelete='cascade')
    domain = fields.Char(string='Domain', required=True, index=True)
    quality_score = fields.Float(string='Quality Score', default=1.0)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    state = fields.Selection([
        ('candidate', 'Candidate'),
        ('verified', 'Verified Success'),
        ('retired', 'Retired'),
    ], string='State', default='verified', required=True)


class AiAgentProfileEntry(models.Model):
    _name = 'ai.agent.profile.entry'
    _description = 'AI Agent Profile Default Entry'
    _order = 'key asc'

    key = fields.Char(string='Configuration Key', required=True, index=True)
    value_json = fields.Text(string='Value (JSON)', required=True)
    source = fields.Selection([
        ('declared', 'User Declared'),
        ('learned', 'System Inferred'),
        ('confirmed', 'User Confirmed'),
    ], string='Source', default='learned', required=True)
    confidence = fields.Float(string='Confidence Score', default=0.5)
    last_confirmed = fields.Datetime(string='Last Confirmed')
    user_id = fields.Many2one('res.users', string='Specific User (Optional)')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
