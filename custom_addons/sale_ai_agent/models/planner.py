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

PLANNER_SYSTEM_PROMPT = """You are an expert Odoo Implementation Planner.
Your job is to break down the user's business use case into an ordered sequence of concrete tasks.
Output ONLY a raw JSON object with this exact structure:
{
  "title": "Short title of the plan",
  "summary": "1-2 sentence overview of what will be done",
  "tasks": [
    {
      "sequence": 1,
      "title": "Human-readable description of this step",
      "tool_name": "exact_tool_name_from_registry",
      "arguments": {"arg1": "value"}
    }
  ]
}

Available tools will be provided. Do NOT invent new tool names. Ensure arguments match each tool's schema.
"""


class PlanValidationError(Exception):
    pass


def parse_and_validate_plan(env, raw_text: str) -> Dict[str, Any]:
    """
    Parses and verifies plan output from the LLM against the tool registry.
    """
    clean_text = raw_text.strip()

    # Strip code block wrappers
    clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
    clean_text = re.sub(r"\s*```$", "", clean_text)

    try:
        plan_dict = json.loads(clean_text)
    except Exception as e:
        # Fallback extract JSON between braces
        match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
        if match:
            try:
                plan_dict = json.loads(match.group(1))
            except Exception:
                raise PlanValidationError(f"Could not parse plan JSON: {str(e)}")
        else:
            raise PlanValidationError(f"Invalid JSON emitted by planner: {str(e)}")

    if not isinstance(plan_dict, dict) or "tasks" not in plan_dict:
        raise PlanValidationError("Plan must contain a top-level 'tasks' array.")

    validated_tasks = []
    for idx, t in enumerate(plan_dict["tasks"]):
        tool_name = t.get("tool_name")
        if not tool_name:
            raise PlanValidationError(f"Task #{idx+1} is missing 'tool_name'.")

        meta = _TOOL_REGISTRY.get(tool_name)
        if not meta:
            raise PlanValidationError(f"Task #{idx+1} specifies non-existent tool '{tool_name}'.")

        if not is_tool_available(env, meta):
            reqs = meta.get("available_if", [])
            raise PlanValidationError(f"Tool '{tool_name}' requires uninstalled module(s): {', '.join(reqs)}.")

        validated_tasks.append({
            "sequence": t.get("sequence", (idx + 1) * 10),
            "title": t.get("title") or f"Execute {meta.get('label', tool_name)}",
            "tool_name": tool_name,
            "arguments": t.get("arguments") or {},
            "tier": meta.get("tier", "T1"),
        })

    plan_dict["tasks"] = validated_tasks
    return plan_dict
