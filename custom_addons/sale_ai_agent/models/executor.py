# -*- coding: utf-8 -*-
"""
Deterministic Plan Executor (Global Decisions 2, 7 & 8).
Executes a validated plan sequence WITHOUT calling the LLM when arguments are known.
Updates task state, links records, checks T2 risk tiers, and stops on failures.

Complexity:
- Time: O(T) where T is tasks count.
- Space: O(1) state per task.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from odoo.exceptions import UserError, AccessError
from ..tools.base import ToolExecutor, _TOOL_REGISTRY

_logger = logging.getLogger(__name__)


class PlanExecutor:
    """Executes use-case tasks sequentially with live status updates."""

    @classmethod
    def execute_use_case(cls, env, use_case_id: int) -> Dict[str, Any]:
        UseCase = env['ai.agent.use.case']
        use_case = UseCase.browse(use_case_id)
        if not use_case.exists():
            return {"success": False, "error": f"Use case {use_case_id} not found"}

        use_case.write({
            'state': 'running',
            'started_at': fields_now(env),
        })

        tasks = use_case.task_ids.sorted(key=lambda t: t.sequence)
        total_tasks = len(tasks)
        completed_tasks = 0
        executed_summaries = []

        context_data = {
            "use_case_id": use_case.id,
            "instruction": use_case.prompt,
        }

        for task in tasks:
            if task.state in ('done', 'skipped'):
                completed_tasks += 1
                continue

            task.write({'state': 'running'})
            context_data["task_id"] = task.id

            args = {}
            if task.arguments_json:
                try:
                    args = json.loads(task.arguments_json)
                except Exception:
                    args = {}

            start_t = time.time()
            res = ToolExecutor.execute(env, task.tool_name, args, context=context_data)
            duration = round(time.time() - start_t, 2)

            # Check if intercepted by T2 human approval
            if res.get("approval_required"):
                task.write({
                    'state': 'pending',
                    'result_summary': f"Approval required ({res.get('approval_name', '')})",
                    'res_model': 'ai.agent.approval',
                    'res_id': res.get('approval_id'),
                    'duration': duration,
                })
                use_case.write({
                    'state': 'running',
                    'progress': int((completed_tasks / total_tasks) * 100),
                    'summary': f"Paused: Waiting for human approval on task '{task.title}'.",
                })
                return {
                    "success": True,
                    "status": "approval_required",
                    "use_case_id": use_case.id,
                    "approval_id": res.get("approval_id"),
                    "approval_name": res.get("approval_name"),
                    "message": res.get("message"),
                }

            if not res.get("success"):
                err_text = res.get("error") or "Unknown execution error"
                task.write({
                    'state': 'failed',
                    'error_message': err_text,
                    'result_summary': f"Error: {err_text}",
                    'duration': duration,
                })
                use_case.write({
                    'state': 'failed',
                    'summary': f"Failed on step '{task.title}': {err_text}",
                    'finished_at': fields_now(env),
                })
                return {
                    "success": False,
                    "error": f"Task '{task.title}' failed: {err_text}",
                    "failed_task_id": task.id,
                    "use_case_id": use_case.id,
                }

            # Task succeeded
            res_model, res_id = cls._extract_target_record(res)
            task.write({
                'state': 'done',
                'result_summary': res.get("message") or f"Executed {task.tool_name}",
                'res_model': res_model,
                'res_id': res_id,
                'duration': duration,
            })
            completed_tasks += 1
            executed_summaries.append(f"✓ {task.title}")
            use_case.write({'progress': int((completed_tasks / total_tasks) * 100)})

        use_case.write({
            'state': 'done',
            'progress': 100,
            'finished_at': fields_now(env),
            'summary': f"All {total_tasks} tasks completed successfully.\n" + "\n".join(executed_summaries),
        })

        return {
            "success": True,
            "status": "completed",
            "use_case_id": use_case.id,
            "completed_tasks": completed_tasks,
            "summary": use_case.summary,
        }

    @classmethod
    def _extract_target_record(cls, tool_res: Dict[str, Any]) -> Tuple[Optional[str], Optional[int]]:
        """Finds primary record ID created or modified by the tool."""
        if tool_res.get("sale_order_id"):
            return "sale.order", tool_res["sale_order_id"]
        elif tool_res.get("order_id"):
            return "sale.order", tool_res["order_id"]
        elif tool_res.get("po_id"):
            return "purchase.order", tool_res["po_id"]
        elif tool_res.get("production_id"):
            return "mrp.production", tool_res["production_id"]
        elif tool_res.get("picking_id"):
            return "stock.picking", tool_res["picking_id"]
        elif tool_res.get("lead_id"):
            return "crm.lead", tool_res["lead_id"]
        elif tool_res.get("project_id"):
            return "project.project", tool_res["project_id"]
        elif tool_res.get("task_id"):
            return "project.task", tool_res["task_id"]
        elif tool_res.get("program_id"):
            return "loyalty.program", tool_res["program_id"]
        elif tool_res.get("point_id"):
            return "ai.quality.point", tool_res["point_id"]
        elif tool_res.get("product_tmpl_id"):
            return "product.template", tool_res["product_tmpl_id"]
        elif tool_res.get("product_id"):
            return "product.product", tool_res["product_id"]
        return None, None


def fields_now(env):
    return env['ai.agent.use.case']._fields['started_at'].now()
