# -*- coding: utf-8 -*-
"""
Settings for AI Operations Agent (Global Decisions 1 & 2).
Features:
- Single OpenAI-compatible client configuration (OpenRouter default).
- RPM rate limit and Daily Request Budget parameters.
- 'Test Connection' button with full round-trip verification.
- Clean OpenAI-compatible configuration with zero vendor-specific keys.
"""
from odoo import fields, models
from odoo.exceptions import UserError
from .llm_client import OpenAILLMClient


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ai_api_base = fields.Char(
        string='OpenAI / OpenRouter Base URL',
        default='https://openrouter.ai/api/v1',
        config_parameter='sale_ai_agent.api_base',
        help='Endpoint for standard OpenAI-compatible completions API (e.g. OpenRouter, vLLM, Ollama, OpenAI).',
    )
    ai_api_key = fields.Char(
        string='API Key',
        config_parameter='sale_ai_agent.api_key',
        help='Your OpenAI or OpenRouter API key.',
    )
    ai_model = fields.Char(
        string='Model Name',
        default='google/gemini-2.0-flash-exp:free',
        config_parameter='sale_ai_agent.model',
        help='Model ID (e.g. google/gemini-2.0-flash-exp:free, meta-llama/llama-3.3-70b-instruct:free, openai/gpt-4o-mini).',
    )
    ai_max_tokens = fields.Integer(
        string='Max Output Tokens',
        default=4096,
        config_parameter='sale_ai_agent.max_tokens',
    )
    ai_temperature = fields.Float(
        string='Temperature',
        default=0.7,
        config_parameter='sale_ai_agent.temperature',
    )
    ai_timeout = fields.Integer(
        string='Request Timeout (Seconds)',
        default=45,
        config_parameter='sale_ai_agent.timeout',
    )
    ai_rpm_limit = fields.Integer(
        string='Requests Per Minute (RPM) Budget',
        default=15,
        config_parameter='sale_ai_agent.rpm_limit',
        help='Rate limiter token bucket threshold to prevent 429 errors on free models.',
    )
    ai_daily_budget = fields.Integer(
        string='Daily Request Budget',
        default=200,
        config_parameter='sale_ai_agent.daily_budget',
        help='Hard limit on daily LLM calls to preserve quota on free tiers.',
    )
    ai_redis_url = fields.Char(
        string='Redis Connection URL',
        config_parameter='sale_ai_agent.redis_url',
        help='Optional Redis URL (e.g. redis://localhost:6379/0) for shared rate limiter and RAG cache.',
    )

    ai_system_prompt = fields.Text(
        string='System Prompt',
        default=(
            "You are an expert Operations & Sales AI Agent embedded in Odoo 20. "
            "You plan and execute business tasks as a Junior Odoo Implementer across Sales, Purchase, Inventory, and Manufacturing. "
            "Never execute T2 irreversible actions directly; always request human approval. "
            "Always be concise, precise, and verify data before making changes."
        ),
    )

    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        default_prompt = (
            "You are an expert Operations & Sales AI Agent embedded in Odoo 20. "
            "You plan and execute business tasks as a Junior Odoo Implementer across Sales, Purchase, Inventory, and Manufacturing. "
            "Never execute T2 irreversible actions directly; always request human approval. "
            "Always be concise, precise, and verify data before making changes."
        )
        res['ai_system_prompt'] = ICP.get_str('sale_ai_agent.system_prompt', default=default_prompt)
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_str('sale_ai_agent.system_prompt', (self.ai_system_prompt or '').strip())

    # T2 Human Approval Configuration (Global Decision 7)
    ai_approval_expiry_minutes = fields.Integer(
        string='Approval Expiry (Minutes)',
        default=15,
        config_parameter='sale_ai_agent.approval_expiry_minutes',
    )
    ai_approval_max_records = fields.Integer(
        string='Max Records Per Approval',
        default=50,
        config_parameter='sale_ai_agent.approval_max_records',
    )
    ai_approval_allow_manager = fields.Boolean(
        string='Allow Manager Approver',
        default=False,
        config_parameter='sale_ai_agent.approval_allow_manager',
    )
    ai_approval_require_reauth = fields.Boolean(
        string='Require Password Re-Auth on Final Confirmation',
        default=False,
        config_parameter='sale_ai_agent.approval_require_reauth',
    )

    def action_test_llm_connection(self):
        """Tests live connectivity to the configured OpenAI-compatible endpoint."""
        self.ensure_one()
        client = OpenAILLMClient(
            base_url=self.ai_api_base,
            api_key=self.ai_api_key,
            model=self.ai_model,
            timeout=self.ai_timeout,
        )
        res = client.test_connection()
        if not res.get("success"):
            raise UserError(f"Connection Failed: {res.get('error')}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'LLM Connection Successful',
                'message': res.get('message', 'Ready to handle requests.'),
                'type': 'success',
                'sticky': False,
            }
        }
