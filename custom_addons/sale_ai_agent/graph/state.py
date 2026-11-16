# -*- coding: utf-8 -*-
"""
Graph State Schemas for Orchestration Runtime (Addendum 5 v2 & G12).
Rules:
- Strictly JSON-serializable (No Odoo Recordsets, env, cursors).
- NO chat text in checkpointed state (G3 compliance).
- Large payloads stay in Odoo records and are referenced by ID.
- NEVER put an approval flag (e.g. is_t2_approved) in state.
"""
from typing import TypedDict, List, Dict, Any, Optional

STATE_VERSION = 1

class UseCaseGraphState(TypedDict, total=False):
    # Identification & Odoo Context
    state_version: int
    thread_id: str
    use_case_id: int
    db: str
    uid: int
    company_ids: List[int]
    lang: str

    # Flow & Counters
    domain: str
    spec_hash: str
    spec_fix_attempts: int          # bounded to max 2
    llm_calls_used: int             # budget guard
    llm_calls_limit: int

    chunk_index: int
    total_chunks: int

    # Bounded structured diagnostics (Caps enforced)
    validation_errors: List[str]    # Max 10 items
    warnings: List[str]             # Max 20 items
    assumptions: List[str]          # Max 20 items

    # Execution tracking
    target_record_model: Optional[str]
    target_record_id: Optional[int]
    status: str                     # "in_progress", "preview_required", "approval_required", "completed", "failed"
    error_message: Optional[str]
    summary: str


class StatelessQAState(TypedDict, total=False):
    # Pure in-memory state for Docs and Read-only Queries (No checkpointer)
    user_query: str
    domain: str
    retrieved_docs: List[Dict[str, Any]]
    grade_score: float
    rewrite_count: int              # bounded to max 1
    llm_calls_used: int             # bounded to max 2
    executed_tools: List[Dict[str, Any]]
    final_answer: str
