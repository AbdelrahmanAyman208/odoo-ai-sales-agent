from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ai_provider = fields.Selection(
        selection=[
            ('openai_compatible', 'OpenAI Compatible (OpenAI, OpenRouter, Groq, Local LLM)'),
            ('anthropic', 'Anthropic Claude (Native / FreeModel / Anthropic)'),
            ('gemini', 'Google Gemini'),
        ],
        string='AI Provider',
        default='openai_compatible',
        config_parameter='sale_ai_agent.provider',
        help='Choose which AI backend to use for the sales agent.',
    )
    ai_api_key = fields.Char(
        string='AI API Key',
        config_parameter='sale_ai_agent.api_key',
        help='Your OpenAI, OpenRouter, Groq, or Gemini API Key.',
    )
    ai_api_base = fields.Char(
        string='API Base URL',
        default='https://api.openai.com/v1',
        config_parameter='sale_ai_agent.api_base',
        help='Default for OpenAI: https://api.openai.com/v1. For OpenRouter: https://openrouter.ai/api/v1',
    )
    ai_model = fields.Char(
        string='AI Model',
        default='gpt-4o-mini',
        config_parameter='sale_ai_agent.model',
        help='Model identifier. Anthropic: claude-3-5-sonnet-20241022 or claude-3-7-sonnet-latest. OpenAI: gpt-4o-mini, gpt-4o. Gemini: gemini-1.5-flash, gemini-2.0-flash.',
    )
    ai_temperature = fields.Float(
        string='Temperature',
        default=0.7,
        config_parameter='sale_ai_agent.temperature',
        help='Creativity level between 0.0 (focused) and 1.0 (creative).',
    )
    ai_system_prompt = fields.Text(
        string='AI Assistant System Prompt',
        default=(
            "You are an expert, proactive AI Implementation & Operations Agent embedded in Odoo ERP. "
            "Your role is to assist teams with Sales, Purchasing, Inventory Replenishment, and CRM: "
            "creating customer quotations, managing low-stock alerts, generating automated replenishment orders, "
            "broadcasting RFQs to all suppliers, analyzing vendor offers to find the lowest price, "
            "building composite assembled products, and providing pipeline insights. "
            "Always be professional, concise, accurate, and proactive."
        ),
        config_parameter='sale_ai_agent.system_prompt',
    )
