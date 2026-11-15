# AI Operations Agent (`sale_ai_agent`) for Odoo 20.0

An autonomous AI Operations Agent embedded in **Odoo 20.0** (LGPL-3) that acts as a **Junior Odoo Implementer** across Sales, Purchase, CRM, Promotions & Loyalty, Projects, Inventory, and Manufacturing (including product variants and quality checks), with built-in RAG retrieval over official Odoo 20 documentation.

---

## 🌟 Architectural Foundations (Global Decisions G1 – G10)

### G1: ONE Universal LLM Client (OpenAI-Compatible / OpenRouter)
- Implemented in [`models/llm_client.py`](file:///d:/sales%20agent/custom_addons/sale_ai_agent/models/llm_client.py).
- Communicates exclusively via standard OpenAI Chat Completions (`/chat/completions`) using standard `tools` and `tool_calls`.
- Default base URL: `https://openrouter.ai/api/v1` (supports any OpenAI-compatible provider: OpenRouter, vLLM, Ollama, OpenAI).
- **Zero Fallback Multi-Provider Layer**: Changing providers or models requires only changing the `model` ID in settings.
- **Resilient Retry**: Exponential backoff with jitter on 429/5xx and timeouts (max 3 retries), respecting `Retry-After`.
- All legacy Anthropic-specific code (`tool_use`, `cache_control`) has been deleted.

### G2: Free-Model Reliability & Hard Quota Budget
- **Shared Rate Limiter**: Implemented in [`services/rate_limiter.py`](file:///d:/sales%20agent/custom_addons/sale_ai_agent/services/rate_limiter.py). Enforces Requests-Per-Minute (RPM) token bucket and hard daily request caps (e.g., 50 or 200 calls/day) to prevent 429 errors on free models. Checks budget **before** making external API calls.
- **Dynamic Planner + Deterministic Executor**:
  - Complex use cases call the LLM **once** for structured JSON task planning ([`models/planner.py`](file:///d:/sales%20agent/custom_addons/sale_ai_agent/models/planner.py)).
  - The plan is executed deterministically by [`models/executor.py`](file:///d:/sales%20agent/custom_addons/sale_ai_agent/models/executor.py) **without extra LLM roundtrips**.
- **Self-Healing Argument Parser**: Auto-coerces numeric strings, unpacks single-element lists, and extracts JSON tool calls embedded directly into conversational markdown.

### G3: Zero Plain-Chat Database Persistence
- Plain chat conversations live strictly in client-side state (transient/OWL memory).
- The Odoo database stores **only real business transactions and audit logs**:
  - `ai.agent.use.case`: High-level business goals and progress tracking.
  - `ai.agent.task`: Decomposed tasks with sequence, arguments, and record links.
  - `ai.agent.approval`: T2 human authorization records.
  - `ai.agent.log`: Latency, tool names, and execution metadata (no conversational chat bloat).

### G6 & G7: Human-in-the-Loop T2 Safety
- **Risk Tiers**:
  - **T0**: Read-only queries (stock check, reports, search).
  - **T1**: Reversible/draft actions (create quotation, draft RFQ, BOM, lead).
  - **T2**: Irreversible or financial actions (confirm SO/PO, validate delivery/receipt, mark MO done).
- The LLM **can never execute T2 actions directly**. T2 tools create an `ai.agent.approval` record and halt execution.
- Human confirmation requires a two-step verification workflow with SHA256 snapshot hashes to detect stale data. Direct "Go to Record" navigation opens the target PO/SO immediately.

### G8: Edition-Awareness (Community vs Enterprise)
- Automatically detects installed modules via [`services/capabilities.py`](file:///d:/sales%20agent/custom_addons/sale_ai_agent/services/capabilities.py) and reports capabilities via `get_system_capabilities`.
- When Enterprise apps (such as `quality_control`) are absent, the agent automatically activates lightweight Community fallback models ([`models/ai_quality.py`](file:///d:/sales%20agent/custom_addons/sale_ai_agent/models/ai_quality.py)).

### G9: Cross-Module Decoupling & Traceability
- **Conditional Tool Registration**: Each tool registers with `available_if=[...]`. Missing optional apps never break addon loading.
- **Shared `services/` Layer**: Disambiguation (`partner_resolver`, `product_resolver`), rate-limiting, and document linking are centralized to prevent circular imports.
- **Full Traceability**: All generated records carry indexed `ai_use_case_id` and `ai_task_id` fields.

### G10: Development Infrastructure
- [`docker-compose.dev.yml`](file:///d:/sales%20agent/docker-compose.dev.yml) provided for optional local Redis (shared rate limiter and RAG caching) and Chroma vector storage.

---

## 🛠️ Complete Registered Tools Catalog (46 Tools)

### 1. Sales & Variants (`tools/sales_tools.py`, `tools/variant_tools.py`)
- `create_quotation` (T1): Disambiguates partners and products, applies pricing/discounts, links AI context.
- `confirm_sales_order` (T2): Intercepts execution for human confirmation before confirming quotations.
- `get_quotation_details` (T0): Real-time inspection of lines, pricing, taxes, and status.
- `configure_product_variants` (T1): Configures attributes, values, and price extras with an **explosion guard** (default max 100 variants).

### 2. Purchasing (`tools/purchase_tools.py`)
- `create_rfq` (T1): Generates supplier RFQs with partner disambiguation and custom items.
- `compare_vendor_offers` (T0): Compares supplier pricelists for lowest price and lead times.
- `confirm_purchase_order` (T2): Intercepts execution for human confirmation before financial commitments.

### 3. Inventory & Warehouses (`tools/inventory_tools.py`, `tools/warehouse_tools.py`, `tools/location_tools.py`)
- `get_stock_availability` (T0): Real-time on-hand, free-to-use, and incoming quantities.
- `check_inventory_replenishment` (T0): Scans products below minimum safety threshold.
- `create_replenishment_order` (T1): Triggers automated procurement orders.
- `validate_picking` (T2): Intercepts warehouse stock validation for human approval.
- `get_stock_by_locations` (T0): Breakdown of inventory across internal locations.
- `create_internal_transfer` (T1): Drafts internal stock moves between warehouses/locations.
- `configure_warehouse_network` (T1): Configures warehouses and inter-warehouse resupply routes.
- `configure_reordering_rules` (T1): Sets automated min/max stock points per location.
- `get_warehouse_stock_report` (T0): Network-wide stock overview aggregated via `_read_group`.

### 4. Manufacturing & Quality (`tools/mrp_tools.py`, `tools/quality_tools.py`)
- `create_bill_of_materials` (T1): Creates BOMs with components, quantities, and cycle-prevention guards.
- `create_manufacturing_order` (T1): Drafts MOs with component reservation.
- `confirm_mrp_production` (T2): Intercepts MO confirmation for human authorization.
- `configure_quality_point` (T1): Defines pass/fail or measurement inspection criteria.
- `record_quality_check` (T1): Records inspection outcomes on MOs or stock transfers.
- `list_mrp_quality_checks` (T0): Audits inspection completion status for manufacturing orders.

### 5. CRM Implementer (`tools/crm_tools.py`)
- `setup_crm_pipeline` (T1): Configures sales teams, stages, sequences, won flags, and fold.
- `manage_leads` (T1): Creates or updates opportunities with expected revenue, stage, and priority.
- `merge_duplicate_leads` (T1): $\mathcal{O}(N)$ hash-based duplicate lead detection and native merging.
- `batch_create_leads_from_text` (T1): Parses structured lists/CSVs with in-memory deduplication.
- `score_lead` (T0): Rule-based qualification score (0–100) with explanatory factors.
- `get_crm_reporting` (T0): Pipeline breakdown by stage, revenue, and win rates via `_read_group`.
- `create_quotation_from_opportunity` (T1): Cross-module conversion from Opportunity to draft Sale Order.

### 6. Loyalty, Coupons & Promotions (`tools/loyalty_tools.py`)
- `manage_loyalty_program` (T1): Configures promotions, discount codes, coupon programs, and loyalty cards.
- `generate_coupons` (T1 / T2): Batch generates unique coupon cards (`create([vals_list])`). Escalates to T2 if count > 100.
- `apply_promotions_to_order` (T1): Previews promotional discount effects on open sale orders.
- `get_loyalty_report` (T0): Usage metrics and card counts via `_read_group`.

### 7. Project Management (`tools/project_tools.py`)
- `manage_projects` (T1): Creates/updates projects, managers, and target timelines.
- `manage_project_tasks` (T1): Task assignment, subtasks, deadlines, and sale order line linking.
- `check_project_health_and_deadlines` (T0): Identifies overdue tasks and milestones.

### 8. Documentation RAG & Administration (`tools/docs_tools.py`, `tools/admin_tools.py`, `tools/diagnostic_tools.py`, `tools/search_tools.py`)
- `search_odoo_docs` (T0): Fast hybrid lexical search across official Odoo 20 documentation.
- `get_system_capabilities` (T0): Reports Odoo edition, installed modules count, and active domains.
- `check_system_configuration` (T0): Validates warehouse routes, MTO rules, and tracking settings.
- `check_product_routes_and_bom` (T0): Validates routes (Buy, Manufacture) and BOM presence.
- `search_products` (T0): Multi-field product discovery.
- `search_partner` (T0): Contact and vendor lookup.
- `create_product` (T1): Creates tracked/untracked storable, consumable, or service items.
- `install_or_activate_language` (T1): Installs or activates system translation packages.
- `list_system_languages` (T0): Lists available and active system languages.
- `create_odoo_user` (T1): Creates users and maps them to security groups.

---

## ⚙️ Configuration & Testing

Navigate to **Settings ➔ Sales / Operations ➔ AI Operations Agent**:
1. **OpenAI / OpenRouter Base URL**: `https://openrouter.ai/api/v1` (or local vLLM/Ollama).
2. **API Key**: Group-restricted; never logged in plain text.
3. **Model Name**: e.g., `google/gemini-2.0-flash-exp:free`, `meta-llama/llama-3.3-70b-instruct:free`, `anthropic/claude-3.5-sonnet`.
4. **Rate Limiting**: Configure RPM token bucket and Daily Request Budget.
5. **Test LLM Connection Button**: Runs a live connectivity check and displays a notification.

---
//fe_oa_e7b04ee2bf4217e0e6f0d5bff2de84af1451789117d41a69//
## 🚀 Running the End-to-End Use Case

Open the **AI Operations Agent** in Odoo 20 and paste this scenario:

```text
Execute this complete business use case:
1. Create a CRM Opportunity for 'Deco Addict' titled 'Executive Boardroom Desks' with expected revenue $12,000.
2. Check if components exist: 'Table Top' and 'Steel Legs'.
3. Create a Bill of Materials for a new finished product 'Executive Conference Table' consisting of:
   - 1 unit of Table Top
   - 4 units of Steel Legs
4. Create a draft Sales Quotation for customer 'Deco Addict' for 10 units of 'Executive Conference Table' with a 5% discount, linked to the opportunity.
5. Create a Manufacturing Order (MO) for 10 units of 'Executive Conference Table'.
6. Add a Quality Control Point for 'Executive Conference Table' titled 'Surface & Finish Inspection' (pass/fail).
7. Check stock availability for the components; if any component is low, compare supplier offers and create an RFQ for the cheapest supplier.
8. Request T2 human confirmation for the Sales Quotation.
```

The agent will parse the request, construct a structured task plan, execute steps deterministically, and present the **T2 Human Approval Card** with direct navigation links.
