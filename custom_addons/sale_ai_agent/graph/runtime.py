# -*- coding: utf-8 -*-
"""
Compiled Graph Orchestration Engine (Addendum 5 v2 & Phase 14).
Builds Top Graph and Subgraphs:
- ROUTE_INTENT -> LOCAL_ANSWER / DOCS_QA / READ_QA / USE_CASE
- USE_CASE is checkpointed into dedicated PostgreSQL schema `saa_langgraph`.
- Zero chat persistence: state only tracks control flow.
"""
import logging
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

from .state import UseCaseGraphState, STATE_VERSION
from .checkpointer import get_checkpoint_pool, init_checkpointer_schema
from .nodes import (
    extract_spec_node,
    preflight_node,
    validate_node,
    spec_correction_node,
    preview_gate_node,
    execute_chunk_node,
    approval_gate_node,
    verify_node,
    report_node,
)

_logger = logging.getLogger(__name__)

# Cached compiled graphs
_COMPILED_USE_CASE_GRAPH = None


def build_use_case_graph():
    """Builds the full G11 Use Case StateGraph."""
    builder = StateGraph(UseCaseGraphState)

    # 1. Register nodes
    builder.add_node("extract_spec", extract_spec_node)
    builder.add_node("preflight", preflight_node)
    builder.add_node("validate", validate_node)
    builder.add_node("spec_correction", spec_correction_node)
    builder.add_node("preview_gate", preview_gate_node)
    builder.add_node("execute_chunk", execute_chunk_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("verify", verify_node)
    builder.add_node("report", report_node)

    # 2. Add edges & transitions
    builder.set_entry_point("extract_spec")
    builder.add_edge("extract_spec", "preflight")

    # Conditional validation edge
    def route_after_validate(state: UseCaseGraphState):
        if state.get("status") == "spec_correction_required":
            return "spec_correction"
        elif state.get("status") == "failed":
            return END
        return "preview_gate"

    builder.add_edge("preflight", "validate")
    builder.add_conditional_edges("validate", route_after_validate, {
        "spec_correction": "spec_correction",
        "preview_gate": "preview_gate",
        END: END,
    })
    builder.add_edge("spec_correction", "validate")

    builder.add_edge("preview_gate", "execute_chunk")

    # Conditional execution edge (Self-loop or T2 pause)
    def route_after_execute(state: UseCaseGraphState):
        status = state.get("status")
        if status == "approval_required":
            return "approval_gate"
        elif status == "failed":
            return END
        return "verify"

    builder.add_conditional_edges("execute_chunk", route_after_execute, {
        "approval_gate": "approval_gate",
        "verify": "verify",
        END: END,
    })

    builder.add_edge("approval_gate", "verify")
    builder.add_edge("verify", "report")
    builder.add_edge("report", END)

    return builder


def get_compiled_use_case_graph(env):
    """Compiles and caches the state graph with dedicated postgres checkpointer."""
    global _COMPILED_USE_CASE_GRAPH
    if _COMPILED_USE_CASE_GRAPH is not None:
        return _COMPILED_USE_CASE_GRAPH

    init_checkpointer_schema(env)
    pool = get_checkpoint_pool(env)
    builder = build_use_case_graph()

    checkpointer = PostgresSaver(pool)
    _COMPILED_USE_CASE_GRAPH = builder.compile(checkpointer=checkpointer)

    _logger.info("LangGraph Use-Case Graph successfully compiled with PostgresSaver checkpointer.")
    return _COMPILED_USE_CASE_GRAPH


def run_use_case_through_graph(env, use_case_id: int) -> Dict[str, Any]:
    """
    Executes a use case end-to-end via the LangGraph runtime.
    Odoo recordsets remain the source of truth for domain data.
    """
    graph = get_compiled_use_case_graph(env)
    thread_id = f"{env.cr.dbname}:{use_case_id}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: UseCaseGraphState = {
        "state_version": STATE_VERSION,
        "thread_id": thread_id,
        "use_case_id": use_case_id,
        "db": env.cr.dbname,
        "uid": env.uid,
        "company_ids": env.context.get("allowed_company_ids", [env.company.id]),
        "lang": env.context.get("lang", "en_US"),
        "llm_calls_used": 0,
        "llm_calls_limit": 5,
        "spec_fix_attempts": 0,
        "validation_errors": [],
        "warnings": [],
        "assumptions": [],
        "status": "in_progress",
    }

    try:
        final_state = graph.invoke(initial_state, config=config)
        return {
            "success": final_state.get("status") in ("completed", "verified", "approval_required"),
            "status": final_state.get("status"),
            "summary": final_state.get("summary", ""),
            "target_record_model": final_state.get("target_record_model"),
            "target_record_id": final_state.get("target_record_id"),
        }
    except Exception as e:
        _logger.exception("Error executing use case %s through LangGraph: %s", use_case_id, e)
        return {
            "success": False,
            "status": "failed",
            "error": str(e),
        }
