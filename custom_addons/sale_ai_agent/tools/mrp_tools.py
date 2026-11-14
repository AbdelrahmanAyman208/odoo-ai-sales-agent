# -*- coding: utf-8 -*-
"""
Manufacturing (MRP) Domain Tools for AI Agent.
Covers: Bill of Materials (BOM), Manufacturing Orders (MO), component availability, MTO flows.

Time Complexity: O(1) queries for BOM lines and MO creation.
Space Complexity: O(C) where C is number of components.
"""
from typing import Any, Dict
from odoo.fields import Command
from .base import agent_tool
from .matching import find_or_disambiguate_product


@agent_tool(
    name="create_bill_of_materials",
    domain="mrp",
    label="Create Bill of Materials (BOM)",
    description="Creates a new manufacturing Bill of Materials (mrp.bom) defining components and quantities for a product.",
    tier="T1",
    examples=[
        "Create BOM for Desk consisting of 1 Table Top and 4 Legs",
        "Define Bill of Materials for Custom PC",
    ],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Finished product name or ID"},
            "product_qty": {"type": "number", "description": "Quantity produced (default 1.0)"},
            "bom_type": {"type": "string", "enum": ["normal", "phantom"], "description": "BOM Type: normal (manufacture) or phantom (kit)"},
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "component_name_or_id": {"type": "string", "description": "Component product name or ID"},
                        "quantity": {"type": "number", "description": "Quantity needed"},
                    },
                    "required": ["component_name_or_id", "quantity"],
                },
                "description": "List of components with quantities",
            },
        },
        "required": ["product_name_or_id", "components"],
    },
)
def create_bill_of_materials(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    prod_id, p_err = find_or_disambiguate_product(env, args["product_name_or_id"], allow_create=False)
    if p_err:
        return {"success": False, **p_err}

    product = env["product.product"].browse(prod_id)
    components = args.get("components", [])
    if not components:
        return {"success": False, "error": "Cannot create BOM with empty components list."}

    bom_lines = []
    total_cost = 0.0

    for comp in components:
        c_query = comp["component_name_or_id"]
        c_qty = float(comp["quantity"])
        c_id, c_err = find_or_disambiguate_product(env, c_query, allow_create=False)
        if c_err:
            return {"success": False, **c_err}

        # Cycle prevention guard
        if c_id == prod_id:
            return {
                "success": False,
                "error": f"Cannot add product '{product.display_name}' as a component of its own Bill of Materials (would cause a cycle)."
            }

        comp_prod = env["product.product"].browse(c_id)
        total_cost += (comp_prod.standard_price or 0.0) * c_qty

        bom_lines.append(Command.create({
            "product_id": c_id,
            "product_qty": c_qty,
        }))

    bom_vals = {
        "product_tmpl_id": product.product_tmpl_id.id,
        "product_id": product.id,
        "product_qty": float(args.get("product_qty", 1.0)),
        "type": args.get("bom_type", "normal"),
        "bom_line_ids": bom_lines,
    }
    bom = env["mrp.bom"].create(bom_vals)

    return {
        "success": True,
        "bom_id": bom.id,
        "product_name": product.display_name,
        "components_count": len(components),
        "calculated_unit_cost": total_cost,
        "message": f"BOM created for {product.display_name} with {len(components)} components (Estimated Cost: {total_cost:.2f}).",
    }


@agent_tool(
    name="create_manufacturing_order",
    domain="mrp",
    label="Create Manufacturing Order (MO)",
    description="Creates a draft Manufacturing Order (mrp.production) for a manufactured product with an active BOM.",
    tier="T1",
    examples=[
        "Create MO for 10 Office Desks",
        "Produce 5 units of Custom PC",
    ],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Manufactured product name or ID"},
            "quantity": {"type": "number", "description": "Quantity to produce"},
        },
        "required": ["product_name_or_id", "quantity"],
    },
)
def create_manufacturing_order(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    prod_id, p_err = find_or_disambiguate_product(env, args["product_name_or_id"], allow_create=False)
    if p_err:
        return {"success": False, **p_err}

    product = env["product.product"].browse(prod_id)
    bom = env["mrp.bom"]._bom_find(product)[product]
    if not bom:
        return {
            "success": False,
            "error": f"No active Bill of Materials (BOM) found for '{product.display_name}'. Please create a BOM first.",
        }

    qty = float(args.get("quantity", 1.0))
    mo = env["mrp.production"].create({
        "product_id": product.id,
        "product_qty": qty,
        "bom_id": bom.id,
    })

    return {
        "success": True,
        "production_id": mo.id,
        "production_name": mo.name,
        "product_name": product.display_name,
        "quantity": qty,
        "state": mo.state,
        "message": f"Manufacturing Order {mo.name} created for {qty} unit(s) of {product.display_name}.",
    }


@agent_tool(
    name="confirm_mrp_production",
    domain="mrp",
    label="Confirm Manufacturing Order",
    description="Confirms a draft manufacturing order and reserves component inventory. This is a Tier 2 action requiring human approval.",
    tier="T2",
    examples=[
        "Confirm MO/00025",
        "Approve and confirm manufacturing order for Desk",
    ],
    parameters={
        "type": "object",
        "properties": {
            "production_id": {"type": "integer", "description": "Manufacturing Order ID to confirm"},
            "record_ids": {"type": "array", "items": {"type": "integer"}, "description": "Optional list of MO IDs for bulk confirmation"},
        },
    },
)
def confirm_mrp_production(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    mo_id = args.get("production_id")
    mo = env["mrp.production"].browse(mo_id)
    if not mo.exists():
        return {"success": False, "error": f"Manufacturing Order ID {mo_id} not found."}
    mo.action_confirm()
    return {
        "success": True,
        "production_id": mo.id,
        "production_name": mo.name,
        "state": mo.state,
        "message": f"Manufacturing Order {mo.name} confirmed successfully.",
    }

