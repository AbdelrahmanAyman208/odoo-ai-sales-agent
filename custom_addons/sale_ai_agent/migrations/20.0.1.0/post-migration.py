# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Remove obsolete ir.config_parameter keys belonging to removed providers
    (OpenAI, Gemini, Groq, Ollama) per Global Decision 1.
    """
    _logger.info("Migrating sale_ai_agent to 20.0.1.0: Removing obsolete provider config parameters")
    obsolete_keys = [
        'sale_ai_agent.provider',
        'sale_ai_agent.openai_api_key',
        'sale_ai_agent.gemini_api_key',
        'sale_ai_agent.groq_api_key',
        'sale_ai_agent.ollama_endpoint',
        'sale_ai_agent.fallback_model',
    ]
    cr.execute(
        "DELETE FROM ir_config_parameter WHERE key = ANY(%s)",
        (obsolete_keys,)
    )
    _logger.info("Deleted %d obsolete parameter keys.", cr.rowcount)

