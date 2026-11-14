# -*- coding: utf-8 -*-
"""
System Capabilities & Edition Detection Service (Global Decision 7).
Discovers installed modules, edition (Community vs Enterprise), and available feature flags.

Complexity:
- Time: O(1) cached per registry; O(N) single query on first load where N = installed modules count.
- Space: O(M) set of installed module names in memory.
"""
import logging
from typing import Dict, Any, Set

_logger = logging.getLogger(__name__)

# Registry-level or memory cache
_INSTALLED_MODULES_CACHE: Set[str] = set()
_EDITION_CACHE: str = ""


def get_installed_modules(env) -> Set[str]:
    """
    Returns the set of installed module names.
    Queries ir_module_module once and caches in memory.
    """
    global _INSTALLED_MODULES_CACHE
    if _INSTALLED_MODULES_CACHE:
        return _INSTALLED_MODULES_CACHE

    try:
        modules = env['ir.module.module'].sudo().search_read(
            [('state', '=', 'installed')],
            ['name']
        )
        _INSTALLED_MODULES_CACHE = {m['name'] for m in modules}
    except Exception as e:
        _logger.warning("Failed querying installed modules: %s", e)
        _INSTALLED_MODULES_CACHE = set()

    return _INSTALLED_MODULES_CACHE


def refresh_installed_modules_cache(env) -> Set[str]:
    """Force-refreshes the installed modules cache."""
    global _INSTALLED_MODULES_CACHE
    _INSTALLED_MODULES_CACHE = set()
    return get_installed_modules(env)


def is_module_installed(env, module_name: str) -> bool:
    """Checks if a given module name is installed."""
    return module_name in get_installed_modules(env)


def get_odoo_edition(env) -> str:
    """
    Detects if running Community or Enterprise.
    Enterprise typically installs 'web_enterprise' or has enterprise code in addons path.
    """
    global _EDITION_CACHE
    if _EDITION_CACHE:
        return _EDITION_CACHE

    installed = get_installed_modules(env)
    if 'web_enterprise' in installed:
        _EDITION_CACHE = 'Enterprise'
    else:
        _EDITION_CACHE = 'Community'

    return _EDITION_CACHE


def get_system_capabilities(env) -> Dict[str, Any]:
    """
    Full capability manifest for the AI Agent and diagnostics.
    Reports installed business modules, edition, and domain statuses.
    """
    installed = get_installed_modules(env)
    edition = get_odoo_edition(env)

    capabilities = {
        "edition": edition,
        "domains": {
            "sales": 'sale_management' in installed or 'sale' in installed,
            "purchase": 'purchase' in installed,
            "inventory": 'stock' in installed,
            "mrp": 'mrp' in installed,
            "crm": 'crm' in installed,
            "project": 'project' in installed,
            "loyalty": 'loyalty' in installed or 'sale_loyalty' in installed,
            "quality": 'quality_control' in installed,  # If False, AI lightweight fallback used
            "timesheet": 'hr_timesheet' in installed,
        },
        "quality_mode": "native_enterprise" if 'quality_control' in installed else "ai_lightweight_community",
        "total_installed_modules": len(installed),
    }
    return capabilities
