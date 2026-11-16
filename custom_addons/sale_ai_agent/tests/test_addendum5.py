# -*- coding: utf-8 -*-
"""
Test Suite for Addendum 5 v2:
- Phase 14: LangGraph State Machine, dedicated schema checkpointer, and interrupt pauses.
- Phase 15: Learning Loop models, PII sanitizer, and auto-promotion rules.
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo.addons.sale_ai_agent.models.ai_learning import sanitize_lesson_text
from odoo.addons.sale_ai_agent.graph.state import UseCaseGraphState
from odoo.addons.sale_ai_agent.graph.runtime import get_compiled_use_case_graph, run_use_case_through_graph


class TestAddendum5(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.user = cls.env.user

    def test_01_sanitizer_rejects_pii(self):
        """Sanitizer must strictly reject email addresses, phone numbers, and amounts."""
        # Clean text passes
        self.assertEqual(sanitize_lesson_text("Always set priority to high on VIP accounts."), "Always set priority to high on VIP accounts.")
        
        # Email address rejected
        with self.assertRaises(ValidationError):
            sanitize_lesson_text("Contact admin@example.com for route clearance.")
            
        # Phone number rejected
        with self.assertRaises(ValidationError):
            sanitize_lesson_text("Call +1 555-123-4567 before releasing delivery.")
            
        # Currency amount rejected
        with self.assertRaises(ValidationError):
            sanitize_lesson_text("Orders above $50,000 need CFO approval.")

    def test_02_learning_models_crud(self):
        """Verify creation and relations of feedback, lessons, and examples."""
        UseCase = self.env['ai.agent.use.case']
        use_case = UseCase.create({
            'name': 'Test Replenishment Case',
            'prompt': 'Order 50 units of desk',
            'state': 'done',
        })

        # Feedback
        Feedback = self.env['ai.agent.feedback']
        fb = Feedback.create({
            'use_case_id': use_case.id,
            'signal': 'thumbs_up',
            'reason': 'Fast execution and accurate lead times.',
        })
        self.assertTrue(fb.id)
        self.assertEqual(fb.signal, 'thumbs_up')

        # Lesson
        Lesson = self.env['ai.agent.lesson']
        lesson = Lesson.create({
            'domain': 'inventory',
            'trigger': 'insufficient_replenish_route',
            'guidance': 'Verify that supplier route is active on product template before triggering replenishment.',
            'type': 'config_gotcha',
            'state': 'approved',
            'support_count': 3,
        })
        self.assertTrue(lesson.id)
        self.assertEqual(lesson.state, 'approved')

        # Example
        Example = self.env['ai.agent.example']
        ex = Example.create({
            'use_case_id': use_case.id,
            'domain': 'inventory',
            'quality_score': 0.95,
            'state': 'verified',
        })
        self.assertTrue(ex.id)

    def test_03_langgraph_top_graph_structure(self):
        """Verify that LangGraph top graph compiles cleanly with all required G11 nodes."""
        graph = get_compiled_use_case_graph(self.env)
        self.assertIsNotNone(graph)
        
        expected_nodes = {
            'extract_spec', 'preflight', 'validate', 'spec_correction',
            'preview_gate', 'execute_chunk', 'approval_gate', 'verify', 'report'
        }
        actual_nodes = set(graph.nodes.keys())
        for n in expected_nodes:
            self.assertIn(n, actual_nodes, f"Missing required node {n} in graph!")

    def test_04_execution_through_graph(self):
        """Verifies running a use case through the compiled graph runtime."""
        UseCase = self.env['ai.agent.use.case']
        Task = self.env['ai.agent.task']
        use_case = UseCase.create({
            'name': 'Simple Graph Test Case',
            'prompt': 'Check stock availability for all products',
            'state': 'planning',
        })
        Task.create({
            'use_case_id': use_case.id,
            'sequence': 10,
            'title': 'Check system capabilities',
            'tool_name': 'get_system_capabilities',
            'arguments_json': '{}',
            'state': 'pending',
        })
        
        # Execute directly through graph with active test environment hook
        from odoo.addons.sale_ai_agent.graph.nodes import set_test_active_env
        set_test_active_env(self.env)
        try:
            res = run_use_case_through_graph(self.env, use_case.id)
            self.assertTrue(res.get("success"), f"Execution failed: {res.get('error')}")
            self.assertIn("completed", res.get("status"))
        finally:
            set_test_active_env(None)
