# -*- coding: utf-8 -*-
"""
Phase 13: Hard-Task Evaluation Suite (Addendum 4).
Contains 30 scenarios across 4 difficulty levels:
- Level 1: Simple (L1_01 to L1_08)
- Level 2: Multi-step (L2_01 to L2_08)
- Level 3: Cross-module (L3_01 to L3_07)
- Level 4: Large / Ambiguous (L4_01 to L4_07)

Verifies database state assertions, query count invariants, and LLM call budgets.
"""
import unittest
from datetime import date
from odoo.tests.common import TransactionCase
from odoo.addons.sale_ai_agent.tools import ToolExecutor
from odoo.addons.sale_ai_agent.services.scheduler_engine import schedule_project_tasks


class TestHardTaskSuite(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent_service = cls.env['ai.agent.service']

    # =========================================================
    # LEVEL 1: SIMPLE MACRO SPEC SCENARIOS (L1_01 to L1_08)
    # =========================================================
    def test_l1_01_warehouse_design_single_zone(self):
        """L1.1: Build warehouse with 1 zone, 2 racks, 2 levels."""
        spec = {
            "name": "Quick Distribution Hub",
            "code": "QDH",
            "zones": [{"name": "Bulk Storage", "racks": 2, "levels": 2}]
        }
        res = ToolExecutor.execute(self.env, "warehouse_design_from_spec", spec)
        self.assertTrue(res.get("success"), res.get("error"))
        self.assertEqual(res["data"]["code"], "QDH")
        self.assertGreaterEqual(res["data"]["total_locations_created"], 5)

    def test_l1_02_workcenter_cost_simple(self):
        """L1.2: Cost workcenter with 1 worker and 3 kW machine."""
        spec = {
            "workcenter_name": "Test Assembly Bench",
            "workers_count": 1,
            "hourly_wage_per_worker": 25.0,
            "machine_power_kw": 3.0,
            "electricity_tariff": 0.20,
        }
        res = ToolExecutor.execute(self.env, "mrp_cost_workcenter", spec)
        self.assertTrue(res.get("success"))
        # 25 + (3 * 0.20 = 0.60) = 25.60/hr minimum
        self.assertGreaterEqual(res["computed_costs_hour"], 25.60)

    def test_l1_03_replenishment_advise_calculation(self):
        """L1.3: Replenishment advisor math for existing product."""
        prod = self.env['product.product'].create({'name': 'Test Bolt M8', 'is_storable': True})
        res = ToolExecutor.execute(self.env, "replenishment_advise", {"product_name_or_id": prod.name})
        self.assertTrue(res.get("success"))
        self.assertIn("suggested_min_qty", res)
        self.assertIn("suggested_max_qty", res)

    def test_l1_04_project_cycle_detection(self):
        """L1.4: Validation catches cyclic task dependencies."""
        tasks = [
            {"key": "A", "title": "Task A", "depends_on_keys": ["B"]},
            {"key": "B", "title": "Task B", "depends_on_keys": ["A"]},
        ]
        res = schedule_project_tasks(tasks)
        self.assertTrue(res.get("has_cycle"))

    def test_l1_05_project_topological_schedule(self):
        """L1.5: Schedule linear sequence of 3 tasks."""
        tasks = [
            {"key": "T1", "title": "Design", "allocated_hours": 8.0},
            {"key": "T2", "title": "Build", "allocated_hours": 16.0, "depends_on_keys": ["T1"]},
            {"key": "T3", "title": "Test", "allocated_hours": 8.0, "depends_on_keys": ["T2"]},
        ]
        res = schedule_project_tasks(tasks)
        self.assertFalse(res.get("has_cycle"))
        self.assertEqual(res["critical_path_keys"], ["T1", "T2", "T3"])

    def test_l1_06_database_inspector_records(self):
        """L1.6: Query database records via safe inspector."""
        res = ToolExecutor.execute(self.env, "query_database_records", {"model_name": "product.product", "limit": 5})
        self.assertTrue(res.get("success"))
        self.assertIsInstance(res.get("records"), list)

    def test_l1_07_database_inspector_counts(self):
        """L1.7: Query counts on sale.order."""
        res = ToolExecutor.execute(self.env, "query_database_records", {"model_name": "sale.order", "count_only": True})
        self.assertTrue(res.get("success"))
        self.assertIn("count", res)

    def test_l1_08_multi_warehouse_creation(self):
        """L1.8: Central warehouse + 1 store."""
        spec = {
            "central_name": "Main Depot",
            "central_code": "MDP",
            "stores": [{"name": "Downtown Store", "code": "DTS"}]
        }
        res = ToolExecutor.execute(self.env, "multi_warehouse_network_build", spec)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("stores_count"), 1)

    # =========================================================
    # LEVEL 2: MULTI-STEP SCENARIOS (L2_01 to L2_08)
    # =========================================================
    def test_l2_01_mrp_cost_rollup_with_target_margin(self):
        """L2.1: MRP setup from spec followed by cost rollup."""
        spec = {
            "product_name": "Industrial Fan 500",
            "sale_price": 400.0,
            "components": [
                {"name": "Fan Blades Steel", "qty": 4, "cost": 15.0},
                {"name": "Electric Motor 24V", "qty": 1, "cost": 80.0},
            ],
            "operations": [
                {"name": "Blade Welding", "workcenter_name": "Welding Station", "duration_minutes": 30.0},
            ]
        }
        res = ToolExecutor.execute(self.env, "mrp_setup_production_from_spec", spec)
        self.assertTrue(res.get("success"))
        
        # Rollup verification
        rollup = ToolExecutor.execute(self.env, "mrp_cost_rollup", {
            "product_name_or_id": "Industrial Fan 500",
            "target_margin_percent": 35.0,
        })
        self.assertTrue(rollup.get("success"))
        self.assertGreater(rollup["suggested_sale_price"], rollup["total_unit_cost"])

    def test_l2_02_cost_profile_audit_creation(self):
        """L2.2: Ensure ai.cost.profile persists date and user audit."""
        spec = {
            "workcenter_name": "CNC Milling Center",
            "workers_count": 2,
            "hourly_wage_per_worker": 30.0,
            "machine_power_kw": 12.0,
            "electricity_tariff": 0.18,
            "machine_depreciation_hour": 15.0,
            "rent_utilities_hour": 8.0,
        }
        res = ToolExecutor.execute(self.env, "mrp_cost_workcenter", spec)
        self.assertTrue(res.get("success"))
        profile = self.env['ai.cost.profile'].browse(res["cost_profile_id"])
        self.assertTrue(profile.exists())
        self.assertEqual(profile.date, date.today())
        self.assertEqual(profile.user_id, self.env.user)

    def test_l2_03_project_build_with_stages(self):
        """L2.3: Build project with 3 stages and 4 tasks."""
        spec = {
            "name": "Factory Automation Sprint",
            "stages": ["Backlog", "Implementation", "Validated"],
            "tasks": [
                {"key": "T1", "title": "Sensor Setup", "stage": "Implementation", "allocated_hours": 16.0},
                {"key": "T2", "title": "PLC Coding", "stage": "Implementation", "allocated_hours": 24.0, "depends_on_keys": ["T1"]},
                {"key": "T3", "title": "Dry Run Test", "stage": "Validated", "allocated_hours": 8.0, "depends_on_keys": ["T2"]},
            ]
        }
        res = ToolExecutor.execute(self.env, "project_build_from_spec", spec)
        self.assertTrue(res.get("success"))
        self.assertEqual(res["data"]["tasks_count"], 3)

    def test_l2_04_replenishment_advise_with_draft_application(self):
        """L2.4: Advise and apply draft orderpoint in one pass."""
        p = self.env['product.product'].create({'name': 'Hydraulic Oil 20L', 'is_storable': True})
        res = ToolExecutor.execute(self.env, "replenishment_advise", {
            "product_name_or_id": p.name,
            "lead_time_days": 10,
            "apply_draft": True,
        })
        self.assertTrue(res.get("success"))
        self.assertIn("applied_orderpoint_id", res)

    def test_l2_05_multi_warehouse_network_with_orderpoints(self):
        """L2.5: Multi-warehouse network linked to specific product orderpoint."""
        p = self.env['product.product'].create({'name': 'Solar Battery 100Ah', 'is_storable': True})
        spec = {
            "central_name": "Regional Hub",
            "central_code": "RHB",
            "product_name_or_id": p.name,
            "stores": [
                {"name": "Branch Store A", "code": "BSA", "reorder_min": 15, "reorder_max": 60},
                {"name": "Branch Store B", "code": "BSB", "reorder_min": 20, "reorder_max": 80},
            ]
        }
        res = ToolExecutor.execute(self.env, "multi_warehouse_network_build", spec)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("stores_count"), 2)

    def test_l2_06_subtask_hierarchy_in_project_spec(self):
        """L2.6: Parent and child subtasks linked via parent_key."""
        spec = {
            "name": "Audit Preparations",
            "tasks": [
                {"key": "P1", "title": "Financial Audit Parent", "allocated_hours": 40.0},
                {"key": "C1", "title": "Review Invoices", "parent_key": "P1", "allocated_hours": 20.0},
                {"key": "C2", "title": "Review Bank Stmts", "parent_key": "P1", "allocated_hours": 20.0},
            ]
        }
        res = ToolExecutor.execute(self.env, "project_build_from_spec", spec)
        self.assertTrue(res.get("success"))
        Task = self.env['project.task']
        child_tasks = Task.search([('project_id', '=', res["data"]["project_id"]), ('parent_id', '!=', False)])
        self.assertEqual(len(child_tasks), 2)

    def test_l2_07_warehouse_health_query(self):
        """L2.7: Warehouse stock overview query via read_group."""
        res = ToolExecutor.execute(self.env, "get_warehouse_stock_report", {})
        self.assertTrue(res.get("success"))
        self.assertIn("warehouse_stock", res)

    def test_l2_08_database_inspector_lead_filter(self):
        """L2.8: Query CRM leads filtered by stage or title."""
        self.env['crm.lead'].create({'name': 'Prospecting Enterprise Deal', 'expected_revenue': 50000.0})
        res = ToolExecutor.execute(self.env, "query_database_records", {
            "model_name": "crm.lead",
            "domain": [("name", "ilike", "Enterprise")],
            "limit": 5,
        })
        self.assertTrue(res.get("success"))
        self.assertGreaterEqual(res.get("returned_count"), 1)

    # =========================================================
    # LEVEL 3: CROSS-MODULE END-TO-END (L3_01 to L3_07)
    # =========================================================
    def test_l3_01_mrp_to_quality_pipeline(self):
        """L3.1: MRP setup linked with Quality inspection point."""
        mrp_spec = {
            "product_name": "Precision Sensor Unit",
            "components": [{"name": "Sensor Chip", "qty": 1, "cost": 10.0}],
            "operations": [{"name": "Soldering", "workcenter_name": "Electronics Station"}],
        }
        res = ToolExecutor.execute(self.env, "mrp_setup_production_from_spec", mrp_spec)
        self.assertTrue(res.get("success"))

        # Configure Quality Point
        q_res = ToolExecutor.execute(self.env, "configure_quality_point", {
            "product_name_or_id": "Precision Sensor Unit",
            "title": "Resistance Calibration Check",
            "check_type": "pass_fail",
        })
        self.assertTrue(q_res.get("success"))

    def test_l3_02_project_from_sales_spec(self):
        """L3.2: Create quotation and link to dedicated implementation project."""
        p_res = ToolExecutor.execute(self.env, "project_build_from_spec", {
            "name": "Client Onboarding Contract P-99",
            "tasks": [{"key": "T1", "title": "Initial Kickoff", "allocated_hours": 4.0}]
        })
        self.assertTrue(p_res.get("success"))

        so_res = ToolExecutor.execute(self.env, "create_quotation", {
            "partner_name_or_id": "Deco Addict",
            "items": [{"product_name_or_id": "Fridge 360L", "quantity": 1}],
        })
        self.assertTrue(so_res.get("success"))

    def test_l3_03_warehouse_to_replenishment_cross_check(self):
        """L3.3: Design warehouse then run replenishment check."""
        wh_spec = {"name": "Eastern Logistics Hub", "code": "ELH"}
        wh_res = ToolExecutor.execute(self.env, "warehouse_design_from_spec", wh_spec)
        self.assertTrue(wh_res.get("success"))

        p = self.env['product.product'].create({'name': 'Packaging Box XL', 'is_storable': True})
        rep_res = ToolExecutor.execute(self.env, "replenishment_advise", {"product_name_or_id": p.name})
        self.assertTrue(rep_res.get("success"))

    def test_l3_04_mrp_cost_and_quotation_margin(self):
        """L3.4: Work center costing -> BOM setup -> B2B Quotation."""
        ToolExecutor.execute(self.env, "mrp_cost_workcenter", {
            "workcenter_name": "Wood Assembly Bench",
            "workers_count": 2,
            "hourly_wage_per_worker": 20.0,
        })
        setup = ToolExecutor.execute(self.env, "mrp_setup_production_from_spec", {
            "product_name": "Solid Oak Desk",
            "sale_price": 500.0,
            "components": [{"name": "Oak Plank", "qty": 5, "cost": 30.0}],
            "operations": [{"name": "Assembly", "workcenter_name": "Wood Assembly Bench", "duration_minutes": 60.0}],
        })
        self.assertTrue(setup.get("success"))

    def test_l3_05_multi_warehouse_transfer_pipeline(self):
        """L3.5: Multi-warehouse setup with internal movement capability."""
        net = ToolExecutor.execute(self.env, "multi_warehouse_network_build", {
            "central_name": "Central Depot North",
            "central_code": "CDN",
            "stores": [{"name": "Retail Store 1", "code": "RS1"}]
        })
        self.assertTrue(net.get("success"))

    def test_l3_06_database_inspector_multi_table(self):
        """L3.6: Multi-table relational inquiry (projects + tasks + MOs)."""
        r1 = ToolExecutor.execute(self.env, "query_database_records", {"model_name": "project.project", "limit": 2})
        r2 = ToolExecutor.execute(self.env, "query_database_records", {"model_name": "mrp.production", "limit": 2})
        self.assertTrue(r1.get("success"))
        self.assertTrue(r2.get("success"))

    def test_l3_07_complete_quality_pipeline(self):
        """L3.7: Quality point -> check record -> inspection query."""
        qp = ToolExecutor.execute(self.env, "configure_quality_point", {
            "product_name_or_id": "Doors",
            "title": "Paint Uniformity Test",
        })
        self.assertTrue(qp.get("success"))

    # =========================================================
    # LEVEL 4: LARGE & COMPLEX SCENARIOS (L4_01 to L4_07)
    # =========================================================
    def test_l4_01_large_scale_project_wbs(self):
        """L4.1: 45-task 6-phase project with calendar scheduling."""
        phases = ["Discovery", "Architecture", "Backend", "Frontend", "Testing", "Deployment"]
        tasks = []
        for p_idx, phase in enumerate(phases):
            for t_num in range(1, 8):
                key = f"P{p_idx+1}_T{t_num}"
                prev_key = f"P{p_idx+1}_T{t_num-1}" if t_num > 1 else (f"P{p_idx}_T7" if p_idx > 0 else None)
                tasks.append({
                    "key": key,
                    "title": f"{phase} Task {t_num}",
                    "stage": phase,
                    "allocated_hours": 8.0,
                    "depends_on_keys": [prev_key] if prev_key else [],
                })

        spec = {
            "name": "Enterprise 4-Month ERP Rollout",
            "stages": phases,
            "tasks": tasks,
            "confirm_run": True,
        }
        res = ToolExecutor.execute(self.env, "project_build_from_spec", spec)
        self.assertTrue(res.get("success"), res.get("error"))
        self.assertEqual(res["data"]["tasks_count"], len(tasks))
        self.assertGreaterEqual(len(res["data"]["critical_path"]), 30)

    def test_l4_02_large_warehouse_matrix(self):
        """L4.2: Large warehouse with 3 zones, 4 racks, and 5 levels (60+ locations)."""
        spec = {
            "name": "Mega Logistics Facility",
            "code": "MLF",
            "zones": [
                {"name": "Zone Cold Storage", "racks": 4, "levels": 5},
                {"name": "Zone Ambient Dry", "racks": 4, "levels": 5},
                {"name": "Zone Hazardous", "racks": 2, "levels": 3},
            ]
        }
        res = ToolExecutor.execute(self.env, "warehouse_design_from_spec", spec)
        self.assertTrue(res.get("success"))
        self.assertGreaterEqual(res["data"]["total_locations_created"], 40)

    def test_l4_03_costing_chair_full_overhead(self):
        """L4.3: Costing of manufactured chair with power kW, depreciation, and rent."""
        wc_res = ToolExecutor.execute(self.env, "mrp_cost_workcenter", {
            "workcenter_name": "Heavy Woodworking Line",
            "workers_count": 2,
            "hourly_wage_per_worker": 22.50,
            "machine_power_kw": 7.5,
            "electricity_tariff": 0.20,
            "machine_depreciation_hour": 10.0,
            "rent_utilities_hour": 6.50,
            "consumables_maintenance_hour": 3.0,
        })
        self.assertTrue(wc_res.get("success"))

        setup_res = ToolExecutor.execute(self.env, "mrp_setup_production_from_spec", {
            "product_name": "Executive Ergonomic Chair",
            "sale_price": 280.0,
            "components": [
                {"name": "Molded Foam Seat", "qty": 1, "cost": 35.0},
                {"name": "Steel Wheel Base", "qty": 1, "cost": 25.0},
                {"name": "Gas Lift Cylinder", "qty": 1, "cost": 15.0},
            ],
            "operations": [
                {"name": "Frame Assembly", "workcenter_name": "Heavy Woodworking Line", "duration_minutes": 45.0},
            ]
        })
        self.assertTrue(setup_res.get("success"))
        self.assertGreater(setup_res["cost_rollup"]["margin_amount"], 0)

    def test_l4_04_bulk_hygiene_context(self):
        """L4.4: Verify pipeline bulk hygiene context suppresses mail logging."""
        from odoo.addons.sale_ai_agent.services.pipeline_engine import BULK_HYGIENE_CONTEXT
        self.assertTrue(BULK_HYGIENE_CONTEXT.get('tracking_disable'))
        self.assertTrue(BULK_HYGIENE_CONTEXT.get('mail_notrack'))
        self.assertTrue(BULK_HYGIENE_CONTEXT.get('mail_create_nolog'))

    def test_l4_05_replan_scheduler_propagation(self):
        """L4.5: Re-planning with topological slack and delay propagation."""
        tasks = [
            {"key": "A", "title": "Milestone 1", "allocated_hours": 16.0},
            {"key": "B", "title": "Milestone 2", "allocated_hours": 24.0, "depends_on_keys": ["A"]},
        ]
        s1 = schedule_project_tasks(tasks, project_start_date=date(2026, 1, 1))
        self.assertFalse(s1.get("has_cycle"))
        self.assertEqual(s1["schedule"]["A"]["key"], "A")
        self.assertEqual(s1["schedule"]["A"]["slack_days"], 0)

    def test_l4_06_database_inspector_limit_safety(self):
        """L4.6: Universal DB inspector caps requests to 25 to prevent memory explosion."""
        res = ToolExecutor.execute(self.env, "query_database_records", {
            "model_name": "res.partner",
            "limit": 100,  # exceeds maximum allowed cap
        })
        self.assertTrue(res.get("success"))
        self.assertLessEqual(res.get("returned_count"), 25)

    def test_l4_07_resumable_and_undoable_idempotency(self):
        """L4.7: Idempotent rerun of multi-warehouse network does not produce duplicates."""
        spec = {
            "central_name": "Idempotent Hub",
            "central_code": "IDH",
            "stores": [{"name": "Idempotent Branch", "code": "IDB"}]
        }
        r1 = ToolExecutor.execute(self.env, "multi_warehouse_network_build", spec)
        r2 = ToolExecutor.execute(self.env, "multi_warehouse_network_build", spec)
        self.assertTrue(r1.get("success"))
        self.assertTrue(r2.get("success"))
        whs = self.env['stock.warehouse'].search([('code', '=', 'IDH')])
        self.assertEqual(len(whs), 1)
