# -*- coding: utf-8 -*-
"""
Purchase Domain Tools for AI Agent.
Covers: create RFQ, compare vendor offers, broadcast to suppliers, confirm PO (T2).

Time Complexity: O(1) queries for RFQ creation and supplier comparison.
Space Complexity: O(V) where V is number of suppliers compared.
"""
from typing import Any, Dict
from odoo.fields import Command
from .base import agent_tool
from .matching import find_or_disambiguate_partner, find_or_disambiguate_product


@agent_tool(
    name="create_rfq",
    domain="purchase",
    label="Create Request for Quotation (RFQ)",
    description="Creates a new draft purchase order / RFQ with vendor and product line items.",
    tier="T1",
    examples=[
        "Create RFQ for Apex Supplies for 15 Table Tops",
        "Draft purchase order for vendor WoodTech with 40 Legs",
    ],
    parameters={
        "type": "object",
        "properties": {
            "partner_name_or_id": {"type": "string", "description": "Vendor name or ID"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_name_or_id": {"type": "string", "description": "Product name or ID"},
                        "quantity": {"type": "number", "description": "Quantity to order"},
                        "price_unit": {"type": "number", "description": "Optional unit price override"},
                    },
                    "required": ["product_name_or_id", "quantity"],
                },
                "description": "Items list",
            },
            "origin": {"type": "string", "description": "Source document or reason (e.g. Replenishment)"},
        },
        "required": ["partner_name_or_id", "items"],
    },
)
def create_rfq(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    vendor_id, error = find_or_disambiguate_partner(env, args["partner_name_or_id"], allow_create=False)
    if error:
        return {"success": False, **error}

    items = args.get("items", [])
    if not items:
        return {"success": False, "error": "Cannot create RFQ with empty items list."}

    order_lines = []
    for it in items:
        prod_id, p_err = find_or_disambiguate_product(env, it["product_name_or_id"], allow_create=False)
        if p_err:
            return {"success": False, **p_err}

        line_vals = {
            "product_id": prod_id,
            "product_qty": float(it["quantity"]),
        }
        if "price_unit" in it:
            line_vals["price_unit"] = float(it["price_unit"])

        order_lines.append(Command.create(line_vals))

    vals = {
        "partner_id": vendor_id,
        "company_id": env.company.id,
        "currency_id": env.company.currency_id.id,
        "order_line": order_lines,
        "origin": args.get("origin") or "Drafted by AI Agent",
    }
    po = env["purchase.order"].create(vals)

    po_data = po.search_read(
        [("id", "=", po.id)],
        ["id", "name", "amount_total", "partner_id", "state"]
    )[0]

    return {
        "success": True,
        "po_id": po.id,
        "po_name": po_data["name"],
        "vendor_name": po_data["partner_id"][1],
        "amount_total": po_data["amount_total"],
        "state": po_data["state"],
        "message": f"RFQ {po_data['name']} created successfully for vendor {po_data['partner_id'][1]}.",
    }


@agent_tool(
    name="compare_vendor_offers",
    domain="purchase",
    label="Compare Vendor Offers & Supplier Prices",
    description="Analyzes supplierinfo records and existing RFQs for a product to find lowest price and fastest lead time.",
    tier="T0",
    examples=[
        "Compare vendor offers for Desk Pro",
        "Which supplier is cheapest for Table Top?",
    ],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Product name or ID to compare"},
            "quantity": {"type": "number", "description": "Target purchase quantity (default 1)"},
        },
        "required": ["product_name_or_id"],
    },
)
def compare_vendor_offers(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    prod_id, p_err = find_or_disambiguate_product(env, args["product_name_or_id"], allow_create=False)
    if p_err:
        return {"success": False, **p_err}

    product = env["product.product"].browse(prod_id)
    target_qty = float(args.get("quantity", 1.0))

    # Single search_read on product.supplierinfo O(1) query
    suppliers = env["product.supplierinfo"].search_read(
        ["|", ("product_id", "=", product.id), ("product_tmpl_id", "=", product.product_tmpl_id.id)],
        ["partner_id", "price", "delay", "min_qty", "currency_id"],
        order="price asc"
    )

    if not suppliers:
        return {
            "success": True,
            "product_name": product.display_name,
            "offers_count": 0,
            "message": f"No vendor price list entries found for {product.display_name}.",
            "best_offer": None,
        }

    offers = []
    for s in suppliers:
        offers.append({
            "vendor_name": s["partner_id"][1],
            "price": s["price"],
            "lead_time_days": s["delay"],
            "min_qty": s["min_qty"],
        })

    best = offers[0]
    return {
        "success": True,
        "product_name": product.display_name,
        "target_quantity": target_qty,
        "offers_count": len(offers),
        "offers": offers,
        "best_offer": best,
        "recommendation": f"Cheapest vendor is {best['vendor_name']} at {best['price']:.2f} per unit (Lead time: {best['lead_time_days']} days).",
    }


@agent_tool(
    name="confirm_purchase_order",
    domain="purchase",
    label="Confirm Purchase Order",
    description="Confirms a draft RFQ into a binding Purchase Order. This is an irreversible financial action requiring human approval.",
    tier="T2",
    examples=[
        "Confirm purchase order P00014",
        "Approve and confirm RFQ for supplier WoodTech",
    ],
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "integer", "description": "Purchase order ID to confirm"},
            "record_ids": {"type": "array", "items": {"type": "integer"}, "description": "Optional list of PO IDs for bulk confirmation"},
        },
    },
)
def confirm_purchase_order(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    po_id = args.get("order_id")
    po = env["purchase.order"].browse(po_id)
    if not po.exists():
        return {"success": False, "error": f"Purchase Order ID {po_id} not found."}
    po.button_confirm()
    return {
        "success": True,
        "po_id": po.id,
        "po_name": po.name,
        "state": po.state,
        "message": f"Purchase Order {po.name} confirmed successfully.",
    }

