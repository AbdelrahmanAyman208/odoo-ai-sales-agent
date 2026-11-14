# -*- coding: utf-8 -*-
"""
Inventory Domain Tools for AI Agent.
Covers: stock on hand / forecasted lookups via _read_group, reordering rules, transfers, adjustments.

Time Complexity: O(1) queries using stock.quant aggregations.
Space Complexity: O(P) where P is products checked.
"""
from typing import Any, Dict, List
from .base import agent_tool
from .matching import find_or_disambiguate_product


@agent_tool(
    name="get_stock_availability",
    domain="inventory",
    label="Check Stock & Inventory Availability",
    description="Queries real-time quantity on hand, reserved quantity, and forecasted availability for products.",
    tier="T0",
    examples=[
        "How many units of Office Chair do we have in stock?",
        "Check availability for Desk Pro",
    ],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Product name or ID"},
        },
        "required": ["product_name_or_id"],
    },
)
def get_stock_availability(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    prod_id, p_err = find_or_disambiguate_product(env, args["product_name_or_id"], allow_create=False)
    if p_err:
        return {"success": False, **p_err}

    product = env["product.product"].browse(prod_id)

    # Use _read_group on stock.quant for O(1) aggregation per Odoo 20 standard
    quant_groups = env["stock.quant"]._read_group(
        domain=[
            ("product_id", "=", product.id),
            ("location_id.usage", "=", "internal"),
        ],
        groupby=["product_id"],
        aggregates=["quantity:sum", "reserved_quantity:sum"],
    )

    qty_on_hand = 0.0
    qty_reserved = 0.0
    if quant_groups:
        _, on_hand, reserved = quant_groups[0]
        qty_on_hand = on_hand or 0.0
        qty_reserved = reserved or 0.0

    qty_free = max(0.0, qty_on_hand - qty_reserved)

    return {
        "success": True,
        "product_id": product.id,
        "product_name": product.display_name,
        "qty_on_hand": qty_on_hand,
        "qty_reserved": qty_reserved,
        "qty_free": qty_free,
        "uom": product.uom_id.name,
        "tracking": product.tracking,
        "message": (
            f"Product '{product.display_name}': {qty_on_hand} {product.uom_id.name} on hand "
            f"({qty_reserved} reserved, {qty_free} available)."
        ),
    }


@agent_tool(
    name="check_inventory_replenishment",
    domain="inventory",
    label="Scan Inventory for Replenishment",
    description="Scans inventory against safety thresholds and returns low-stock items.",
    tier="T0",
    examples=["Check low stock items", "Scan inventory for replenishment"],
    parameters={
        "type": "object",
        "properties": {
            "threshold": {"type": "number", "description": "Safety threshold (default 10.0)"},
        },
    },
)
def check_inventory_replenishment(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    threshold = float(args.get("threshold", 10.0))
    Product = env["product.product"]
    products = Product.search_read(
        [("sale_ok", "=", True)],
        ["id", "name", "qty_available"],
        limit=50
    )
    low_stock = [p for p in products if p.get("qty_available", 0.0) < threshold]
    return {
        "success": True,
        "total_products_checked": len(products),
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock,
    }


@agent_tool(
    name="create_replenishment_order",
    domain="inventory",
    label="Create Replenishment Purchase Order",
    description="Creates a replenishment draft PO for a low-stock product.",
    tier="T1",
    examples=["Replenish 25 units of Desk Pro"],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Product to replenish"},
            "quantity": {"type": "number", "description": "Quantity to order"},
        },
        "required": ["product_name_or_id", "quantity"],
    },
)
def create_replenishment_order(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    prod_id, p_err = find_or_disambiguate_product(env, args["product_name_or_id"], allow_create=False)
    if p_err:
        return {"success": False, **p_err}

    product = env["product.product"].browse(prod_id)
    qty = float(args.get("quantity", 10.0))

    seller = product.seller_ids[:1]
    vendor_id = seller.partner_id.id if seller else env["res.partner"].search([("supplier_rank", ">", 0)], limit=1).id
    if not vendor_id:
        vendor_id = env["res.partner"].search([], limit=1).id

    po = env["purchase.order"].create({
        "partner_id": vendor_id,
        "origin": f"Auto-Replenishment for {product.name}",
        "order_line": [
            (0, 0, {
                "product_id": product.id,
                "product_qty": qty,
            })
        ]
    })
    return {
        "success": True,
        "po_id": po.id,
        "po_name": po.name,
        "product": product.name,
        "quantity": qty,
        "message": f"Replenishment order {po.name} created for {qty} units of {product.name}.",
    }


@agent_tool(
    name="validate_picking",
    domain="inventory",
    label="Validate Stock Transfer / Delivery / Receipt",
    description="Validates a warehouse picking (receipt or delivery). This is an irreversible inventory operation requiring human approval.",
    tier="T2",
    examples=[
        "Validate delivery order WH/OUT/00012",
        "Receive goods for incoming shipment WH/IN/00008",
    ],
    parameters={
        "type": "object",
        "properties": {
            "picking_id": {"type": "integer", "description": "Stock picking ID to validate"},
            "record_ids": {"type": "array", "items": {"type": "integer"}, "description": "Optional list of picking IDs for bulk validation"},
        },
    },
)
def validate_picking(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    picking_id = args.get("picking_id")
    picking = env["stock.picking"].browse(picking_id)
    if not picking.exists():
        return {"success": False, "error": f"Stock picking ID {picking_id} not found."}

    for move in picking.move_ids:
        if move.quantity == 0 and move.product_uom_qty > 0:
            move.quantity = move.product_uom_qty

    picking.button_validate()
    return {
        "success": True,
        "picking_id": picking.id,
        "picking_name": picking.name,
        "state": picking.state,
        "message": f"Stock picking {picking.name} validated successfully.",
    }
