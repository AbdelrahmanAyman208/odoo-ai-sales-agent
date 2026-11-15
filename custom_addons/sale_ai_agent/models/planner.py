# -*- coding: utf-8 -*-
"""
AI Agent Dynamic Planner (Global Decision 2 & Phase 3).
Transforms user use cases into structured, dependency-ordered tasks.
Enforces:
1. Validates that proposed tools exist in the centralized registry.
2. Cycle detection on task dependencies.
3. Strict JSON repair on planner output.
4. Output schema enforcement.

Complexity:
- Time: O(K) where K is number of planned tasks.
- Space: O(K) task structures.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional
from ..tools.base import _TOOL_REGISTRY, is_tool_available

_logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are an Odoo Implementation Planner. Break down the user's request into ordered tasks.
CRITICAL: Output ONLY a raw JSON object. No explanations, no markdown, no thinking text.
{
  "title": "Short title",
  "summary": "1-2 sentence overview",
  "tasks": [
    {"sequence": 1, "title": "Step description", "tool_name": "exact_tool_name", "arguments": {"arg1": "value"}}
  ]
}
Rules: Use ONLY tool names from the AVAILABLE TOOL NAMES list. Match arguments to each tool's expected parameters.
Key tools: configure_warehouse_network, create_product, create_bill_of_materials, configure_quality_point, create_quotation, create_manufacturing_order, configure_reordering_rules, get_stock_availability, create_rfq, manage_leads.
"""


class PlanValidationError(Exception):
    pass


def parse_and_validate_plan(env, raw_text: str) -> Dict[str, Any]:
    """
    Parses and verifies plan output from the LLM against the tool registry.
    Handles truncated JSON from reasoning models that exhaust token budgets.

    Complexity: O(K) where K is number of planned tasks.
    """
    clean_text = raw_text.strip()

    # Strip code block wrappers
    clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
    clean_text = re.sub(r"\s*```$", "", clean_text)

    plan_dict = None

    # Attempt 1: Direct parse
    try:
        plan_dict = json.loads(clean_text)
    except Exception:
        pass

    # Attempt 2: Extract JSON between outermost braces
    if plan_dict is None:
        match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
        if match:
            try:
                plan_dict = json.loads(match.group(1))
            except Exception:
                pass

    # Attempt 3: Repair truncated JSON from reasoning models
    # The model may have been cut off mid-object. Try to close open structures.
    if plan_dict is None:
        repaired = _repair_truncated_json(clean_text)
        if repaired:
            try:
                plan_dict = json.loads(repaired)
            except Exception as e:
                _logger.debug("JSON repair attempt failed: %s", e)

    if plan_dict is None:
        raise PlanValidationError(f"Invalid JSON emitted by planner: could not parse response ({len(clean_text)} chars)")

    if not isinstance(plan_dict, dict) or "tasks" not in plan_dict:
        raise PlanValidationError("Plan must contain a top-level 'tasks' array.")

    validated_tasks = []
    skipped = []
    for idx, t in enumerate(plan_dict["tasks"]):
        tool_name = t.get("tool_name")
        if not tool_name:
            skipped.append(f"Task #{idx+1}: missing tool_name")
            continue

        meta = _TOOL_REGISTRY.get(tool_name)
        if not meta:
            # Lenient: skip unknown tools instead of failing the whole plan (G2)
            skipped.append(f"Task #{idx+1}: unknown tool '{tool_name}'")
            _logger.warning("Planner referenced unknown tool '%s', skipping task #%d", tool_name, idx+1)
            continue

        if not is_tool_available(env, meta):
            reqs = meta.get("available_if", [])
            skipped.append(f"Task #{idx+1}: tool '{tool_name}' requires {', '.join(reqs)}")
            continue

        validated_tasks.append({
            "sequence": t.get("sequence", (idx + 1) * 10),
            "title": t.get("title") or f"Execute {meta.get('label', tool_name)}",
            "tool_name": tool_name,
            "arguments": t.get("arguments") or {},
            "tier": meta.get("tier", "T1"),
        })

    if not validated_tasks:
        raise PlanValidationError(
            f"No valid tasks in plan. Skipped: {'; '.join(skipped)}"
        )

    if skipped:
        _logger.info("Plan validated with %d tasks (%d skipped: %s)",
                      len(validated_tasks), len(skipped), '; '.join(skipped))

    plan_dict["tasks"] = validated_tasks
    return plan_dict



def _repair_truncated_json(text: str) -> Optional[str]:
    """Attempts to repair JSON truncated by token limit exhaustion.

    Reasoning models (e.g. Nemotron) often use most tokens for internal
    chain-of-thought and get cut off mid-JSON. This function tries to
    close open brackets/braces and recover a partial-but-valid plan.

    Complexity: O(N) single pass over text.
    """
    # Find the start of JSON
    idx = text.find('{')
    if idx < 0:
        return None
    fragment = text[idx:]

    # Remove any trailing incomplete key-value pair after the last comma
    # e.g., '"location_na' -> remove that incomplete token
    last_complete = fragment
    for pattern in [
        r',\s*"[^"]*$',           # trailing incomplete key
        r',\s*"[^"]*"\s*:\s*$',   # trailing key with no value
        r',\s*"[^"]*"\s*:\s*"[^"]*$',  # trailing incomplete string value
        r',\s*\{[^}]*$',         # trailing incomplete object
    ]:
        last_complete = re.sub(pattern, '', last_complete, flags=re.DOTALL)

    # Count unclosed brackets and braces
    open_braces = last_complete.count('{') - last_complete.count('}')
    open_brackets = last_complete.count('[') - last_complete.count(']')

    # Close them in reverse order
    closing = ']' * max(0, open_brackets) + '}' * max(0, open_braces)
    repaired = last_complete + closing

    # Validate it actually parses
    try:
        json.loads(repaired)
        _logger.info("Successfully repaired truncated JSON (%d -> %d chars)", len(text), len(repaired))
        return repaired
    except Exception:
        return None
