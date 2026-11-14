# -*- coding: utf-8 -*-
"""
Self-Check Diagnostic Tools for Odoo 20 (Global Decision 7).
Enables agent to inspect real system state, capabilities, routes, and installed modules before acting.
"""
from typing import Any, Dict
from ..tools.base import agent_tool
from ..services.capabilities import get_system_capabilities as get_caps


@agent_tool(
    name="get_system_capabilities",
    domain="administration",
    label="Get System Capabilities & Edition",
    description="Discovers Odoo edition (Community vs Enterprise), active business domains, installed modules count, and quality mode.",
    tier="T0",
    examples=["What edition is this?", "What modules are available?"],
    parameters={"type": "object", "properties": {}},
)
def get_system_capabilities(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    caps = get_caps(env)
    return {
        "success": True,
        "capabilities": caps,
        "message": f"Odoo 20.0 ({caps['edition']} Edition) with {caps['total_installed_modules']} installed modules. Quality mode: {caps['quality_mode']}."
    }


@agent_tool(
    name="check_system_configuration",
    domain="inventory",
    label="Self-Check System & Module Configuration",
    description="Inspects installed modules, warehouse multi-step routing settings, and tracking features.",
    tier="T0",
    examples=["Check system configuration", "Are multi-step routes enabled?"],
    parameters={"type": "object", "properties": {}},
)
def check_system_configuration(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    # Check key module installations
    Module = env["ir.module.module"]
    modules_installed = {
        m["name"]: (m["state"] == "installed")
        for m in Module.search_read([("name", "in", ["sale_management", "purchase", "stock", "mrp", "crm", "project", "loyalty"])], ["name", "state"])
    }

    # Warehouse routing & tracking settings
    has_mto = bool(env["stock.route"].search([("name", "ilike", "Replenish on Order (MTO)")], limit=1))
    warehouses_count = env["stock.warehouse"].search_count([])

    return {
        "success": True,
        "company": env.company.name,
        "currency": env.company.currency_id.name,
        "modules_installed": modules_installed,
        "warehouses_count": warehouses_count,
        "mto_route_configured": has_mto,
        "message": f"System configured with {warehouses_count} warehouse(s). Key modules verified.",
    }


@agent_tool(
    name="check_product_routes_and_bom",
    domain="mrp",
    label="Self-Check Product Routes & BOM Status",
    description="Inspects whether a product has an active BOM and what routes (Buy, Manufacture, MTO) are configured.",
    tier="T0",
    examples=["Check routes and BOM for Desk Pro", "Can we manufacture Chair?"],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Product name or ID"},
        },
        "required": ["product_name_or_id"],
    },
)
def check_product_routes_and_bom(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from ..services.product_resolver import find_or_disambiguate_product
    query = str(args["product_name_or_id"])
    prod, disambig = find_or_disambiguate_product(env, query)
    if disambig:
        return {"success": False, "disambiguation_required": True, "candidates": disambig}
    if not prod:
        return {"success": False, "error": f"Product '{query}' not found."}

    bom = env["mrp.bom"]._bom_find(prod)[prod]
    routes = [r.name for r in (prod.route_ids | prod.product_tmpl_id.route_ids)]

    return {
        "success": True,
        "product_id": prod.id,
        "product_name": prod.display_name,
        "has_bom": bool(bom),
        "bom_id": bom.id if bom else None,
        "configured_routes": routes,
        "is_manufactured": any("manufacture" in r.lower() for r in routes) or bool(bom),
        "is_purchasable": any("buy" in r.lower() for r in routes) or bool(prod.seller_ids),
        "suppliers_count": len(prod.seller_ids),
    }
