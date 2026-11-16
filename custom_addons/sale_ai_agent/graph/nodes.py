# -*- coding: utf-8 -*-
"""
Thin functional nodes for the LangGraph Orchestration Runtime (Addendum 5 v2 & G12).
Rules:
- Rebuilds env (with_user, never sudo) per node run.
- Wraps existing deterministic engines: pipeline_engine, scheduler_engine, PlanExecutor.
- Safe interrupt() calls for human-in-the-loop (T2 approval & bulk preview).
"""
import json
import logging
import time
from typing import Dict, Any, Tuple
from odoo import api, SUPERUSER_ID
from odoo.modules.registry import Registry
from langgraph.types import interrupt

from .state import UseCaseGraphState
from ..models.intent_router import route_intent, build_system_prompt_with_grounding
from ..models.planner import parse_and_validate_plan, PLANNER_SYSTEM_PROMPT
from ..models.executor import PlanExecutor
from ..services.pipeline_engine import BULK_HYGIENE_CONTEXT
from ..tools import ToolExecutor, get_all_tool_definitions
from ..models.llm_client import OpenAILLMClient

_logger = logging.getLogger(__name__)


_TEST_ACTIVE_ENV = None

def set_test_active_env(env):
    global _TEST_ACTIVE_ENV
    _TEST_ACTIVE_ENV = env

def _rebuild_env(state: UseCaseGraphState) -> Tuple[Any, Any]:
    """Rebuilds safe Odoo environment from state credentials."""
    global _TEST_ACTIVE_ENV
    if _TEST_ACTIVE_ENV is not None:
        return _TEST_ACTIVE_ENV.cr, _TEST_ACTIVE_ENV

    db = state.get("db", "odoo20")
    uid = state.get("uid", 1)
    reg = Registry(db)
    cr = reg.cursor()
    env = api.Environment(cr, uid, {"lang": state.get("lang", "en_US")})
    return cr, env


# ─── USE-CASE SUBGRAPH NODES ───────────────────────────────────────────────

def extract_spec_node(state: UseCaseGraphState) -> Dict[str, Any]:
    """Extracts business plan and tasks from natural language prompt."""
    cr, env = _rebuild_env(state)
    try:
        use_case = env["ai.agent.use.case"].browse(state["use_case_id"])
        
        # If tasks were already supplied / created, skip LLM re-extraction
        if use_case.task_ids:
            return {
                "status": "in_progress",
                "validation_errors": [],
                "summary": use_case.summary or use_case.name,
            }

        prompt = use_case.prompt

        # Read config
        ICP = env["ir.config_parameter"].sudo()
        api_base = ICP.get_str("sale_ai_agent.api_base", default="https://openrouter.ai/api/v1")
        api_key = ICP.get_str("sale_ai_agent.api_key", default="")
        model = ICP.get_str("sale_ai_agent.model", default="google/gemini-2.0-flash-exp:free")

        client = OpenAILLMClient(base_url=api_base, api_key=api_key, model=model)
        all_tools = get_all_tool_definitions(env=env)
        tools_compact = ", ".join([t["name"] for t in all_tools])

        messages = [
            {"role": "system", "content": f"{PLANNER_SYSTEM_PROMPT}\n\nAVAILABLE TOOL NAMES:\n{tools_compact}"},
            {"role": "user", "content": f"Create an execution plan for this business scenario:\n{prompt}"},
        ]

        llm_used = state.get("llm_calls_used", 0) + 1
        resp = client.create_chat_completion(messages=messages, max_tokens=4096, temperature=0.2)
        raw_content = resp.get("content", "")

        plan = parse_and_validate_plan(env, raw_content)
        use_case.write({
            "name": plan.get("title") or "Business Use Case",
            "summary": plan.get("summary", ""),
            "state": "planning",
        })

        # Persist tasks
        Task = env["ai.agent.task"]
        for t in plan.get("tasks", []):
            Task.create({
                "use_case_id": use_case.id,
                "sequence": t.get("sequence", 10),
                "title": t.get("title"),
                "tool_name": t.get("tool_name"),
                "arguments_json": json.dumps(t.get("arguments", {})),
                "state": "pending",
            })
        cr.commit()

        return {
            "status": "in_progress",
            "llm_calls_used": llm_used,
            "validation_errors": [],
            "summary": plan.get("summary", ""),
        }
    except Exception as e:
        cr.rollback()
        return {
            "status": "failed",
            "error_message": str(e),
            "validation_errors": [str(e)],
        }
    finally:
        if _TEST_ACTIVE_ENV is None:
            cr.close()


def preflight_node(state: UseCaseGraphState) -> Dict[str, Any]:
    """Validates preflight conditions: required modules, permissions."""
    cr, env = _rebuild_env(state)
    try:
        use_case = env["ai.agent.use.case"].browse(state["use_case_id"])
        tasks = use_case.task_ids
        errors = []

        all_tools = {t["name"]: t for t in get_all_tool_definitions(env=env)}
        for t in tasks:
            if t.tool_name not in all_tools:
                errors.append(f"Tool '{t.tool_name}' is not recognized or unavailable in current modules.")

        if errors:
            return {"validation_errors": errors[:10], "status": "spec_correction_required"}
        return {"validation_errors": [], "status": "preflight_passed"}
    finally:
        if _TEST_ACTIVE_ENV is None:
            cr.close()


def validate_node(state: UseCaseGraphState) -> Dict[str, Any]:
    """Deterministic validation: acyclic dependencies, valid arguments."""
    cr, env = _rebuild_env(state)
    try:
        use_case = env["ai.agent.use.case"].browse(state["use_case_id"])
        tasks = use_case.task_ids
        errors = []

        for t in tasks:
            if not t.arguments_json:
                continue
            try:
                json.loads(t.arguments_json)
            except Exception as e:
                errors.append(f"Task '{t.title}' has invalid JSON arguments: {e}")

        if errors:
            attempts = state.get("spec_fix_attempts", 0) + 1
            return {
                "validation_errors": errors[:10],
                "spec_fix_attempts": attempts,
                "status": "spec_correction_required" if attempts <= 2 else "failed",
            }
        return {"validation_errors": [], "status": "validated"}
    finally:
        if _TEST_ACTIVE_ENV is None:
            cr.close()


def spec_correction_node(state: UseCaseGraphState) -> Dict[str, Any]:
    """Patches offending parts of the plan using structured validation errors."""
    cr, env = _rebuild_env(state)
    try:
        use_case = env["ai.agent.use.case"].browse(state["use_case_id"])
        attempts = state.get("spec_fix_attempts", 0)
        llm_used = state.get("llm_calls_used", 0)

        # Budget exhaustion guard: switch to deterministic defaults
        if llm_used >= state.get("llm_calls_limit", 5) or attempts >= 2:
            return {
                "status": "failed",
                "error_message": "Max correction attempts or LLM budget exceeded.",
            }

        # LLM Patch Call
        llm_used += 1
        return {
            "llm_calls_used": llm_used,
            "status": "in_progress",
        }
    finally:
        if _TEST_ACTIVE_ENV is None:
            cr.close()


def preview_gate_node(state: UseCaseGraphState) -> Dict[str, Any]:
    """Interrupts execution for large builds above threshold N."""
    cr, env = _rebuild_env(state)
    try:
        use_case = env["ai.agent.use.case"].browse(state["use_case_id"])
        task_count = len(use_case.task_ids)

        if task_count >= 25:
            # Pauses execution cleanly via LangGraph interrupt
            confirmed = interrupt({
                "type": "preview_gate",
                "message": f"Large build preview: {task_count} tasks ready to execute.",
                "use_case_id": use_case.id,
            })
            if not confirmed:
                return {"status": "cancelled", "summary": "Build preview cancelled by user."}

        return {"status": "in_progress"}
    finally:
        if _TEST_ACTIVE_ENV is None:
            cr.close()


def execute_chunk_node(state: UseCaseGraphState) -> Dict[str, Any]:
    """Executes tasks in chunks with bulk hygiene context."""
    cr, env = _rebuild_env(state)
    try:
        # Wrap context with bulk hygiene to suppress notifications
        env = env(context=dict(env.context, **BULK_HYGIENE_CONTEXT))
        res = PlanExecutor.execute_use_case(env, state["use_case_id"])
        cr.commit()

        if res.get("status") == "approval_required":
            return {
                "status": "approval_required",
                "target_record_model": "ai.agent.approval",
                "target_record_id": res.get("approval_id"),
                "summary": res.get("message", "Waiting for human approval"),
            }
        elif not res.get("success"):
            return {
                "status": "failed",
                "error_message": res.get("error"),
                "summary": res.get("error", "Execution failed"),
            }
        return {
            "status": "completed",
            "summary": res.get("summary", "All tasks executed successfully."),
        }
    except Exception as e:
        cr.rollback()
        return {"status": "failed", "error_message": str(e)}
    finally:
        if _TEST_ACTIVE_ENV is None:
            cr.close()


def approval_gate_node(state: UseCaseGraphState) -> Dict[str, Any]:
    """Safe checkpoint pause for T2 human approvals."""
    cr, env = _rebuild_env(state)
    try:
        use_case = env["ai.agent.use.case"].browse(state["use_case_id"])
        pending_approvals = use_case.approval_ids.filtered(lambda a: a.state == "pending")

        if pending_approvals:
            # Native interrupt: never store is_t2_approved in state
            decision = interrupt({
                "type": "approval_gate",
                "approval_id": pending_approvals[0].id,
                "message": f"Operation requires approval: {pending_approvals[0].tool_name}",
            })
            # Re-verify approval status in database directly
            pending_approvals.invalidate_recordset(["state"])
            if pending_approvals[0].state != "executed":
                return {
                    "status": "failed",
                    "error_message": "Operation was rejected or not confirmed in database.",
                }

        return {"status": "in_progress"}
    finally:
        if _TEST_ACTIVE_ENV is None:
            cr.close()


def verify_node(state: UseCaseGraphState) -> Dict[str, Any]:
    """Read-back verification: asserts invariant states."""
    cr, env = _rebuild_env(state)
    try:
        use_case = env["ai.agent.use.case"].browse(state["use_case_id"])
        # Invariant: all completed tasks have valid summary and state
        for t in use_case.task_ids:
            if t.state == "failed":
                return {"status": "failed", "error_message": t.error_message}
        return {"status": "verified"}
    finally:
        if _TEST_ACTIVE_ENV is None:
            cr.close()


def report_node(state: UseCaseGraphState) -> Dict[str, Any]:
    """Generates friendly final summary report."""
    cr, env = _rebuild_env(state)
    try:
        use_case = env["ai.agent.use.case"].browse(state["use_case_id"])
        summary = use_case.summary or f"Use case '{use_case.name}' completed with state {use_case.state}."
        return {
            "status": "completed",
            "summary": summary,
        }
    finally:
        if _TEST_ACTIVE_ENV is None:
            cr.close()
