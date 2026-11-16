# -*- coding: utf-8 -*-
"""
Universal Database Inspector Tool.
Allows the AI agent to safely query database records, counts, and summaries
across core models with strict read-only guarantees.

Tier: T0 (Read-only, no human approval needed)
Complexity:
- Time: O(limit) indexed search_read
- Space: O(limit * fields) payload size
"""
import logging
from typing import Dict, Any, List
from .base import agent_tool

_logger = logging.getLogger(__name__)

# Allowed models for introspection
_ALLOWED_MODELS = {
    'sale.order': ['name', 'partner_id', 'date_order', 'amount_total', 'state'],
    'sale.order.line': ['order_id', 'product_id', 'product_uom_qty', 'price_unit', 'price_subtotal'],
    'purchase.order': ['name', 'partner_id', 'date_order', 'amount_total', 'state'],
    'stock.quant': ['product_id', 'location_id', 'quantity', 'reserved_quantity'],
    'stock.location': ['name', 'complete_name', 'usage', 'location_id'],
    'mrp.production': ['name', 'product_id', 'product_qty', 'state', 'date_start'],
    'project.project': ['name', 'partner_id', 'user_id', 'task_count'],
    'project.task': ['name', 'project_id', 'stage_id', 'user_ids', 'date_deadline'],
    'crm.lead': ['name', 'partner_id', 'stage_id', 'expected_revenue', 'probability'],
    'product.product': ['name', 'default_code', 'list_price', 'standard_price', 'qty_available'],
    'res.partner': ['name', 'email', 'phone', 'city', 'country_id'],
    'ai.agent.use.case': ['name', 'state', 'progress', 'summary', 'started_at'],
    'ai.agent.task': ['title', 'tool_name', 'state', 'result_summary', 'duration'],
}


@agent_tool(
    name="query_database_records",
    domain="general",
    label="Inspect Database Records & Counts",
    description="Safely inspects database records or counts from any core Odoo model (sale.order, mrp.production, stock.quant, project.task, etc.).",
    tier="T0",
    examples=[
        "Show latest 5 sales orders",
        "How many tasks are in progress in project 1?",
        "Check stock.quant for product Fridge 360L",
    ],
    parameters={
        "type": "object",
        "properties": {
            "model_name": {
                "type": "string",
                "description": "Technical model name (e.g. 'sale.order', 'stock.quant', 'mrp.production', 'project.task', 'product.product')",
            },
            "domain": {
                "type": "array",
                "description": "Optional search domain filter, e.g. [['state', '=', 'draft']]",
            },
            "limit": {
                "type": "integer",
                "default": 10,
                "description": "Maximum number of records to return (up to 25)",
            },
            "count_only": {
                "type": "boolean",
                "default": False,
                "description": "Return only the total matching count instead of records",
            },
        },
        "required": ["model_name"],
    },
)
def query_database_records(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    model_name = str(args.get("model_name") or "").strip().lower()

    if model_name not in _ALLOWED_MODELS:
        allowed_list = ", ".join(sorted(_ALLOWED_MODELS.keys()))
        return {
            "success": False,
            "error": f"Model '{model_name}' is not in the allowed models list. Allowed models: {allowed_list}",
        }

    if model_name not in env:
        return {"success": False, "error": f"Model '{model_name}' is not installed in this Odoo database."}

    Model = env[model_name]
    raw_domain = args.get("domain") or []
    
    # Sanitize domain to list of tuples
    domain = []
    if isinstance(raw_domain, list):
        for item in raw_domain:
            if isinstance(item, (list, tuple)) and len(item) == 3:
                domain.append(tuple(item))
            elif isinstance(item, str) and item in ('|', '&', '!'):
                domain.append(item)

    limit = min(max(1, int(args.get("limit", 10))), 25)

    try:
        total_count = Model.search_count(domain)
        if args.get("count_only"):
            return {
                "success": True,
                "model": model_name,
                "count": total_count,
                "message": f"Found {total_count} matching records in {model_name}.",
            }

        fields_to_read = _ALLOWED_MODELS[model_name]
        records = Model.search_read(domain, fields=fields_to_read, limit=limit, order='id desc')

        # Format many2one values to clean strings
        cleaned_records = []
        for rec in records:
            item = {}
            for k, v in rec.items():
                if isinstance(v, (list, tuple)) and len(v) == 2 and isinstance(v[0], int) and isinstance(v[1], str):
                    item[k] = v[1] # Display name of Many2one
                else:
                    item[k] = v
            cleaned_records.append(item)

        return {
            "success": True,
            "model": model_name,
            "total_count": total_count,
            "returned_count": len(cleaned_records),
            "records": cleaned_records,
            "message": f"Retrieved {len(cleaned_records)} of {total_count} records from {model_name}.",
        }
    except Exception as e:
        _logger.exception("Failed in query_database_records: %s", e)
        return {"success": False, "error": f"Query error: {str(e)}"}
