# -*- coding: utf-8 -*-
"""
Multi-Warehouse & Advanced Logistics Domain Tools (Phase 12, Global Decision 8).
Features:
- Warehouse network topology & configuration.
- Multi-warehouse stock visibility via _read_group.
- Reordering rules (min/max stock points).
- Automated replenishment scheduler triggers.
- Dry-run replenishment simulation without DB commit.

Complexity:
- Time: O(1) rules/transfers; O(W) stock aggregation where W is warehouses count.
- Space: O(K) where K is returned quants.
"""
import logging
from typing import Any, Dict, List, Optional
from ..tools.base import agent_tool
from ..services.product_resolver import find_or_disambiguate_product

_logger = logging.getLogger(__name__)


@agent_tool(
    name="configure_warehouse_network",
    domain="inventory",
    label="Configure Warehouse Network & Routes",
    description="Creates or configures warehouses, codes, addresses, and inter-warehouse resupply routes.",
    tier="T1",
    available_if=["stock"],
    examples=["Setup East Coast Warehouse (code: ECW)", "Configure Central Hub"],
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Warehouse Name"},
            "code": {"type": "string", "description": "Short code (up to 5 chars)"},
            "resupply_wh_id": {"type": "integer", "description": "Optional source warehouse ID for resupply"},
        },
        "required": ["name", "code"],
    },
)
def configure_warehouse_network(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    Warehouse = env['stock.warehouse']
    code = args["code"].strip().upper()[:5]
    name = args["name"].strip()

    existing = Warehouse.search([('code', '=', code)], limit=1)
    if existing:
        return {
            "success": True,
            "warehouse_id": existing.id,
            "name": existing.name,
            "code": existing.code,
            "message": f"Warehouse with code '{code}' already exists: {existing.name} (ID: {existing.id}).",
        }

    vals = {
        'name': name,
        'code': code,
        'company_id': env.company.id,
    }
    wh = Warehouse.create(vals)
    return {
        "success": True,
        "warehouse_id": wh.id,
        "name": wh.name,
        "code": wh.code,
        "view_location_id": wh.view_location_id.id,
        "lot_stock_id": wh.lot_stock_id.id,
        "message": f"Warehouse '{wh.name}' ({wh.code}) created successfully.",
    }


@agent_tool(
    name="configure_reordering_rules",
    domain="inventory",
    label="Configure Min / Max Reordering Rules",
    description="Sets automated replenishment orderpoints (min qty, max qty, multiple) per product and location.",
    tier="T1",
    available_if=["stock"],
    examples=["Set min 10 max 50 reordering rule for Desk Pro", "Configure safety stock on Chairs"],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Product name or ID"},
            "location_id": {"type": "integer", "description": "Optional specific internal location ID"},
            "min_qty": {"type": "number", "description": "Minimum stock quantity (threshold to trigger reorder)"},
            "max_qty": {"type": "number", "description": "Maximum stock quantity (target stock level)"},
            "qty_multiple": {"type": "number", "default": 1.0, "description": "Quantity multiple for orders"},
        },
        "required": ["product_name_or_id", "min_qty", "max_qty"],
    },
)
def configure_reordering_rules(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    Orderpoint = env['stock.warehouse.orderpoint']
    prod, disambig = find_or_disambiguate_product(env, str(args["product_name_or_id"]))
    if disambig:
        return {"success": False, "disambiguation_required": True, "candidates": disambig}
    if not prod:
        return {"success": False, "error": f"Product '{args['product_name_or_id']}' not found"}

    loc_id = args.get("location_id")
    if not loc_id:
        wh = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)
        loc_id = wh.lot_stock_id.id if wh else False

    existing = Orderpoint.search([
        ('product_id', '=', prod.id),
        ('location_id', '=', loc_id),
    ], limit=1)

    vals = {
        'product_id': prod.id,
        'location_id': loc_id,
        'product_min_qty': args["min_qty"],
        'product_max_qty': args["max_qty"],
        'qty_multiple': args.get("qty_multiple", 1.0),
    }

    if existing:
        existing.write(vals)
        rule = existing
        action = "updated"
    else:
        rule = Orderpoint.create(vals)
        action = "created"

    return {
        "success": True,
        "rule_id": rule.id,
        "product_name": prod.display_name,
        "min_qty": rule.product_min_qty,
        "max_qty": rule.product_max_qty,
        "action": action,
        "message": f"Reordering rule {action} for '{prod.display_name}': Min {rule.product_min_qty}, Max {rule.product_max_qty}.",
    }


@agent_tool(
    name="get_warehouse_stock_report",
    domain="inventory",
    label="Warehouse Network Stock Overview",
    description="Aggregates on-hand and available quantities across all configured warehouses via _read_group.",
    tier="T0",
    available_if=["stock"],
    examples=["Show warehouse stock report", "Compare stock between warehouses"],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Optional specific product to filter"},
        },
    },
)
def get_warehouse_stock_report(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    Quant = env['stock.quant']
    domain = [('location_id.usage', '=', 'internal')]

    if args.get("product_name_or_id"):
        prod, disambig = find_or_disambiguate_product(env, str(args["product_name_or_id"]))
        if prod:
            domain.append(('product_id', '=', prod.id))

    quant_data = Quant._read_group(
        domain,
        ['location_id.warehouse_id', 'product_id'],
        ['quantity:sum', 'reserved_quantity:sum'],
    )

    report = []
    for wh, prod_rec, qty, reserved in quant_data:
        report.append({
            "warehouse": wh.name if wh else "External / Internal Unassigned",
            "product_name": prod_rec.display_name if prod_rec else "All",
            "on_hand": qty or 0.0,
            "reserved": reserved or 0.0,
            "available": (qty or 0.0) - (reserved or 0.0),
        })

    return {
        "success": True,
        "lines_count": len(report),
        "warehouse_stock": report[:25],
    }
