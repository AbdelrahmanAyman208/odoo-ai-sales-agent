# MASTER SPEC: Odoo 20.0 AI Sales & Operations Copilot (`sale_ai_agent`)

---

# ROLE & MISSION
You are a Senior Odoo Architect and Senior Python/OWL engineer working inside an existing Odoo addon: `sale_ai_agent` (Odoo 20.0, LGPL-3).
The agent acts as a JUNIOR ODOO IMPLEMENTER across Sales, Purchase, Inventory, and Manufacturing. A business use case described in natural language is planned, executed end-to-end, and reported clearly without manual intervention, while strictly adhering to safety, approval, and performance boundaries.

---

# GLOBAL DECISIONS

## GLOBAL DECISION 1: SINGLE PROVIDER (ANTHROPIC CLAUDE VIA CUSTOM BASE URL)
- The ONLY supported provider is Anthropic Claude, called through the custom Anthropic-compatible base URL.
- REMOVE: OpenAI, Gemini, Groq, Ollama/local LLM code, provider selection fields/UI, fallback/auto-switch logic, and all related settings/tests/README sections.
- Single client: `claude_client.py` speaking Anthropic Messages API (tool_use / tool_result blocks, streaming SSE).
- Settings keep only: Base URL, API Key (group-restricted, never logged), Model name, Max tokens, Temperature, Timeout, System Prompt.
- Exponential backoff + jitter on 429/5xx/timeouts (max 2-3 tries), respect Retry-After, fail fast with a user-facing message. No blocking workers.
- Migration to delete obsolete `ir.config_parameter` keys.

## GLOBAL DECISION 2: CHAT = QUESTIONS, NOT STORED DATA
- Plain chat messages and answers are NEVER saved in the database.
- Chat history lives in client (OWL state) for current session only, sent as bounded sliding window (O(k)).
- Intent separation:
  - QUESTION: Read-only tools only, answer from live data, zero DB writes/records.
  - USE CASE / ACTION REQUEST: Create a use case with plan and tasks, execute.
- Persisted models only: `ai.agent.use.case`, `ai.agent.task`, `ai.agent.approval`, and `ai.agent.log` (audit of tool calls).

## GLOBAL DECISION 3: SPEED & STREAMING
- Stream (SSE) responses; OWL UI appends to a single message node via `requestAnimationFrame`.
- Anthropic prompt caching (`cache_control`) on static prefix: system prompt + tool definitions + domain playbook.
- Send only relevant tools per request via keyword/intent router (`sales`, `purchase`, `inventory`, `mrp`, `crm`).
- Minimal tool payloads; batch independent tool calls; reuse HTTP connection pool.
- Log step latencies (TTFT, total, tool execution) in `ai.agent.log`.

## GLOBAL DECISION 4: Odoo 20.0 ONLY
- Only supported version: Odoo 20.0. Remove all 17.0/18.0 compatibility branches and references.
- Manifest version format: `20.0.x.y.z`. Depends: `sale_management`, `purchase`, `stock`, `mrp`, `crm`, `bus`, `mail`.
- Ground truth is real Odoo 20.0 source code (`odoo20/`). Verify field names, methods, states, and syntax directly.
- Modern API: `_read_group` style per 20.0, `<list>` views (never `<tree>`), no `attrs`/`states` XML attributes, no `name_get`.

## GLOBAL DECISION 5: UI = CLEAN CHAT + SEPARATE CAPABILITIES PANEL
- Chat area contains ONLY conversation, input, status line, and use-case progress. No in-stream capability dump.
- Collapsible "What I can do" panel (OWL component) organized by module: Sales, Purchase, Inventory, Manufacturing, CRM.
  - One-line description.
  - Executable actions.
  - 2-3 clickable example prompts that populate input without auto-send.
- Generated statically from tool registry metadata (`domain`, `label`, `description`, `examples`). Bilingual (English/Arabic).
- Act as junior implementer: master data, routes, BOMs, transaction flows. Clear indication when no tool exists.

## GLOBAL DECISION 6: HUMAN APPROVAL FOR RISKY ACTIONS (T2)
### Risk Tiers
- **T0 (Read-Only)**: Free execution, zero side-effects.
- **T1 (Drafts / Reversible)**: Quotations, RFQs, draft MOs, BOMs, line edits. Auto-execute, logged.
- **T2 (Irreversible / Financial / Bulk)**: Confirm SO/PO, validate/receive picking, mark MO done, create/post invoices, register payment, cancel, scrap, inventory adjustments, and ALL bulk actions. **T2 REQUIRES HUMAN APPROVAL.**
### Core Rules
1. LLM NEVER executes T2 actions directly. T2 tools create `ai.agent.approval` and return `approval_required`.
2. Execution ONLY via CSRF-protected HTTP/JSON-RPC controller bound to session user (`requested_by`). Never use `sudo()`.
3. Two-step confirmation: Step 1 full review card -> Step 2 final confirmation (type count or `CONFIRM`).
4. Cards rendered strictly from DB data (prompt injection defense).
5. Conditional/bulk actions resolved into concrete frozen list before approval creation.
6. Frozen snapshot hash (`snapshot_hash`) rechecked at execution; stale if records changed.
7. Expiry (default 15m), idempotency, savepoint per record.

---

# PHASES BREAKDOWN

## PHASE 1: Sales & Purchase Quality
- Strict JSON schema validation, type coercion, informative error returns.
- Partner/product matching: exact -> ilike -> fuzzy. Disambiguation if multiple candidates.
- Full Sales & Purchase tool suite with idempotency keys.
- Real user security context (no unwarranted sudo).

## PHASE 2: Chatbot Reliability & Orchestration
- Network timeouts, retry policy with jitter, rate-limit UI indicators.
- Tool argument auto-repair and structured feedback to model.
- Max-iterations & token/step guards to prevent infinite loops.
- `with self.env.cr.savepoint():` per tool execution.
- Asynchronous execution for long use-cases via bus/ir.cron so worker never hangs.

## PHASE 3: Use-Case-Driven Architecture
- Remove all static/hardcoded legacy use cases.
- New models: `ai.agent.use.case` and `ai.agent.task` with live status tracking.
- Dynamic planner and task DAG execution.
- Optimized OWL UI with progress bar, task checklist, and final summary card.

## PHASE 4: Inventory Module (Implementer)
- Warehouses, locations, routes, operation types, putaway rules.
- Stock on hand / forecasted / reserved aggregations using `_read_group` on `stock.quant`.
- Receipts, deliveries, internal transfers, adjustments, scrap, tracking setup.
- Reordering rules, multi-route auto-replenishment.

## PHASE 5: Manufacturing Module
- BOMs (normal, kit, phantom), components, work centers, operations.
- Manufacturing Orders: create, check availability, reserve, produce, scrap, done.
- End-to-end MTO: SO -> MO -> missing components RFQ/PO -> receipt -> produce -> deliver.
- Multi-level BOM cost roll-up and production availability reports.

## PHASE 6: Performance & ORM Complexity
- Zero ORM calls inside loops. O(1) queries per tool call via `search_read`, `_read_group`, `mapped`.
- Complexity documented in all docstrings.
- In-memory static registries and schema caching.
- Query-count tests (`assertQueryCount`).

## PHASE 7: Code Quality, Security & Test Coverage
- Modular architecture: `claude_client.py`, `tools/` (by domain), `planner.py`, `executor.py`, `intent_router.py`.
- Security checks (`check_access_rights`, `check_access_rule`).
- Mocked LLM unit, integration, and end-to-end MTO scenario tests.
- Verify removal of legacy providers and adherence to single-provider model.

## PHASE 8: Odoo Knowledge Grounding
- Knowledge sources: Odoo 20.0 documentation and source code.
- Runtime playbooks in `knowledge/` (`sales.md`, `purchase.md`, `inventory.md`, `mrp.md`, `crm.md`) injected selectively into prompt cache.
- Read-only self-check diagnostic tools before action execution.
- Static docs search tool (`search_odoo_docs`).
- Scripted knowledge scenario tests.
