# -*- coding: utf-8 -*-
"""
AI Agent Core Service (Global Decisions 1, 2, 7 & 8).
Powered by OpenAILLMClient.
Orchestrates:
- Budget and rate-limit verification before LLM calls.
- Pure questions vs Use-case planning.
- Bounded token windows.
- Full execution audit logging in ai.agent.log.

Complexity:
- Time: O(1) + LLM latency.
- Space: O(M) message payload.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from odoo import api, models
from .llm_client import OpenAILLMClient, LLMClientError
from .intent_router import build_system_prompt_with_grounding, route_intent
from .planner import parse_and_validate_plan, PLANNER_SYSTEM_PROMPT, PlanValidationError
from .executor import PlanExecutor
from ..services.rate_limiter import check_and_consume_budget, get_budget_status
from ..services.database_context_service import build_live_database_context
from ..tools import ToolExecutor, get_all_tool_definitions

_logger = logging.getLogger(__name__)


class AiAgentService(models.AbstractModel):
    _name = 'ai.agent.service'
    _description = 'AI Agent Core Service — OpenAI-Compatible LLM Gateway'

    @api.model
    def _get_config(self):
        """Reads settings from ir.config_parameter (Odoo 20 API)."""
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'api_base': (ICP.get_str('sale_ai_agent.api_base', default='https://openrouter.ai/api/v1') or '').strip().rstrip('/'),
            'api_key': (ICP.get_str('sale_ai_agent.api_key', default='') or '').strip(),
            'model': (ICP.get_str('sale_ai_agent.model', default='google/gemini-2.0-flash-exp:free') or '').strip(),
            'max_tokens': ICP.get_int('sale_ai_agent.max_tokens', 4096),
            'temperature': ICP.get_float('sale_ai_agent.temperature', 0.7),
            'timeout': ICP.get_int('sale_ai_agent.timeout', 45),
            'system_prompt': ICP.get_str(
                'sale_ai_agent.system_prompt',
                default=(
                    "You are an expert Operations & Sales AI Agent embedded in Odoo 20. "
                    "You act as a Junior Odoo Implementer across Sales, Purchase, Inventory, MRP, CRM, Projects, and Loyalty. "
                    "Be concise, precise, and never execute T2 actions without approval."
                ),
            ),
        }

    @api.model
    def _get_llm_client(self, cfg=None):
        cfg = cfg or self._get_config()
        return OpenAILLMClient(
            base_url=cfg['api_base'],
            api_key=cfg['api_key'],
            model=cfg['model'],
            timeout=cfg['timeout'],
        )

    @api.model
    def run_agent_turn(self, messages, max_iterations=10, source='chat_agent', model_name=None, res_id=None):
        """
        Executes a turn: checks budget, handles use cases via planning or answers direct questions.
        """
        # 1. Budget and rate-limiting check (G2)
        allowed, budget_info = check_and_consume_budget(self.env, cost=1)
        if not allowed:
            return {
                "role": "assistant",
                "content": f"⚠️ **Rate Limit / Daily Budget Reached**: You have used {budget_info.get('daily_used')}/{budget_info.get('daily_budget')} calls today. Please wait or increase the budget in Settings.",
                "executed_tools": [],
            }

        cfg = self._get_config()
        client = self._get_llm_client(cfg)
        Logs = self.env['ai.agent.log']
        start_time = time.time()

        last_user_prompt = ""
        for m in reversed(messages):
            if m.get('role') == 'user':
                last_user_prompt = m.get('content', '')
                break

        domain = route_intent(last_user_prompt)

        # 2. Check if this is a complex multi-step use case
        if domain == "multi" or any(kw in last_user_prompt.lower() for kw in ("use case", "usecase", "scenario", "flow", "workflow")):
            # Route through LangGraph Use-Case engine
            return self._plan_and_execute_use_case_graph(client, cfg, last_user_prompt)

        # 3. Normal question / single-domain turn
        system_prompt, domain = build_system_prompt_with_grounding(cfg['system_prompt'], last_user_prompt)
        
        # Inject live database & activity context
        db_context = build_live_database_context(self.env, active_model=model_name, active_id=res_id)
        system_prompt = f"{system_prompt}\n\n{db_context}"

        tool_defs = get_all_tool_definitions(env=self.env, domain=domain)

        api_messages = [{"role": "system", "content": system_prompt}]
        for m in messages[-10:]:
            if m.get('role') in ('user', 'assistant'):
                api_messages.append({"role": m['role'], "content": m['content']})

        try:
            resp = client.create_chat_completion(
                messages=api_messages,
                tools=tool_defs,
                max_tokens=cfg['max_tokens'],
                temperature=cfg['temperature'],
            )

            tool_calls = resp.get("tool_calls", [])
            content = resp.get("content", "")
            executed_tools = []

            # Execute tool calls if returned
            for tc in tool_calls:
                t_name = tc.get("name")
                t_args = tc.get("arguments", {})
                res = ToolExecutor.execute(self.env, t_name, t_args, context={"instruction": last_user_prompt})
                executed_tools.append({
                    "tool": t_name,
                    "arguments": t_args,
                    "result": res,
                })

            duration = round(time.time() - start_time, 2)
            usage = resp.get("usage", {})
            Logs.sudo().create({
                'name': f"Chat Action: {domain}",
                'user_id': self.env.user.id,
                'source': source,
                'prompt': last_user_prompt[:500],
                'response': content[:1000],
                'tools_called': json.dumps([t['tool'] for t in executed_tools]),
                'status': 'success',
                'execution_time': duration,
            })

            # If tools were executed but no conversational content was generated
            if executed_tools and not content:
                first_res = executed_tools[0]["result"]
                content = first_res.get("message") or f"Executed tool '{executed_tools[0]['tool']}' successfully."

            return {
                "role": "assistant",
                "content": content,
                "executed_tools": executed_tools,
            }

        except LLMClientError as e:
            return {"role": "assistant", "content": f"API Error: {str(e)}", "executed_tools": []}
        except Exception as e:
            _logger.exception("Unexpected error in run_agent_turn: %s", e)
            return {"role": "assistant", "content": f"Execution error: {str(e)}", "executed_tools": []}

    def _plan_and_execute_use_case_graph(self, client, cfg, prompt: str) -> Dict[str, Any]:
        """Orchestrates complex use case through compiled LangGraph engine."""
        UseCase = self.env['ai.agent.use.case']
        use_case = UseCase.create({
            'name': "Business Use Case",
            'prompt': prompt,
            'state': 'planning',
        })
        try:
            from ..graph.runtime import run_use_case_through_graph
            graph_res = run_use_case_through_graph(self.env, use_case.id)

            task_list_str = "\n".join([
                f"- {'✓' if t.state=='done' else '⏳'} **{t.title}**: {t.result_summary or t.state}"
                for t in use_case.task_ids
            ])

            reply_content = (
                f"### 📋 {use_case.name}\n"
                f"{use_case.summary or ''}\n\n"
                f"**Execution Status**: {use_case.state.upper()} ({use_case.progress}%)\n\n"
                f"{task_list_str}\n\n"
            )
            if graph_res.get("status") == "approval_required":
                reply_content += f"\n🛡️ **{graph_res.get('summary')}**"

            return {
                "role": "assistant",
                "content": reply_content,
                "executed_tools": [],
                "use_case_id": use_case.id,
            }
        except Exception as e:
            _logger.warning("LangGraph execution fallback to legacy executor: %s", e)
            return self._plan_and_execute_use_case(client, cfg, prompt)

    def _plan_and_execute_use_case(self, client, cfg, prompt: str) -> Dict[str, Any]:
        """Plans and runs an end-to-end use case via ai.agent.use.case and ai.agent.task.

        Uses a compact tool list to save context budget and max_tokens=4096 to
        accommodate reasoning-model overhead (G2: free-model robustness).

        Complexity: O(T) where T is the number of tools/tasks.
        """
        UseCase = self.env['ai.agent.use.case']
        Task = self.env['ai.agent.task']

        # Compact tool list: name only (descriptions bloat context for free models)
        all_tools = get_all_tool_definitions(env=self.env)
        tools_compact = ", ".join([t['name'] for t in all_tools])

        messages = [
            {"role": "system", "content": f"{PLANNER_SYSTEM_PROMPT}\n\nAVAILABLE TOOL NAMES:\n{tools_compact}"},
            {"role": "user", "content": f"Create an execution plan for this business scenario:\n{prompt}"},
        ]

        plan = None
        last_error = None
        # Try twice: generous max_tokens for reasoning models, then even larger (G2)
        for attempt_tokens in (8192, 12000):
            try:
                resp = client.create_chat_completion(
                    messages=messages,
                    max_tokens=attempt_tokens,
                    temperature=0.2,
                )
                raw_content = resp.get("content", "")
                if not raw_content.strip():
                    _logger.warning("Planner returned empty content (attempt max_tokens=%d)", attempt_tokens)
                    last_error = "LLM returned empty response (likely reasoning model token exhaustion)"
                    continue
                plan = parse_and_validate_plan(self.env, raw_content)
                break
            except Exception as e:
                last_error = str(e)
                _logger.warning("Planning attempt failed (max_tokens=%d): %s", attempt_tokens, e)
                continue

        if plan is None:
            _logger.warning("All planning attempts failed: %s", last_error)
            return {
                "role": "assistant",
                "content": f"⚠️ Could not generate automated plan ({last_error}). Please try specifying the individual steps.",
                "executed_tools": [],
            }

        # Create persistent use case and tasks
        use_case = UseCase.create({
            'name': plan.get("title") or "Business Use Case",
            'prompt': prompt,
            'state': 'planning',
            'summary': plan.get("summary", ""),
        })

        for t in plan.get("tasks", []):
            Task.create({
                'use_case_id': use_case.id,
                'sequence': t.get("sequence", 10),
                'title': t.get("title"),
                'tool_name': t.get("tool_name"),
                'arguments_json': json.dumps(t.get("arguments", {})),
                'state': 'pending',
            })

        # Deterministic execution of the created use case
        exec_res = PlanExecutor.execute_use_case(self.env, use_case.id)

        # Build clean user response
        task_list_str = "\n".join([
            f"- {'✓' if t.state=='done' else '⏳'} **{t.title}**: {t.result_summary or t.state}"
            for t in use_case.task_ids
        ])

        reply_content = (
            f"### 📋 {use_case.name}\n"
            f"{use_case.summary or ''}\n\n"
            f"**Execution Status**: {use_case.state.upper()} ({use_case.progress}%)\n\n"
            f"{task_list_str}\n\n"
        )
        if exec_res.get("status") == "approval_required":
            reply_content += f"\n🛡️ **{exec_res.get('message')}**"

        return {
            "role": "assistant",
            "content": reply_content,
            "executed_tools": [],
            "use_case_id": use_case.id,
        }
