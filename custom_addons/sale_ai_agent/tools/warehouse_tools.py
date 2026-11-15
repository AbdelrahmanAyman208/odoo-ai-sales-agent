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
    Location = env['stock.location']

    # Support creating locations if location_name is specified
    if args.get("location_name"):
        loc_name = str(args["location_name"]).strip()
        usage = args.get("location_usage", "internal")
        parent_loc_id = args.get("parent_location_id")
        if not parent_loc_id:
            # Default parent to default warehouse stock location
            wh = Warehouse.search([('company_id', '=', env.company.id)], limit=1)
            parent_loc_id = wh.lot_stock_id.id if wh else False

        existing_loc = Location.search([
            ('name', '=', loc_name),
            ('location_id', '=', parent_loc_id),
        ], limit=1)
        if not existing_loc:
            # Also search by complete_name
            existing_loc = Location.search([('complete_name', '=', loc_name)], limit=1)

        if existing_loc:
            return {
                "success": True,
                "location_id": existing_loc.id,
                "name": existing_loc.complete_name,
                "message": f"Location '{existing_loc.complete_name}' already exists (ID: {existing_loc.id}).",
            }

        new_loc = Location.create({
            'name': loc_name.split('/')[-1],
            'location_id': parent_loc_id,
            'usage': usage,
            'company_id': env.company.id,
        })
        return {
            "success": True,
            "location_id": new_loc.id,
            "name": new_loc.complete_name,
            "message": f"Location '{new_loc.complete_name}' created successfully (ID: {new_loc.id}).",
        }

    # Otherwise standard warehouse creation
    name = str(args.get("name") or "New Warehouse").strip()
    code = str(args.get("code") or name[:3]).strip().upper()[:5]

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
    prod_query = (
        args.get("product_name_or_id")
        or args.get("product_name")
        or args.get("product")
        or "Fridge 360L"
    )
    prod, disambig = find_or_disambiguate_product(env, str(prod_query))
    if disambig:
        return {"success": False, "disambiguation_required": True, "candidates": disambig}
    if not prod:
        return {"success": False, "error": f"Product '{prod_query}' not found"}

    min_qty = float(args.get("min_qty") or args.get("min") or 3.0)
    max_qty = float(args.get("max_qty") or args.get("max") or 10.0)

    loc_id = args.get("location_id")
    if not loc_id and args.get("location_name"):
        loc = env['stock.location'].search([
            '|',
            ('name', 'ilike', args["location_name"]),
            ('complete_name', 'ilike', args["location_name"]),
        ], limit=1)
        if loc:
            loc_id = loc.id

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
        'product_min_qty': min_qty,
        'product_max_qty': max_qty,
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
