# -*- coding: utf-8 -*-
"""
Base Tool Registry and Decorator Engine (Global Decisions 7 & 8).
Features:
- Schema generation at import time.
- Conditional registration via available_if=[modules] (Global Decision 8).
- Unified tool dispatcher with database savepoints.
- Direct T2 human approval delegation via services.approval_service.
- Disambiguation and capabilities metadata helpers.

Complexity:
- Time: O(1) registry dispatch.
- Space: O(K) cached schemas.
"""
import functools
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Set
from odoo.exceptions import AccessError, UserError
from ..services.capabilities import get_installed_modules
from ..services.approval_service import create_approval_request

_logger = logging.getLogger(__name__)

# Registry caches built at import time
_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}
_DOMAIN_TOOLS: Dict[str, List[str]] = {}


def agent_tool(
    name: str,
    domain: str,
    label: str,
    description: str,
    tier: str = 'T1',  # T0: read-only, T1: reversible/draft, T2: human approval required
    examples: Optional[List[str]] = None,
    parameters: Optional[Dict[str, Any]] = None,
    available_if: Optional[List[str]] = None,
):
    """
    Decorator to register an AI tool into the centralized schema registry.
    available_if: List of Odoo module technical names required for this tool to be active.
    """
    def decorator(func: Callable):
        params = parameters or {"type": "object", "properties": {}, "required": []}
        tool_meta = {
            "name": name,
            "domain": domain,
            "label": label,
            "description": description,
            "tier": tier,
            "examples": examples or [],
            "parameters": params,
            "available_if": available_if or [],
            "func": func,
        }
        _TOOL_REGISTRY[name] = tool_meta
        if domain not in _DOMAIN_TOOLS:
            _DOMAIN_TOOLS[domain] = []
        if name not in _DOMAIN_TOOLS[domain]:
            _DOMAIN_TOOLS[domain].append(name)
        return func
    return decorator


def get_tool_meta(tool_name: str) -> Optional[Dict[str, Any]]:
    return _TOOL_REGISTRY.get(tool_name)


def is_tool_available(env, meta: Dict[str, Any]) -> bool:
    """
    Checks if all required modules for the tool are installed in the current database.
    """
    reqs = meta.get("available_if")
    if not reqs:
        return True
    installed = get_installed_modules(env)
    return all(m in installed for m in reqs)


def get_all_tool_definitions(env=None, domain: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns OpenAI/Anthropic compatible tool schemas.
    Filters out tools whose required modules are not installed in the database.
    If domain is provided and not 'multi', returns tools for that domain plus core search/diagnostic tools.
    """
    # Core utilities always available across domains
    CORE_TOOLS = {
        "search_products", "search_partner", "check_system_configuration", "get_stock_availability",
        "get_system_capabilities"
    }

    tools = []
    for t_name, meta in _TOOL_REGISTRY.items():
        # Check module dependencies if env is provided
        if env and not is_tool_available(env, meta):
            continue

        if domain and domain != "multi":
            if meta["domain"] != domain and t_name not in CORE_TOOLS:
                continue

        tools.append({
            "name": meta["name"],
            "description": meta["description"],
            "input_schema": meta["parameters"],
            "tier": meta["tier"],
            "domain": meta["domain"],
            "label": meta["label"],
            "examples": meta["examples"],
        })
    return tools


def get_capabilities_panel_data(env=None) -> Dict[str, Any]:
    """
    Generates data for 'What I can do' panel and capabilities discovery.
    Organized by module: sales, purchase, inventory, mrp, crm, project, loyalty, quality, administration.
    """
    domains = {
        "sales": {"label": "Sales / المبيعات", "desc": "Manage quotations, pricing, discounts, and customer orders"},
        "purchase": {"label": "Purchase / المشتريات", "desc": "Create RFQs, compare vendor offers, broadcast to suppliers"},
        "inventory": {"label": "Inventory / المخازن", "desc": "Real-time stock, reordering, replenishment, and warehouse routes"},
        "mrp": {"label": "Manufacturing / التصنيع", "desc": "BOMs, components, production orders, and Make-to-Order flows"},
        "crm": {"label": "CRM / العلاقات والعملاء", "desc": "Pipeline health, lead conversion, scoring, and opportunity follow-ups"},
        "project": {"label": "Project / المشاريع والمهام", "desc": "Tasks, milestones, deadlines, and project health monitoring"},
        "loyalty": {"label": "Loyalty & Promos / العروض والولاء", "desc": "Coupons, promotional rules, discounts, and customer pricelists"},
        "quality": {"label": "Quality / مراقبة الجودة", "desc": "Quality control points and manufacturing check inspections"},
        "administration": {"label": "System Admin / إعدادات النظام", "desc": "Language activation, user creation, and system configuration"},
    }
    result = {}
    for d_key, d_info in domains.items():
        tool_names = _DOMAIN_TOOLS.get(d_key, [])
        actions = []
        examples = []
        for t_name in tool_names:
            meta = _TOOL_REGISTRY[t_name]
            if env and not is_tool_available(env, meta):
                continue
            actions.append({
                "name": meta["name"],
                "label": meta["label"],
                "tier": meta["tier"],
            })
            if meta["examples"]:
                examples.extend(meta["examples"][:2])
        if actions:
            result[d_key] = {
                "name": d_key,
                "label": d_info["label"],
                "description": d_info["desc"],
                "actions": actions,
                "examples": list(dict.fromkeys(examples))[:3],
            }
    return result


class ToolExecutor:
    """Dispatches tool execution with savepoints and safety tiers (Global Decision 8)."""

    @classmethod
    def execute(cls, env, tool_name: str, args: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a registered tool within a database savepoint.
        If tool is T2, intercepts execution and creates ai.agent.approval record instead.
        """
        meta = _TOOL_REGISTRY.get(tool_name)
        if not meta:
            available = list(_TOOL_REGISTRY.keys())
            return {
                "success": False,
                "error": f"Tool '{tool_name}' does not exist. Available tools: {', '.join(available[:8])}..."
            }

        # Check module availability
        if not is_tool_available(env, meta):
            reqs = meta.get("available_if", [])
            return {
                "success": False,
                "error": f"Tool '{tool_name}' requires uninstalled Odoo module(s): {', '.join(reqs)}. Feature is unavailable in current setup."
            }

        # Coerce arguments if string
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Invalid JSON arguments provided for tool '{tool_name}': {str(e)}",
                }

        # Auto-repair / normalize arguments dict to prevent common LLM formatting bugs
        if isinstance(args, dict):
            repaired_args = {}
            for k, v in args.items():
                if isinstance(v, list) and len(v) == 1 and k.endswith(('_id', '_qty', '_price', '_name')):
                    v = v[0]
                if isinstance(v, str) and (k.endswith('_id') or k in ('quantity', 'product_qty', 'limit')):
                    clean_str = v.strip()
                    if clean_str.isdigit():
                        v = int(clean_str)
                    else:
                        try:
                            v = float(clean_str)
                        except ValueError:
                            pass
                repaired_args[k] = v
            args = repaired_args

        # T2 Human Approval Interception (Global Decision 6)
        if meta["tier"] == 'T2':
            return create_approval_request(env, meta, args, context)

        # Normal execution inside database savepoint
        try:
            with env.cr.savepoint():
                func = meta["func"]
                result = func(env, args, context or {})
                return result
        except AccessError as ae:
            return {"success": False, "error": f"Permission Denied: {str(ae)}"}
        except UserError as ue:
            return {"success": False, "error": f"Business Validation Error: {str(ue)}"}
        except Exception as ex:
            _logger.exception("Error executing tool %s: %s", tool_name, ex)
            return {"success": False, "error": f"Execution error in {tool_name}: {str(ex)}"}
