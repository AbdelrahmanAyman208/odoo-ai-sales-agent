import json
from unittest.mock import patch
from odoo.tests.common import TransactionCase


class TestSalesAiAgent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test customer
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test ACME Corp',
            'email': 'acme@example.com',
            'phone': '+1 555 123 4567',
        })
        # Create test product
        cls.product = cls.env['product.product'].create({
            'name': 'Ergonomic Desk Pro',
            'default_code': 'DESK-PRO',
            'list_price': 450.0,
            'sale_ok': True,
        })
        # Create test opportunity
        cls.lead = cls.env['crm.lead'].create({
            'name': '50 Desks for ACME',
            'partner_id': cls.partner.id,
            'expected_revenue': 22500.0,
            'probability': 60.0,
        })

    def test_01_tool_search_products(self):
        """Test search_products tool."""
        Tools = self.env['ai.sales.tools']
        res = Tools.execute_tool('search_products', {'query': 'Ergonomic', 'limit': 5})
        self.assertIn('products', res)
        self.assertTrue(len(res['products']) >= 1)
        self.assertEqual(res['products'][0]['id'], self.product.id)

    def test_02_tool_search_partner(self):
        """Test search_partner tool."""
        Tools = self.env['ai.sales.tools']
        res = Tools.execute_tool('search_partner', {'query': 'ACME', 'limit': 5})
        self.assertIn('partners', res)
        self.assertTrue(len(res['partners']) >= 1)
        self.assertEqual(res['partners'][0]['id'], self.partner.id)

    def test_03_tool_get_pipeline_summary(self):
        """Test get_pipeline_summary tool."""
        Tools = self.env['ai.sales.tools']
        res = Tools.execute_tool('get_pipeline_summary', {})
        self.assertIn('total_open_opportunities', res)
        self.assertTrue(res['total_open_opportunities'] >= 1)
        self.assertIn('total_expected_revenue', res)

    def test_04_tool_create_quotation(self):
        """Test create_quotation tool creates a draft sale order."""
        Tools = self.env['ai.sales.tools']
        items = [{'product_name_or_id': 'Ergonomic Desk Pro', 'quantity': 2, 'price_unit': 400.0}]
        res = Tools.execute_tool('create_quotation', {
            'partner_name_or_id': self.partner.id,
            'items': items,
            'note': 'Special pricing',
        })
        self.assertTrue(res.get('success'))
        order_id = res.get('order_id')
        order = self.env['sale.order'].browse(order_id)
        self.assertEqual(order.state, 'draft')
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line[0].product_id.id, self.product.id)
        self.assertEqual(order.order_line[0].product_uom_qty, 2)
        self.assertEqual(order.amount_untaxed, 800.0)

    def test_05_ai_followup_wizard(self):
        """Test AI follow-up draft generation and email posting.

        Mocks call_llm_raw since no API key is available in test env.
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1})],
        })

        mock_response = {
            "role": "assistant",
            "content": (
                "Subject: Following up on your recent quotation\n\n"
                "<p>Dear Test ACME Corp,</p>"
                "<p>I wanted to follow up on the quotation we prepared for you.</p>"
                "<p>Best regards,<br/>Sales Team</p>"
            ),
            "tool_calls": None,
        }

        with patch.object(
            type(self.env['ai.agent.service']),
            'call_llm_raw',
            return_value=mock_response,
        ):
            wizard = self.env['ai.sale.followup.wizard'].create({
                'order_id': order.id,
                'partner_id': self.partner.id,
                'tone': 'professional',
            })
            wizard.action_generate_draft()
            self.assertTrue(wizard.email_subject)
            self.assertTrue(wizard.email_body)

            # Test sending
            wizard.action_send_email()
            # Verify chatter log
            messages = order.message_ids
            self.assertTrue(any(wizard.email_subject in (m.subject or '') for m in messages))

    def test_06_ai_agent_chat_turn(self):
        """Test full chat agent turn with tool execution.

        Mocks run_agent_turn to return a Claude-style response with
        tool execution results, simulating the real agent loop.
        """
        mock_result = {
            "content": "### 📊 Sales Pipeline Summary\n\nTotal Open Deals: 3\nTotal Pipeline Value: $22,500.00",
            "executed_tools": [
                {
                    "tool": "get_pipeline_summary",
                    "args": {},
                    "result": {"success": True, "total_open_opportunities": 3},
                    "duration": 0.05,
                }
            ],
            "duration": 1.2,
        }

        with patch.object(
            type(self.env['ai.agent.service']),
            'run_agent_turn',
            return_value=mock_result,
        ):
            Chat = self.env['ai.agent.chat'].create({
                'user_message': 'What is the status of our sales pipeline?',
            })
            Chat.action_send_message()
            self.assertTrue(Chat.history_json)
            history = json.loads(Chat.history_json)
            self.assertEqual(len(history), 2)  # 1 user + 1 assistant
            self.assertEqual(history[0]['role'], 'user')
            self.assertEqual(history[1]['role'], 'assistant')
            self.assertIn('Pipeline', history[1]['content'])

    def test_07_inventory_replenishment_tools(self):
        """Test check_inventory_replenishment and create_replenishment_order tools."""
        Tools = self.env['ai.sales.tools']

        # 1. Test scanning inventory
        rep_check = Tools.execute_tool('check_inventory_replenishment', {'threshold': 10.0})
        self.assertTrue(rep_check.get('success'))
        self.assertIn('total_products_checked', rep_check)
        self.assertIn('low_stock_count', rep_check)

        # 2. Test generating replenishment purchase order
        rep_order = Tools.execute_tool('create_replenishment_order', {
            'product_name_or_id': self.product.id,
            'quantity': 25.0,
        })
        self.assertTrue(rep_order.get('success'))
        po_id = rep_order.get('po_id')
        self.assertTrue(po_id)
        po = self.env['purchase.order'].browse(po_id)
        self.assertTrue(po.exists())
        self.assertEqual(po.state, 'draft')
        self.assertEqual(len(po.order_line), 1)
        self.assertEqual(po.order_line[0].product_id.id, self.product.id)
        self.assertEqual(po.order_line[0].product_qty, 25.0)
        self.assertIn('Auto-Replenishment', po.origin)

    def test_08_replenishment_chat_turn(self):
        """Test invoking replenishment via chat assistant.

        Mocks run_agent_turn to simulate Claude calling inventory tools.
        """
        mock_result = {
            "content": (
                "I've scanned your Inventory and found 3 low-stock items. "
                "I've created a Replenishment order for Ergonomic Desk Pro."
            ),
            "executed_tools": [
                {
                    "tool": "check_inventory_replenishment",
                    "args": {"threshold": 10.0},
                    "result": {"success": True, "low_stock_count": 3},
                    "duration": 0.02,
                },
                {
                    "tool": "create_replenishment_order",
                    "args": {"product_name_or_id": "Ergonomic Desk Pro", "quantity": 25.0},
                    "result": {"success": True, "po_name": "P00001"},
                    "duration": 0.04,
                }
            ],
            "duration": 1.5,
        }

        with patch.object(
            type(self.env['ai.agent.service']),
            'run_agent_turn',
            return_value=mock_result,
        ):
            Chat = self.env['ai.agent.chat'].create({
                'user_message': 'Scan inventory for products below safety stock and execute automated replenishment orders.',
            })
            Chat.action_send_message()
            self.assertTrue(Chat.history_json)
            history = json.loads(Chat.history_json)
            self.assertEqual(len(history), 2)
            assistant_resp = history[1]['content']
            self.assertTrue('Replenishment' in assistant_resp or 'Inventory' in assistant_resp)

    def test_09_approval_two_step_confirmation(self):
        """Test Global Decision 6: Two-step confirmation for T2 operations."""
        Approval = self.env['ai.agent.approval']

        # 1. Create a draft quotation
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 5,
                'price_unit': 100.0,
            })],
        })
        self.assertEqual(order.state, 'draft')

        # 2. Compute snapshot hash
        snap_hash, rec_display, total_amount, currency_id = Approval.compute_snapshot_hash(
            'sale.order', [order.id]
        )
        self.assertTrue(snap_hash)
        self.assertEqual(total_amount, order.amount_total)

        # 3. Create approval record
        approval = Approval.create({
            'tool_name': 'confirm_sales_order',
            'request_text': 'Confirm sales order for ACME Corp',
            'res_model': 'sale.order',
            'record_ids_json': json.dumps([order.id]),
            'records_display_json': json.dumps(rec_display),
            'total_amount': total_amount,
            'currency_id': currency_id,
            'snapshot_hash': snap_hash,
        })
        self.assertEqual(approval.state, 'pending')

        # 4. Attempting Step 2 directly without Step 1 must fail
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            approval.action_step2_execute(confirmation_token='1')

        # 5. Execute Step 1 "Approve"
        approval.action_step1_approve()
        self.assertEqual(approval.state, 'step1_approved')
        self.assertTrue(approval.step1_at)

        # 6. Execute Step 2 with incorrect token must fail
        with self.assertRaises(UserError):
            approval.action_step2_execute(confirmation_token='WRONG_TOKEN')

        # 7. Execute Step 2 with correct token ("1" or "CONFIRM")
        results = approval.action_step2_execute(confirmation_token='CONFIRM')
        self.assertEqual(approval.state, 'executed')
        self.assertEqual(order.state, 'sale')
        self.assertTrue(results[0]['success'])

        # 8. Idempotency check: executing again must fail
        with self.assertRaises(UserError):
            approval.action_step2_execute(confirmation_token='CONFIRM')

    def test_10_approval_staleness_protection(self):
        """Test Global Decision 6: Stale snapshot prevents execution if data changes."""
        Approval = self.env['ai.agent.approval']

        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 2,
                'price_unit': 200.0,
            })],
        })
        snap_hash, rec_display, total_amount, currency_id = Approval.compute_snapshot_hash(
            'sale.order', [order.id]
        )
        approval = Approval.create({
            'tool_name': 'confirm_sales_order',
            'request_text': 'Confirm sales order',
            'res_model': 'sale.order',
            'record_ids_json': json.dumps([order.id]),
            'records_display_json': json.dumps(rec_display),
            'total_amount': total_amount,
            'currency_id': currency_id,
            'snapshot_hash': snap_hash,
        })
        approval.action_step1_approve()

        # Modify record in database behind the scenes (change price)
        order.order_line[0].price_unit = 350.0

        # Step 2 execution must detect change and mark approval stale
        res = approval.action_step2_execute(confirmation_token='CONFIRM')
        self.assertFalse(res.get('success'))
        self.assertTrue(res.get('stale'))
        self.assertEqual(approval.state, 'stale')
        # Order should NOT have been confirmed
        self.assertEqual(order.state, 'draft')
