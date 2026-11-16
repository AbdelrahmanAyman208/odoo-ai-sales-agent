# Addendum 4 Implementation Plan: Advanced Execution Engine & Hard-Task Evaluation Suite

## Objective
Implement Addendum 4 replacing Phases 4, 5, and 8, introducing G11 (Advanced Execution Engine) and Phase 13 (Hard-Task Evaluation Suite with 30+ scenarios across 4 difficulty levels).

---

## 1. Architecture & Global Decisions (G11)
1. **Pipeline Execution Engine (`services/pipeline_engine.py`)**:
   - `UNDERSTAND`: Schema validation of macro specs, batched resolution of partners, products, users, locations.
   - `PREFLIGHT`: Checks modules, settings, permissions, master data, size estimate. Generates "fix configuration" tasks if missing.
   - `VALIDATE`: Deterministic verification (cycle detection, working calendar consistency, UoM checks, capacities).
   - `PREVIEW`: Compact preview summary for builds above threshold $N$ with a single "Run" confirmation.
   - `EXECUTE`: Chunked/batched execution with idempotency keys, savepoints, and bulk context hygiene (`tracking_disable`, `mail_notrack`, `mail_create_nolog`, `mail_auto_subscribe_no_notify`).
   - `VERIFY`: Read-back assertions (no dependency cycle, BOM rollup invariants, no orphan locations).
   - `REPORT`: Detailed results with counts, links, warnings, assumptions, query count, and execution duration.

2. **Resumable & Undoable State**:
   - Every task execution records created IDs under its idempotency key.
   - `undo_use_case`: Safely archives/cancels created draft records.

3. **Auditable Costing Model (`models/ai_cost_profile.py`)**:
   - Model `ai.cost.profile` for work center costing components (wages, power kW, electricity tariff, depreciation, rent/utilities, consumables) and date-stamped audit trails.

---

## 2. Phase 8 (Replaced): Project Module Spec-First Macro Tools
- `tools/macro_project_tools.py`:
  - `project_build_from_spec`: Two-phase batched creation (create records with temp keys -> set parent/child and `depend_on_ids` in one batched write: $O(V+E)$).
  - Deterministic topological scheduler with critical path analysis, slack, and calendar awareness.
  - `project_replan`: Delay propagation updating only affected tasks.
  - `project_portfolio_health`: $O(1)$ query health overview using `_read_group`.

---

## 3. Phase 4 (Replaced): Advanced Inventory & Warehouse Spec-First Macro Tools
- `tools/macro_inventory_tools.py`:
  - `warehouse_design_from_spec`: Full location hierarchy (zones, aisles, racks, levels, bins), 1/2/3-step routing, putaway rules, removal strategies.
  - `multi_warehouse_network_build`: Central warehouse and retail stores with automated resupply routes and reordering rules.
  - `replenishment_advise`: Average daily demand calculation x lead time + safety stock using `_read_group` over stock moves.
  - `warehouse_health_report`: $O(1)$ query analytics for dead stock, aging, negative stock, and stockout risk.

---

## 4. Phase 5 (Replaced): Advanced MRP & Costing Spec-First Macro Tools
- `tools/macro_mrp_tools.py`:
  - `mrp_setup_production_from_spec`: Batched creation of multi-level BOMs, operations, and work centers.
  - `mrp_cost_workcenter`: Breakdown of labor, power/electricity, depreciation, rent/utilities overhead. Creates `ai.cost.profile`.
  - `mrp_cost_rollup`: Standard vs actual comparison (material usage variance, labor rate variance, target margin pricing).
  - `mrp_capacity_schedule`: Work center load balancing, bottleneck detection, lead-time estimation.

---

## 5. Expert Playbooks (`knowledge/`)
- `knowledge/project_playbook.md`: WBS patterns, estimation heuristics, critical path methodology.
- `knowledge/inventory_playbook.md`: Warehouse zone design, replenishment formulas, safety stock math.
- `knowledge/mrp_playbook.md`: Work center hourly rate formulas, BOM costing rollup, OEE benchmarks.

---

## 6. Phase 13: Hard-Task Evaluation Suite (`tests/hard_tasks/`)
- 30 comprehensive test scenarios across 4 levels:
  - **L1 Simple**: Single macro specs, product & location setup.
  - **L2 Multi-Step**: Re-planning, cost rollup with electricity and labor.
  - **L3 Cross-Module**: MTO end-to-end (SO -> MO -> RFQ -> Quality Gate -> Delivery).
  - **L4 Large / Ambiguous**: 45-task 6-phase project with calendar scheduling, crash recovery / resume, and bulk hygiene.
- Dual execution mode: Mocked LLM (CI regression) and Live LLM mode.
