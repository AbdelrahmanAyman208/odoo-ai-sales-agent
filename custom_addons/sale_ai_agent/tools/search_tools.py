# -*- coding: utf-8 -*-
"""
Search and Lookup Tools for Products and Partners.
"""
from typing import Any, Dict
from .base import agent_tool
from .matching import find_or_disambiguate_partner, find_or_disambiguate_product


@agent_tool(
    name="search_products",
    domain="inventory",
    label="Search Products",
    description="Search products in catalog by name or SKU code.",
    tier="T0",
    examples=["Find product Desk", "Search catalog for Chair"],
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword or SKU"},
            "limit": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    },
)
def search_products(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    query = (args.get("query") or "").strip()
    limit = int(args.get("limit", 5))
    Product = env["product.product"]
    domain = ["|", ("name", "ilike", query), ("default_code", "ilike", query)]
    matches = Product.search_read(
        domain,
        ["id", "name", "default_code", "list_price", "qty_available"],
        limit=limit
    )
    return {
        "success": True,
        "query": query,
        "count": len(matches),
        "products": matches,
    }


@agent_tool(
    name="search_partner",
    domain="sales",
    label="Search Customers / Partners",
    description="Search contacts and customers by name, email, or phone.",
    tier="T0",
    examples=["Find customer ACME", "Search partner by email"],
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Customer name, email, or phone"},
            "limit": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    },
)
def search_partner(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    query = (args.get("query") or "").strip()
    limit = int(args.get("limit", 5))
    Partner = env["res.partner"]
    domain = ["|", "|", ("name", "ilike", query), ("email", "ilike", query), ("phone", "ilike", query)]
    matches = Partner.search_read(
        domain,
        ["id", "name", "email", "phone", "is_company"],
        limit=limit
    )
    return {
        "success": True,
        "query": query,
        "count": len(matches),
        "partners": matches,
    }


@agent_tool(
    name="create_product",
    domain="inventory",
    label="Create Product",
    description="Creates a new product in the catalog with price, cost, storable setting, tracking, and optional routes (Buy, Manufacture).",
    tier="T1",
    examples=[
        "Create product Table Top with cost 50 and price 100",
        "Create product Ergonomic Standing Desk Pro with sales price $450 and enable Track Inventory",
        "Create raw material Steel Leg with cost 15",
    ],
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Product name (e.g. 'Table Top', 'Steel Leg')"},
            "default_code": {"type": "string", "description": "Internal reference or SKU code"},
            "list_price": {"type": "number", "description": "Sales price (default 0.0)"},
            "standard_price": {"type": "number", "description": "Cost price (default 0.0)"},
            "is_storable": {"type": "boolean", "description": "True for storable inventory items (default True)", "default": True},
            "tracking": {"type": "string", "enum": ["none", "lot", "serial"], "description": "Tracking mode: none, lot, or serial (default none)"},
            "routes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of route names: 'buy', 'manufacture', 'mto'",
            },
        },
        "required": ["name"],
    },
)
def create_product(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    name = (args.get("name") or "").strip()
    if not name:
        return {"success": False, "error": "Product name cannot be empty."}

    # Check if product with this exact name already exists
    Product = env["product.product"]
    existing = Product.search([("name", "=", name)], limit=1)
    if existing:
        return {
            "success": True,
            "product_id": existing.id,
            "product_tmpl_id": existing.product_tmpl_id.id,
            "name": existing.name,
            "list_price": existing.list_price,
            "already_exists": True,
            "message": f"Product '{existing.name}' already exists (ID: {existing.id}).",
        }

    is_storable = args.get("is_storable", True)
    tracking = args.get("tracking")
    tracking_val = tracking if tracking in ("lot", "serial") else False

    vals = {
        "name": name,
        "is_storable": bool(is_storable),
        "list_price": float(args.get("list_price", 0.0)),
        "standard_price": float(args.get("standard_price", 0.0)),
    }
    if tracking_val:
        vals["tracking"] = tracking_val
    if args.get("default_code"):
        vals["default_code"] = str(args.get("default_code")).strip()

    # Route assignments
    routes_arg = args.get("routes", [])
    if routes_arg:
        route_records = []
        Route = env["stock.route"]
        for r_name in routes_arg:
            r_clean = r_name.strip().lower()
            if "buy" in r_clean:
                r_found = Route.search([("name", "ilike", "Buy")], limit=1)
                if r_found:
                    route_records.append(r_found.id)
            elif "manufactur" in r_clean:
                r_found = Route.search([("name", "ilike", "Manufacture")], limit=1)
                if r_found:
                    route_records.append(r_found.id)
            elif "mto" in r_clean or "order" in r_clean:
                r_found = Route.search([("name", "ilike", "Replenish on Order")], limit=1)
                if r_found:
                    route_records.append(r_found.id)
        if route_records:
            vals["route_ids"] = [(6, 0, list(set(route_records)))]

    try:
        new_prod = Product.create(vals)
        return {
            "success": True,
            "product_id": new_prod.id,
            "product_tmpl_id": new_prod.product_tmpl_id.id,
            "name": new_prod.name,
            "list_price": new_prod.list_price,
            "standard_price": new_prod.standard_price,
            "is_storable": new_prod.is_storable,
            "tracking": new_prod.tracking or "none",
            "message": f"Successfully created product '{new_prod.name}' (ID: {new_prod.id}, Storable: {new_prod.is_storable}).",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed creating product '{name}': {str(e)}"}

