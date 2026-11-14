# -*- coding: utf-8 -*-
"""
Test Suite for Intent Routing, Domain Knowledge Grounding, and Diagnostic Tools.
"""
from odoo.tests.common import TransactionCase
from ..models.intent_router import route_intent, get_playbook_for_domain, build_system_prompt_with_grounding
from ..tools import ToolExecutor


class TestKnowledgeAndDiagnostics(TransactionCase):

    def test_01_intent_routing(self):
        """Verify queries correctly map to their target domain."""
        self.assertEqual(route_intent("Create BOM with 4 legs and table top"), "mrp")
        self.assertEqual(route_intent("Produce 10 units on manufacturing order"), "mrp")
        self.assertEqual(route_intent("Compare vendor offers and find cheapest supplier"), "purchase")
        self.assertEqual(route_intent("Check stock on hand in warehouse"), "inventory")
        self.assertEqual(route_intent("Show CRM deals and expected pipeline revenue"), "crm")
        self.assertEqual(route_intent("Create quotation for customer ACME"), "sales")

    def test_02_playbook_injection(self):
        """Verify targeted playbook loading and caching."""
        mrp_playbook = get_playbook_for_domain("mrp")
        self.assertIn("Bill of Materials", mrp_playbook)
        self.assertIn("Make-to-Order", mrp_playbook)

        base_prompt = "You are an AI implementer."
        grounded, domain = build_system_prompt_with_grounding(base_prompt, "Create BOM for custom desk")
        self.assertEqual(domain, "mrp")
        self.assertIn("--- DOMAIN KNOWLEDGE PLAYBOOK (MRP) ---", grounded)

    def test_03_diagnostic_tools(self):
        """Test self-check diagnostic tools execution."""
        # 1. System config check
        sys_res = ToolExecutor.execute(self.env, "check_system_configuration", {})
        self.assertTrue(sys_res.get("success"))
        self.assertIn("modules_installed", sys_res)
        self.assertTrue(sys_res["modules_installed"].get("sale_management"))

        # 2. Product routes and BOM check
        product = self.env["product.product"].create({
            "name": "Diagnostic Test Product",
            "list_price": 100.0,
            "sale_ok": True,
        })
        diag_res = ToolExecutor.execute(self.env, "check_product_routes_and_bom", {"product_name_or_id": product.id})
        self.assertTrue(diag_res.get("success"))
        self.assertFalse(diag_res.get("has_bom"))
        self.assertIn("configured_routes", diag_res)

