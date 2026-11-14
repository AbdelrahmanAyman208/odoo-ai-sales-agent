# -*- coding: utf-8 -*-
"""
Compatibility adapter wrapping new tools/ package.
Delegates to ToolExecutor and get_all_tool_definitions.
"""
import json
import logging
from odoo import api, models
from ..tools import ToolExecutor, get_all_tool_definitions

_logger = logging.getLogger(__name__)


class AiSalesTools(models.AbstractModel):
    _name = 'ai.sales.tools'
    _description = 'Sales AI Agent Tools Engine (Adapter)'

    @api.model
    def get_tool_definitions(self, domain=None):
        return get_all_tool_definitions(domain=domain)

    @api.model
    def execute_tool(self, tool_name: str, args=None, context=None):
        """Dispatches to modular ToolExecutor."""
        if args is None:
            args = {}
        return ToolExecutor.execute(self.env, tool_name, args, context=context)
