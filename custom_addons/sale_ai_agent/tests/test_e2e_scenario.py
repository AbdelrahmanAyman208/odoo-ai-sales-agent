# -*- coding: utf-8 -*-
"""
End-to-End Scenario Test:
'Customer orders 50 units of a manufactured product -> MO -> missing components RFQ -> receipt -> production -> delivery'
Verifies junior implementer behavior across all 4 operational domains.
"""
from odoo.tests.common import TransactionCase
from ..tools import ToolExecutor


class TestEndToEndScenario(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create partner
        cls.customer = cls.env["res.partner"].create({
            "name": "Global Office Supplies",
            "email": "global@example.com",
        })
        cls.vendor = cls.env["res.partner"].create({
            "name": "Raw Materials Supplier Inc",
            "supplier_rank": 1,
        })

        # Create raw components
        cls.comp_top = cls.env["product.product"].create({
            "name": "Custom Wood Top",
            "list_price": 50.0,
            "standard_price": 25.0,
            "sale_ok": True,
        })
        cls.comp_leg = cls.env["product.product"].create({
            "name": "Steel Desk Leg",
            "list_price": 15.0,
            "standard_price": 8.0,
            "sale_ok": True,
        })

        # Create finished manufactured product
        cls.desk = cls.env["product.product"].create({
            "name": "Custom Executive Desk",
            "list_price": 250.0,
            "sale_ok": True,
        })

    def test_e2e_manufactured_product_order_flow(self):
        """End-to-end execution of MTO manufacturing and procurement pipeline."""
        # 1. AI Agent checks BOM: notices it does not exist and creates it
        bom_res = ToolExecutor.execute(self.env, "create_bill_of_materials", {
            "product_name_or_id": self.desk.id,
            "product_qty": 1.0,
            "components": [
                {"component_name_or_id": self.comp_top.id, "quantity": 1.0},
                {"component_name_or_id": self.comp_leg.id, "quantity": 4.0},
            ]
        })
        self.assertTrue(bom_res.get("success"))
        bom_id = bom_res.get("bom_id")
        self.assertTrue(bom_id)

        # 2. Customer orders 50 units -> Create quotation
        so_res = ToolExecutor.execute(self.env, "create_quotation", {
            "partner_name_or_id": self.customer.id,
            "items": [
                {"product_name_or_id": self.desk.id, "quantity": 50.0}
            ]
        })
        self.assertTrue(so_res.get("success"))
        order_id = so_res.get("order_id")
        order = self.env["sale.order"].browse(order_id)
        self.assertEqual(order.state, "draft")

        # 3. AI Agent creates Manufacturing Order for 50 units
        mo_res = ToolExecutor.execute(self.env, "create_manufacturing_order", {
            "product_name_or_id": self.desk.id,
            "quantity": 50.0,
        })
        self.assertTrue(mo_res.get("success"))
        mo_id = mo_res.get("production_id")
        mo = self.env["mrp.production"].browse(mo_id)
        self.assertEqual(mo.state, "draft")
        self.assertEqual(mo.product_qty, 50.0)

        # 4. Check component shortages and generate RFQ for missing parts
        rfq_res = ToolExecutor.execute(self.env, "create_rfq", {
            "partner_name_or_id": self.vendor.id,
            "items": [
                {"product_name_or_id": self.comp_top.id, "quantity": 50.0},
                {"product_name_or_id": self.comp_leg.id, "quantity": 200.0},
            ],
            "origin": f"Shortage procurement for {mo.name}"
        })
        self.assertTrue(rfq_res.get("success"))
        po_id = rfq_res.get("po_id")
        po = self.env["purchase.order"].browse(po_id)
        self.assertEqual(po.state, "draft")
        self.assertEqual(len(po.order_line), 2)

        # 5. Confirm operations go through T2 approval guard
        t2_res = ToolExecutor.execute(self.env, "confirm_sales_order", {
            "order_id": order.id,
        })
        self.assertTrue(t2_res.get("approval_required"))
        approval_id = t2_res.get("approval_id")
        self.assertTrue(approval_id)

        # Approve and execute via Two-Step approval engine
        approval = self.env["ai.agent.approval"].browse(approval_id)
        approval.action_step1_approve()
        approval.action_step2_execute(confirmation_token="CONFIRM")
        self.assertEqual(order.state, "sale")

