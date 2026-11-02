import json
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
        """Test AI follow-up draft generation and email posting."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1})],
        })
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
        """Test full chat agent turn with tool execution."""
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
        """Test invoking replenishment via chat assistant."""
        Chat = self.env['ai.agent.chat'].create({
            'user_message': 'Scan inventory for products below safety stock and execute automated replenishment orders.',
        })
        Chat.action_send_message()
        self.assertTrue(Chat.history_json)
        history = json.loads(Chat.history_json)
        self.assertEqual(len(history), 2)
        assistant_resp = history[1]['content']
        self.assertTrue('Replenishment' in assistant_resp or 'Inventory' in assistant_resp)
