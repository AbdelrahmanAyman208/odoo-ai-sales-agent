# -*- coding: utf-8 -*-
"""
Shared Approval Service (Global Decision 6 & 8).
Manages T2 human approvals, snapshot hashing, and target record routing.

Complexity:
- Time: O(R) where R is record count (bounded by max_records <= 50).
- Space: O(R) JSON snapshot.
"""
import json
import logging
from typing import Dict, Any, Optional

_logger = logging.getLogger(__name__)


def create_approval_request(env, meta: Dict[str, Any], args: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Creates an ai.agent.approval record instead of executing T2 action directly.
    """
    tool_name = meta["name"]
    res_model = args.get("res_model")
    record_ids = args.get("record_ids") or []

    if not record_ids and args.get("order_id"):
        record_ids = [args.get("order_id")]
        res_model = res_model or ("sale.order" if "sale" in tool_name else "purchase.order")
    elif not record_ids and args.get("picking_id"):
        record_ids = [args.get("picking_id")]
        res_model = res_model or "stock.picking"
    elif not record_ids and args.get("production_id"):
        record_ids = [args.get("production_id")]
        res_model = res_model or "mrp.production"
    elif not record_ids and args.get("program_id"):
        record_ids = [args.get("program_id")]
        res_model = res_model or "loyalty.program"

    if not res_model or not record_ids:
        return {
            "success": False,
            "error": f"T2 tool '{tool_name}' requires concrete target records (res_model and record_ids)."
        }

    # Hard cap check
    ICP = env['ir.config_parameter'].sudo()
    max_records = ICP.get_int('sale_ai_agent.approval_max_records', 50)
    if len(record_ids) > max_records:
        return {
            "success": False,
            "error": f"Records count ({len(record_ids)}) exceeds the maximum allowed approval limit of {max_records}."
        }

    Approval = env['ai.agent.approval']
    try:
        snap_hash, rec_display, total_amount, currency_id = Approval.compute_snapshot_hash(
            res_model, record_ids
        )
    except Exception as e:
        return {"success": False, "error": f"Failed computing snapshot for approval: {str(e)}"}

    instruction = (context or {}).get("instruction") or f"Execute {meta.get('label', tool_name)} on {len(record_ids)} records"
    use_case_id = (context or {}).get("use_case_id")
    task_id = (context or {}).get("task_id")

    approval = Approval.create({
        'use_case_id': use_case_id,
        'task_id': task_id,
        'tool_name': tool_name,
        'request_text': instruction[:200],
        'res_model': res_model,
        'record_ids_json': json.dumps(record_ids),
        'records_display_json': json.dumps(rec_display),
        'total_amount': total_amount,
        'currency_id': currency_id,
        'snapshot_hash': snap_hash,
    })

    return {
        "success": True,
        "approval_required": True,
        "approval_id": approval.id,
        "approval_name": approval.name,
        "tool_name": tool_name,
        "records_count": len(record_ids),
        "total_amount": total_amount,
        "currency": approval.currency_id.symbol if approval.currency_id else '',
        "message": (
            f"Action '{meta.get('label', tool_name)}' is a critical operation (Tier 2) and requires human approval. "
            f"Approval record '{approval.name}' has been created for {len(record_ids)} record(s). "
            "Click on the approval record to review and confirm."
        ),
    }
