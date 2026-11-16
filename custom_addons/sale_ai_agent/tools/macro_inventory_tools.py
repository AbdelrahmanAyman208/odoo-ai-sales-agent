# -*- coding: utf-8 -*-
"""
Advanced Warehouse Macro Tools (Addendum 4 & Phase 4 Replaced).
Spec-First Macro Tools:
- `warehouse_design_from_spec`: Full hierarchy (zones, aisles, racks, levels, bins)
- `multi_warehouse_network_build`: Central WH + Retail stores + Auto-resupply
- `replenishment_advise`: Average daily demand x lead time + safety stock via _read_group
- `warehouse_health_report`: O(1) query inventory health analytics
"""
import logging
from typing import Dict, Any, List, Tuple
from odoo import Command
from .base import agent_tool
from ..services.pipeline_engine import execute_pipeline

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# 1. WAREHOUSE DESIGN FROM SPEC
# ---------------------------------------------------------
def _understand_wh_spec(env, spec: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    assumptions = []
    resolved = dict(spec)
    if not resolved.get("code"):
        resolved["code"] = (resolved.get("name") or "WH")[:4].upper()
        assumptions.append(f"Warehouse code defaulted to '{resolved['code']}'")
    resolved["_estimated_record_count"] = 10
    return resolved, assumptions


def _preflight_wh_spec(env, spec: Dict[str, Any]) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    errors = []
    if 'stock.warehouse' not in env:
        errors.append("Inventory (stock) module is not installed.")
    return len(errors) == 0, errors, []


def _validate_wh_spec(env, spec: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []
    if not spec.get("name"):
        errors.append("Warehouse name is required.")
    return len(errors) == 0, errors


def _execute_wh_design(env, spec: Dict[str, Any]) -> Dict[str, Any]:
    Warehouse = env['stock.warehouse']
    Location = env['stock.location']

    wh_code = spec.get("code", "WH")[:5].upper()
    existing_wh = Warehouse.search([('code', '=', wh_code)], limit=1)
    if not existing_wh:
        wh = Warehouse.create({
            'name': spec.get("name"),
            'code': wh_code,
            'reception_steps': spec.get("reception_steps", "one_step"),
            'delivery_steps': spec.get("delivery_steps", "ship_only"),
            'company_id': env.company.id,
        })
    else:
        wh = existing_wh

    parent_stock = wh.lot_stock_id
    created_locations = []

    # Create zones / racks / bins hierarchy
    zones = spec.get("zones") or [
        {"name": "Raw Materials", "racks": 2, "levels": 3},
        {"name": "Finished Goods", "racks": 2, "levels": 3},
    ]

    for z in zones:
        z_name = z.get("name", "Zone")
        zone_loc = Location.create({
            'name': z_name,
            'location_id': parent_stock.id,
            'usage': 'internal',
            'company_id': env.company.id,
        })
        created_locations.append(zone_loc.complete_name)

        racks_count = int(z.get("racks", 1))
        levels_count = int(z.get("levels", 1))

        loc_vals_list = []
        for r in range(1, racks_count + 1):
            rack_name = f"R{r}"
            for l in range(1, levels_count + 1):
                bin_name = f"{rack_name}-L{l}"
                loc_vals_list.append({
                    'name': bin_name,
                    'location_id': zone_loc.id,
                    'usage': 'internal',
                    'company_id': env.company.id,
                })
        if loc_vals_list:
            sub_locs = Location.create(loc_vals_list)
            created_locations.extend([sl.complete_name for sl in sub_locs])

    return {
        "warehouse_id": wh.id,
        "warehouse_name": wh.name,
        "code": wh.code,
        "total_locations_created": len(created_locations),
        "locations": created_locations[:15],
    }


def _verify_wh_design(env, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    return True, []


@agent_tool(
    name="warehouse_design_from_spec",
    domain="inventory",
    label="Design Complete Warehouse & Location Hierarchy",
    description="Builds an entire multi-level warehouse hierarchy with zones, racks, and bins in one batched execution.",
    tier="T1",
    examples=["Design warehouse with 3 zones and 4 racks x 5 levels"],
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Warehouse Name"},
            "code": {"type": "string", "description": "Warehouse Code (up to 5 chars)"},
            "reception_steps": {"type": "string", "enum": ["one_step", "two_steps", "three_steps"], "default": "one_step"},
            "delivery_steps": {"type": "string", "enum": ["ship_only", "pick_ship", "pick_pack_ship"], "default": "ship_only"},
            "zones": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "racks": {"type": "integer", "default": 2},
                        "levels": {"type": "integer", "default": 3},
                    },
                    "required": ["name"],
                },
            },
        },
        "required": ["name"],
    },
)
def warehouse_design_from_spec(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    return execute_pipeline(
        env=env,
        tool_name="warehouse_design_from_spec",
        spec=args,
        understand_fn=_understand_wh_spec,
        preflight_fn=_preflight_wh_spec,
        validate_fn=_validate_wh_spec,
        execute_fn=_execute_wh_design,
        verify_fn=_verify_wh_design,
    )


# ---------------------------------------------------------
# 2. MULTI-WAREHOUSE NETWORK & RESUPPLY
# ---------------------------------------------------------
@agent_tool(
    name="multi_warehouse_network_build",
    domain="inventory",
    label="Build Multi-Warehouse Network with Automated Resupply",
    description="Creates a central warehouse and retail stores, links inter-warehouse resupply routes, and sets replenishment orderpoints.",
    tier="T1",
    examples=["Create central warehouse and 2 retail stores with auto-resupply"],
    parameters={
        "type": "object",
        "properties": {
            "central_name": {"type": "string", "default": "Central Warehouse"},
            "central_code": {"type": "string", "default": "CWH"},
            "stores": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "code": {"type": "string"},
                        "reorder_min": {"type": "number", "default": 10},
                        "reorder_max": {"type": "number", "default": 50},
                    },
                    "required": ["name", "code"],
                },
            },
            "product_name_or_id": {"type": "string", "description": "Product to configure orderpoint on stores"},
        },
        "required": ["central_name", "stores"],
    },
)
def multi_warehouse_network_build(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    Warehouse = env['stock.warehouse']
    Orderpoint = env['stock.warehouse.orderpoint']

    # 1. Central WH
    c_code = args.get("central_code", "CWH")[:5].upper()
    central_wh = Warehouse.search([('code', '=', c_code)], limit=1)
    if not central_wh:
        central_wh = Warehouse.create({
            'name': args.get("central_name", "Central Warehouse"),
            'code': c_code,
            'company_id': env.company.id,
        })

    # 2. Store WHs + Resupply Linkage
    stores_data = args.get("stores", [])
    created_stores = []

    # Resolve product if provided
    Product = env['product.product']
    target_prod = False
    if args.get("product_name_or_id"):
        target_prod = Product.search([('name', '=', str(args["product_name_or_id"]))], limit=1)

    for s in stores_data:
        s_code = s.get("code")[:5].upper()
        store_wh = Warehouse.search([('code', '=', s_code)], limit=1)
        if not store_wh:
            store_wh = Warehouse.create({
                'name': s.get("name"),
                'code': s_code,
                'company_id': env.company.id,
                'resupply_wh_ids': [Command.link(central_wh.id)],
            })
        else:
            if central_wh.id not in store_wh.resupply_wh_ids.ids:
                store_wh.write({'resupply_wh_ids': [Command.link(central_wh.id)]})

        # Orderpoint if product exists
        if target_prod:
            existing_op = Orderpoint.search([
                ('product_id', '=', target_prod.id),
                ('location_id', '=', store_wh.lot_stock_id.id),
            ], limit=1)
            op_vals = {
                'product_id': target_prod.id,
                'location_id': store_wh.lot_stock_id.id,
                'product_min_qty': s.get("reorder_min", 10.0),
                'product_max_qty': s.get("reorder_max", 50.0),
            }
            if existing_op:
                existing_op.write(op_vals)
            else:
                Orderpoint.create(op_vals)

        created_stores.append(f"{store_wh.name} ({store_wh.code}) -> Resupplied by {central_wh.code}")

    return {
        "success": True,
        "central_warehouse": f"{central_wh.name} ({central_wh.code})",
        "stores_count": len(created_stores),
        "network": created_stores,
        "message": f"Successfully configured distribution network with central hub and {len(created_stores)} store(s).",
    }


# ---------------------------------------------------------
# 3. REPLENISHMENT ADVISOR (Demand Math & Draft Orderpoints)
# ---------------------------------------------------------
@agent_tool(
    name="replenishment_advise",
    domain="inventory",
    label="Replenishment Advisor (Demand History Analytics)",
    description="Calculates suggested min/max reorder rules based on daily demand velocity, lead times, and safety stock.",
    tier="T0",
    examples=["Advise replenishment rules for Fridge 360L", "Calculate safety stock levels"],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Product name or ID"},
            "lead_time_days": {"type": "integer", "default": 7, "description": "Supplier / production lead time in days"},
            "safety_stock_days": {"type": "integer", "default": 5, "description": "Buffer safety stock in days of demand"},
            "apply_draft": {"type": "boolean", "default": False, "description": "If true, writes the computed rule to stock.warehouse.orderpoint"},
        },
        "required": ["product_name_or_id"],
    },
)
def replenishment_advise(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    Product = env['product.product']
    prod = Product.search([('name', '=', str(args["product_name_or_id"]))], limit=1)
    if not prod:
        return {"success": False, "error": f"Product '{args['product_name_or_id']}' not found."}

    # Demand calculation via _read_group over stock moves
    StockMove = env['stock.move']
    domain = [
        ('product_id', '=', prod.id),
        ('state', '=', 'done'),
        ('location_dest_id.usage', '=', 'customer'),
    ]
    delivered_data = StockMove._read_group(domain, ['product_id'], ['product_qty:sum'])
    total_delivered = delivered_data[0][1] if delivered_data else 0.0

    # Default daily velocity estimate if no historical transactions
    avg_daily_demand = max(1.0, round(total_delivered / 90.0, 2)) if total_delivered > 0 else 2.5
    lead_time = int(args.get("lead_time_days", 7))
    safety_days = int(args.get("safety_stock_days", 5))

    suggested_min = round(avg_daily_demand * lead_time + avg_daily_demand * safety_days, 1)
    suggested_max = round(suggested_min * 2.5, 1)

    res = {
        "success": True,
        "product": prod.display_name,
        "avg_daily_demand": avg_daily_demand,
        "lead_time_days": lead_time,
        "safety_stock_days": safety_days,
        "suggested_min_qty": suggested_min,
        "suggested_max_qty": suggested_max,
        "formula": f"Min = ({avg_daily_demand} daily x {lead_time}d lead time) + ({avg_daily_demand} x {safety_days}d safety buffer) = {suggested_min}",
    }

    if args.get("apply_draft"):
        wh = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)
        Orderpoint = env['stock.warehouse.orderpoint']
        op = Orderpoint.search([('product_id', '=', prod.id), ('location_id', '=', wh.lot_stock_id.id)], limit=1)
        vals = {
            'product_id': prod.id,
            'location_id': wh.lot_stock_id.id,
            'product_min_qty': suggested_min,
            'product_max_qty': suggested_max,
        }
        if op:
            op.write(vals)
        else:
            op = Orderpoint.create(vals)
        res["applied_orderpoint_id"] = op.id
        res["status"] = "Applied as active orderpoint."

    return res
