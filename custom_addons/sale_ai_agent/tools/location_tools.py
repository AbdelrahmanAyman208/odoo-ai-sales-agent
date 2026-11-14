# -*- coding: utf-8 -*-
"""
Inventory Location and Internal Transfer Tools for AI Agent.
Covers: warehouse/location inspection, multi-location stock lookups, internal transfers across stores.

Time Complexity: O(1) queries using stock.quant aggregations.
Space Complexity: O(L) locations list.
"""
from typing import Any, Dict, List
from odoo.fields import Command
from .base import agent_tool
from .matching import find_or_disambiguate_product


@agent_tool(
    name="get_stock_by_locations",
    domain="inventory",
    label="Check Stock Across Specific Locations / Stores",
    description="Queries stock on hand for a product broken down across multiple warehouse stores or locations.",
    tier="T0",
    examples=[
        "Check stock of Office Chair in Store 1 vs Store 2",
        "Where is Desk located across warehouses?",
    ],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Product name or ID"},
        },
        "required": ["product_name_or_id"],
    },
)
def get_stock_by_locations(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    prod_id, p_err = find_or_disambiguate_product(env, args["product_name_or_id"], allow_create=False)
    if p_err:
        return {"success": False, **p_err}

    product = env["product.product"].browse(prod_id)

    quant_groups = env["stock.quant"]._read_group(
        domain=[
            ("product_id", "=", product.id),
            ("location_id.usage", "=", "internal"),
        ],
        groupby=["location_id"],
        aggregates=["quantity:sum", "reserved_quantity:sum"],
    )

    locations_breakdown = []
    total_qty = 0.0

    for loc_rec, on_hand, reserved in quant_groups:
        qty = on_hand or 0.0
        res = reserved or 0.0
        total_qty += qty
        locations_breakdown.append({
            "location_id": loc_rec.id,
            "location_name": loc_rec.display_name,
            "qty_on_hand": qty,
            "qty_reserved": res,
            "qty_available": max(0.0, qty - res),
        })

    return {
        "success": True,
        "product_id": product.id,
        "product_name": product.display_name,
        "total_on_hand": total_qty,
        "locations": locations_breakdown,
        "message": f"Product '{product.display_name}' has {total_qty} units distributed across {len(locations_breakdown)} location(s).",
    }


@agent_tool(
    name="create_internal_transfer",
    domain="inventory",
    label="Create Internal Transfer Between Stores/Locations",
    description="Creates a stock picking transfer moving items from a source location (e.g. Store 1 / Central Warehouse) to a destination location (e.g. Store 2 / Production Floor).",
    tier="T1",
    examples=[
        "Transfer 10 Chairs from Central Warehouse to Store 2",
        "Move 5 Desk Tops from WH/Stock to Store 1",
    ],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Product name or ID"},
            "quantity": {"type": "number", "description": "Quantity to transfer"},
            "source_location": {"type": "string", "description": "Source location name or ID (default main internal stock)"},
            "dest_location": {"type": "string", "description": "Destination location name or ID"},
        },
        "required": ["product_name_or_id", "quantity", "dest_location"],
    },
)
def create_internal_transfer(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    prod_id, p_err = find_or_disambiguate_product(env, args["product_name_or_id"], allow_create=False)
    if p_err:
        return {"success": False, **p_err}

    product = env["product.product"].browse(prod_id)
    qty = float(args["quantity"])

    # Resolve locations
    Location = env["stock.location"]
    src_query = args.get("source_location")
    if src_query:
        src_loc = Location.search([("name", "ilike", src_query), ("usage", "=", "internal")], limit=1)
    else:
        src_loc = Location.search([("usage", "=", "internal")], limit=1)

    dest_query = args.get("dest_location")
    dest_loc = Location.search([("name", "ilike", dest_query), ("usage", "=", "internal")], limit=1)

    if not src_loc:
        return {"success": False, "error": f"Source location '{src_query}' not found."}
    if not dest_loc:
        return {"success": False, "error": f"Destination location '{dest_query}' not found."}

    # Internal picking type
    picking_type = env["stock.picking.type"].search([("code", "=", "internal")], limit=1)
    if not picking_type:
        picking_type = env["stock.picking.type"].search([], limit=1)

    transfer = env["stock.picking"].create({
        "picking_type_id": picking_type.id,
        "location_id": src_loc.id,
        "location_dest_id": dest_loc.id,
        "origin": f"AI Internal Transfer to {dest_loc.name}",
        "move_ids": [
            Command.create({
                "name": f"Transfer {product.name}",
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": src_loc.id,
                "location_dest_id": dest_loc.id,
            })
        ]
    })

    return {
        "success": True,
        "transfer_id": transfer.id,
        "transfer_name": transfer.name,
        "product_name": product.display_name,
        "quantity": qty,
        "source": src_loc.display_name,
        "destination": dest_loc.display_name,
        "state": transfer.state,
        "message": f"Internal transfer {transfer.name} created moving {qty} units of {product.name} from {src_loc.name} to {dest_loc.name}.",
    }

