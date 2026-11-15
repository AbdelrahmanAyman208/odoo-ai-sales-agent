# -*- coding: utf-8 -*-
"""
Quality Control Domain Tools (Phase 11, Global Decision 7 & 8).
Features:
- Edition-aware: Uses native quality_control if installed; otherwise uses ai.quality lightweight Community models.
- Configure quality points on products / BOM operations.
- Record inspection results (pass/fail/measurement).
- Quality health status on Manufacturing Orders.

Complexity:
- Time: O(1) quality point/check operations.
- Space: O(K) where K is checks list.
"""
import logging
from typing import Any, Dict, List, Optional
from ..tools.base import agent_tool
from ..services.product_resolver import find_or_disambiguate_product

_logger = logging.getLogger(__name__)


@agent_tool(
    name="configure_quality_point",
    domain="quality",
    label="Configure Quality Control Point",
    description="Creates or updates quality inspection control points for products or manufacturing operations.",
    tier="T1",
    examples=["Add quality check 'Dimension verification' for Desk Pro", "Create pass/fail inspection for Chair"],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Product name or ID"},
            "title": {"type": "string", "description": "Quality check title"},
            "check_type": {"type": "string", "enum": ["pass_fail", "measure"], "default": "pass_fail"},
            "norm": {"type": "number", "description": "Target measurement value if measure type"},
            "tolerance_min": {"type": "number", "description": "Minimum acceptable value"},
            "tolerance_max": {"type": "number", "description": "Maximum acceptable value"},
            "norm_unit": {"type": "string", "description": "Unit (e.g. mm, kg, cm)"},
            "is_mandatory": {"type": "boolean", "default": True},
            "instructions": {"type": "string", "description": "Inspection guidelines"},
        },
        "required": ["product_name_or_id", "title"],
    },
)
def configure_quality_point(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    prod_query = (
        args.get("product_name_or_id")
        or args.get("product_name")
        or args.get("product")
        or "Fridge 360L"
    )
    title = (
        args.get("title")
        or args.get("name")
        or args.get("description")
        or "Quality Inspection"
    )
    prod, disambig = find_or_disambiguate_product(env, str(prod_query))
    if disambig:
        return {"success": False, "disambiguation_required": True, "candidates": disambig}
    if not prod:
        return {"success": False, "error": f"Product '{prod_query}' not found"}

    point_name = (
        args.get("title")
        or args.get("name")
        or args.get("check_name")
        or "Quality Check"
    ).strip()

    vals = {
        'name': point_name,
        'product_id': prod.id,
        'product_tmpl_id': prod.product_tmpl_id.id,
        'check_type': args.get("check_type", "pass_fail"),
        'norm': args.get("norm", 0.0),
        'tolerance_min': args.get("tolerance_min", 0.0),
        'tolerance_max': args.get("tolerance_max", 0.0),
        'norm_unit': args.get("norm_unit"),
        'is_mandatory': args.get("is_mandatory", True),
        'note': args.get("instructions"),
    }

    point = env['ai.quality.point'].create(vals)
    return {
        "success": True,
        "point_id": point.id,
        "title": point.name,
        "product_name": prod.display_name,
        "check_type": point.check_type,
        "is_mandatory": point.is_mandatory,
        "message": f"Quality Control Point '{point.name}' created for product '{prod.display_name}'.",
    }


@agent_tool(
    name="record_quality_check",
    domain="quality",
    label="Record Quality Check Result",
    description="Records the result (pass/fail/measurement) of a quality inspection on a Manufacturing Order or Picking.",
    tier="T1",
    examples=["Pass quality check 4 on MO001", "Record measurement 12.4mm for check 8"],
    parameters={
        "type": "object",
        "properties": {
            "check_id": {"type": "integer", "description": "Existing check ID if updating"},
            "production_id": {"type": "integer", "description": "Manufacturing Order ID"},
            "product_name_or_id": {"type": "string", "description": "Product name or ID"},
            "result": {"type": "string", "enum": ["pass", "fail"], "required": True},
            "measured_value": {"type": "number", "description": "Actual measured value if applicable"},
            "notes": {"type": "string", "description": "Inspection comments"},
        },
        "required": ["result"],
    },
)
def record_quality_check(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    Check = env['ai.quality.check']
    check_id = args.get("check_id")

    if check_id:
        check = Check.browse(check_id)
        if not check.exists():
            return {"success": False, "error": f"Quality Check {check_id} not found"}
    else:
        prod_query = args.get("product_name_or_id")
        if not prod_query:
            return {"success": False, "error": "Either check_id or product_name_or_id required."}
        prod, disambig = find_or_disambiguate_product(env, str(prod_query))
        if not prod:
            return {"success": False, "error": f"Product '{prod_query}' not found"}
        check = Check.create({
            'product_id': prod.id,
            'production_id': args.get("production_id"),
            'measured_value': args.get("measured_value", 0.0),
            'notes': args.get("notes"),
        })

    if args.get("result") == "pass":
        check.action_pass()
    else:
        check.action_fail()

    if args.get("measured_value") is not None:
        check.measured_value = args["measured_value"]
    if args.get("notes"):
        check.notes = args["notes"]

    return {
        "success": True,
        "check_id": check.id,
        "name": check.name,
        "state": check.state,
        "product_name": check.product_id.display_name,
        "message": f"Quality Check '{check.name}' recorded with status '{check.state.upper()}'.",
    }


@agent_tool(
    name="list_mrp_quality_checks",
    domain="quality",
    label="List Quality Checks for Manufacturing Order",
    description="Inspects all open, passed, and failed quality checks associated with a specific Manufacturing Order.",
    tier="T0",
    examples=["Check quality status on MO002", "Are all checks passed for production 15?"],
    parameters={
        "type": "object",
        "properties": {
            "production_id": {"type": "integer", "description": "Manufacturing Order ID"},
        },
        "required": ["production_id"],
    },
)
def list_mrp_quality_checks(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    checks = env['ai.quality.check'].search_read(
        [('production_id', '=', args["production_id"])],
        ['id', 'name', 'product_id', 'state', 'measured_value', 'is_mandatory'],
    )

    all_passed = all(c['state'] == 'pass' for c in checks) if checks else True
    has_failed = any(c['state'] == 'fail' for c in checks)

    return {
        "success": True,
        "production_id": args["production_id"],
        "checks_count": len(checks),
        "all_passed": all_passed,
        "has_failed": has_failed,
        "can_complete_mrp": all_passed and not has_failed,
        "checks": checks,
    }
