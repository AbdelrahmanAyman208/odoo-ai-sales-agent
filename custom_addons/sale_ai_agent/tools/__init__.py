# -*- coding: utf-8 -*-
"""
Tools package initialization (Global Decisions 7 & 8).
Imports all domain modules to build the centralized tool registry at import time.
"""
from . import base
from . import matching
from . import search_tools
from . import diagnostic_tools
from . import sales_tools
from . import purchase_tools
from . import inventory_tools
from . import location_tools
from . import mrp_tools
from . import crm_tools
from . import admin_tools
from . import loyalty_tools
from . import project_tools
from . import quality_tools
from . import warehouse_tools
from . import variant_tools
from . import docs_tools
from . import inspector_tools

from .base import (
    agent_tool,
    get_all_tool_definitions,
    get_capabilities_panel_data,
    get_tool_meta,
    ToolExecutor,
)
