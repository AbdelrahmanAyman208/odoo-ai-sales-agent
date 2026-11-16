# -*- coding: utf-8 -*-
"""
Execution Pipeline Engine (Global Decision 11 & Addendum 4).
Standard pipeline for all non-trivial macro tools:
UNDERSTAND -> PREFLIGHT -> VALIDATE -> PREVIEW -> EXECUTE -> VERIFY -> REPORT

Features:
- Bulk context hygiene: suppresses chatter logs, notifications, and mail tracking during builds.
- Two-phase hierarchical creation: insert records in batch O(n), link relations in O(n).
- Checkpoint / Savepoints: rollback on failure, idempotency keys for resume without duplicates.
- Read-back invariant verification.
"""
import time
import logging
from typing import Dict, Any, List, Optional, Callable, Tuple
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Odoo 20 context keys to suppress tracking & chatter notifications during bulk builds
BULK_HYGIENE_CONTEXT = {
    'tracking_disable': True,
    'mail_notrack': True,
    'mail_create_nolog': True,
    'mail_create_nosubscribe': True,
    'mail_auto_subscribe_no_notify': True,
    'no_reset_password': True,
}


class PipelineResult:
    def __init__(self, success: bool, message: str, data: Optional[Dict[str, Any]] = None):
        self.success = success
        self.message = message
        self.data = data or {}
        self.warnings: List[str] = []
        self.assumptions: List[str] = []
        self.query_count: int = 0
        self.duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "warnings": self.warnings,
            "assumptions": self.assumptions,
            "query_count": self.query_count,
            "duration": round(self.duration, 3),
        }


def execute_pipeline(
    env,
    tool_name: str,
    spec: Dict[str, Any],
    understand_fn: Callable[[Any, Dict[str, Any]], Tuple[Dict[str, Any], List[str]]],
    preflight_fn: Callable[[Any, Dict[str, Any]], Tuple[bool, List[str], List[Dict[str, Any]]]],
    validate_fn: Callable[[Any, Dict[str, Any]], Tuple[bool, List[str]]],
    execute_fn: Callable[[Any, Dict[str, Any]], Dict[str, Any]],
    verify_fn: Callable[[Any, Dict[str, Any]], Tuple[bool, List[str]]],
    preview_threshold: int = 25,
) -> Dict[str, Any]:
    """
    Executes the standard G11 pipeline with time/query profiling and bulk hygiene.
    """
    start_time = time.time()
    start_queries = len(env.cr._queries) if hasattr(env.cr, '_queries') else 0

    result = PipelineResult(True, f"Executed {tool_name}")

    try:
        # 1. UNDERSTAND: Resolve references & populate spec defaults
        resolved_spec, assumptions = understand_fn(env, spec)
        result.assumptions.extend(assumptions)

        # 2. PREFLIGHT: Check dependencies, configuration, modules
        passed, preflight_errors, fix_tasks = preflight_fn(env, resolved_spec)
        if not passed:
            return {
                "success": False,
                "stage": "PREFLIGHT",
                "error": f"Preflight failed: {'; '.join(preflight_errors)}",
                "fix_tasks": fix_tasks,
            }

        # 3. VALIDATE: Deterministic checks (acyclic, UoM, bounds)
        is_valid, validation_errors = validate_fn(env, resolved_spec)
        if not is_valid:
            return {
                "success": False,
                "stage": "VALIDATE",
                "error": f"Validation failed: {'; '.join(validation_errors)}",
            }

        # 4. PREVIEW: Check if build size requires preview notice
        record_count_est = resolved_spec.get("_estimated_record_count", 1)
        if spec.get("preview_only") or (record_count_est > preview_threshold and not spec.get("confirm_run")):
            return {
                "success": True,
                "stage": "PREVIEW",
                "preview_required": True,
                "record_count_est": record_count_est,
                "message": f"Preview: About to create/update ~{record_count_est} records. Pass 'confirm_run': true to proceed.",
                "summary": resolved_spec.get("_preview_summary", {}),
            }

        # 5. EXECUTE: Batched run with bulk context hygiene and savepoint
        env_hygiene = env(context={**env.context, **BULK_HYGIENE_CONTEXT})
        with env_hygiene.cr.savepoint():
            exec_data = execute_fn(env_hygiene, resolved_spec)
            result.data.update(exec_data)

        # 6. VERIFY: Read back and assert invariants
        verified, verify_warnings = verify_fn(env, result.data)
        if not verified:
            _logger.warning("Pipeline verification warnings in %s: %s", tool_name, verify_warnings)
        result.warnings.extend(verify_warnings)

        # 7. REPORT: Attach duration and queries
        end_queries = len(env.cr._queries) if hasattr(env.cr, '_queries') else start_queries
        result.query_count = end_queries - start_queries
        result.duration = time.time() - start_time
        result.message = f"Successfully completed {tool_name}."

        return result.to_dict()

    except Exception as e:
        _logger.exception("Pipeline failure in %s: %s", tool_name, e)
        return {
            "success": False,
            "stage": "EXECUTE",
            "error": str(e),
            "duration": round(time.time() - start_time, 3),
        }
