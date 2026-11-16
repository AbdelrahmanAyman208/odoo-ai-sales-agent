# -*- coding: utf-8 -*-
"""
Advanced Manufacturing & Costing Macro Tools (Addendum 4 & Phase 5 Replaced).
Spec-First Macro Tools:
- `mrp_setup_production_from_spec`: Batched BOM + Operations + Work Centers build
- `mrp_cost_workcenter`: Labor, power/electricity, depreciation, rent/utilities -> ai.cost.profile
- `mrp_cost_rollup`: Standard vs actual comparison & target margin pricing table
"""
import json
import logging
from typing import Dict, Any, List, Tuple
from odoo import Command
from .base import agent_tool
from ..services.pipeline_engine import execute_pipeline
from ..services.product_resolver import find_or_disambiguate_product

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# 1. WORK CENTER COSTING SPEC & AUDIT PROFILE
# ---------------------------------------------------------
@agent_tool(
    name="mrp_cost_workcenter",
    domain="mrp",
    label="Work Center Cost Calculation (Labor + Power + Overhead)",
    description="Calculates comprehensive work center hourly processing cost factoring labor, machine kW x electricity tariff, depreciation, and rent/utilities. Records auditable ai.cost.profile.",
    tier="T1",
    examples=["Cost work center: 2 workers at $15/hr, 7.5 kW machine, $0.15/kWh electricity, $5 depreciation"],
    parameters={
        "type": "object",
        "properties": {
            "workcenter_name": {"type": "string", "description": "Name of work center to create or update"},
            "workers_count": {"type": "integer", "default": 1},
            "hourly_wage_per_worker": {"type": "number", "default": 20.0},
            "machine_power_kw": {"type": "number", "default": 5.0, "description": "Power rating in kW"},
            "electricity_tariff": {"type": "number", "default": 0.15, "description": "Cost per kWh"},
            "machine_depreciation_hour": {"type": "number", "default": 5.0, "description": "Depreciation cost per hour"},
            "rent_utilities_hour": {"type": "number", "default": 4.0, "description": "Rent and facilities allocation per hour"},
            "consumables_maintenance_hour": {"type": "number", "default": 2.0},
            "apply_to_workcenter": {"type": "boolean", "default": True, "description": "Write computed costs_hour to mrp.workcenter"},
        },
        "required": ["workcenter_name"],
    },
)
def mrp_cost_workcenter(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    wc_name = args["workcenter_name"].strip()
    Workcenter = env['mrp.workcenter']
    CostProfile = env['ai.cost.profile']

    workers = int(args.get("workers_count", 1))
    wage = float(args.get("hourly_wage_per_worker", 20.0))
    labor_cost = workers * wage

    kw = float(args.get("machine_power_kw", 0.0))
    tariff = float(args.get("electricity_tariff", 0.15))
    electricity_cost = kw * tariff

    deprec = float(args.get("machine_depreciation_hour", 0.0))
    rent = float(args.get("rent_utilities_hour", 0.0))
    consumables = float(args.get("consumables_maintenance_hour", 0.0))

    total_cost_hour = round(labor_cost + electricity_cost + deprec + rent + consumables, 2)

    # Find or create workcenter
    wc = Workcenter.search([('name', '=', wc_name)], limit=1)
    if not wc:
        wc = Workcenter.create({
            'name': wc_name,
            'costs_hour': total_cost_hour if args.get("apply_to_workcenter", True) else 0.0,
            'company_id': env.company.id,
        })
    else:
        if args.get("apply_to_workcenter", True):
            wc.write({'costs_hour': total_cost_hour})

    # Create auditable cost profile record
    profile = CostProfile.create({
        'workcenter_id': wc.id,
        'labor_cost_hour': labor_cost,
        'power_kw': kw,
        'electricity_tariff': tariff,
        'depreciation_cost_hour': deprec,
        'rent_utilities_hour': rent,
        'consumables_hour': consumables,
        'components_json': json.dumps(args),
        'notes': f"Calculated by AI Agent: {workers} worker(s) @ ${wage}/hr, {kw}kW @ ${tariff}/kWh",
    })

    return {
        "success": True,
        "workcenter_id": wc.id,
        "workcenter_name": wc.name,
        "computed_costs_hour": total_cost_hour,
        "cost_profile_id": profile.id,
        "breakdown": {
            "labor": f"{workers} workers x ${wage}/hr = ${labor_cost:.2f}/hr",
            "electricity": f"{kw} kW x ${tariff}/kWh = ${electricity_cost:.2f}/hr",
            "depreciation": f"${deprec:.2f}/hr",
            "rent_utilities": f"${rent:.2f}/hr",
            "consumables_maintenance": f"${consumables:.2f}/hr",
            "total_hourly_rate": f"${total_cost_hour:.2f}/hr",
        },
        "message": f"Work Center '{wc.name}' cost profile generated: ${total_cost_hour:.2f}/hour.",
    }


# ---------------------------------------------------------
# 2. COMPLETE MRP SETUP FROM SPEC (BOM + OPERATIONS + WORKCENTERS)
# ---------------------------------------------------------
@agent_tool(
    name="mrp_setup_production_from_spec",
    domain="mrp",
    label="Build Complete Manufacturing Flow from Spec",
    description="Batched creation of finished product, raw components, work centers, routing operations, and Bill of Materials.",
    tier="T1",
    examples=["Setup Fridge manufacturing flow with 3 operations and BOM components"],
    parameters={
        "type": "object",
        "properties": {
            "product_name": {"type": "string", "description": "Finished product name"},
            "sale_price": {"type": "number", "default": 1000.0},
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "qty": {"type": "number", "default": 1.0},
                        "cost": {"type": "number", "default": 50.0},
                    },
                    "required": ["name"],
                },
            },
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "workcenter_name": {"type": "string"},
                        "duration_minutes": {"type": "number", "default": 30.0},
                    },
                    "required": ["name", "workcenter_name"],
                },
            },
        },
        "required": ["product_name", "components"],
    },
)
def mrp_setup_production_from_spec(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    Product = env['product.product']
    Workcenter = env['mrp.workcenter']
    Bom = env['mrp.bom']

    # 1. Finished Product
    p_name = args["product_name"].strip()
    fin_prod = Product.search([('name', '=', p_name)], limit=1)
    if not fin_prod:
        fin_prod = Product.create({
            'name': p_name,
            'is_storable': True,
            'list_price': float(args.get("sale_price", 1000.0)),
        })

    # 2. Raw Components in batch
    comp_lines = []
    total_materials_cost = 0.0

    for c in args.get("components", []):
        c_name = c.get("name").strip()
        c_qty = float(c.get("qty", 1.0))
        c_cost = float(c.get("cost", 50.0))

        raw_prod = Product.search([('name', '=', c_name)], limit=1)
        if not raw_prod:
            raw_prod = Product.create({
                'name': c_name,
                'is_storable': True,
                'standard_price': c_cost,
            })
        total_materials_cost += (raw_prod.standard_price or c_cost) * c_qty
        comp_lines.append(Command.create({
            'product_id': raw_prod.id,
            'product_qty': c_qty,
        }))

    # 3. Workcenters & Operations
    operation_lines = []
    total_labor_cost = 0.0

    for op in args.get("operations", []):
        wc_name = op.get("workcenter_name", "Main Workcenter").strip()
        wc = Workcenter.search([('name', '=', wc_name)], limit=1)
        if not wc:
            wc = Workcenter.create({'name': wc_name, 'costs_hour': 30.0})

        duration = float(op.get("duration_minutes", 30.0))
        total_labor_cost += (wc.costs_hour or 30.0) * (duration / 60.0)

        operation_lines.append(Command.create({
            'name': op.get("name"),
            'workcenter_id': wc.id,
            'time_cycle_manual': duration,
        }))

    # 4. Bill of Materials
    bom_vals = {
        'product_tmpl_id': fin_prod.product_tmpl_id.id,
        'product_id': fin_prod.id,
        'product_qty': 1.0,
        'bom_line_ids': comp_lines,
    }
    if operation_lines:
        bom_vals['operation_ids'] = operation_lines

    bom = Bom.create(bom_vals)
    total_unit_cost = round(total_materials_cost + total_labor_cost, 2)
    fin_prod.write({'standard_price': total_unit_cost})

    return {
        "success": True,
        "product_id": fin_prod.id,
        "product_name": fin_prod.display_name,
        "bom_id": bom.id,
        "components_count": len(comp_lines),
        "operations_count": len(operation_lines),
        "cost_rollup": {
            "materials_cost": round(total_materials_cost, 2),
            "operations_cost": round(total_labor_cost, 2),
            "total_unit_cost": total_unit_cost,
            "sale_price": fin_prod.list_price,
            "margin_amount": round(fin_prod.list_price - total_unit_cost, 2),
            "margin_percent": round(((fin_prod.list_price - total_unit_cost) / (fin_prod.list_price or 1.0)) * 100, 1),
        },
        "message": f"Complete manufacturing flow created for '{fin_prod.display_name}'. Total Unit Cost: ${total_unit_cost:.2f}.",
    }


# ---------------------------------------------------------
# 3. COST ROLLUP & TARGET MARGIN TABLE
# ---------------------------------------------------------
@agent_tool(
    name="mrp_cost_rollup",
    domain="mrp",
    label="BOM Cost Rollup & Margin Analysis",
    description="Performs hierarchical multi-level cost rollup over BOM components and work center operations with target margin pricing suggestion.",
    tier="T0",
    examples=["Cost rollup for Fridge 360L with 30% target margin"],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Finished product name or ID"},
            "target_margin_percent": {"type": "number", "default": 30.0, "description": "Target profit margin percentage"},
        },
        "required": ["product_name_or_id"],
    },
)
def mrp_cost_rollup(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    prod, disambig = find_or_disambiguate_product(env, str(args["product_name_or_id"]))
    if disambig:
        return {"success": False, "disambiguation_required": True, "candidates": disambig}
    if not prod:
        return {"success": False, "error": f"Product '{args['product_name_or_id']}' not found."}

    bom = env['mrp.bom']._bom_find(prod)[prod]
    if not bom:
        bom = env['mrp.bom'].search([('product_tmpl_id', '=', prod.product_tmpl_id.id)], limit=1)

    if not bom:
        return {"success": False, "error": f"No active Bill of Materials found for '{prod.display_name}'."}

    materials_breakdown = []
    total_materials = 0.0
    for line in bom.bom_line_ids:
        c_prod = line.product_id
        c_cost = (c_prod.standard_price or 0.0) * line.product_qty
        total_materials += c_cost
        materials_breakdown.append({
            "component": c_prod.display_name,
            "quantity": line.product_qty,
            "unit_cost": c_prod.standard_price,
            "total_cost": round(c_cost, 2),
        })

    operations_breakdown = []
    total_operations = 0.0
    for op in bom.operation_ids:
        wc = op.workcenter_id
        duration_hrs = op.time_cycle_manual / 60.0
        op_cost = (wc.costs_hour or 0.0) * duration_hrs
        total_operations += op_cost
        operations_breakdown.append({
            "operation": op.name,
            "workcenter": wc.name,
            "duration_minutes": op.time_cycle_manual,
            "hourly_rate": wc.costs_hour,
            "total_cost": round(op_cost, 2),
        })

    total_cost = round(total_materials + total_operations, 2)
    target_margin = float(args.get("target_margin_percent", 30.0)) / 100.0
    suggested_price = round(total_cost / (1.0 - target_margin), 2) if target_margin < 1.0 else total_cost * 1.5

    return {
        "success": True,
        "product_name": prod.display_name,
        "bom_reference": bom.display_name,
        "materials_total": round(total_materials, 2),
        "operations_total": round(total_operations, 2),
        "total_unit_cost": total_cost,
        "current_sale_price": prod.list_price,
        "suggested_sale_price": suggested_price,
        "target_margin_percent": args.get("target_margin_percent", 30.0),
        "materials": materials_breakdown,
        "operations": operations_breakdown,
    }
