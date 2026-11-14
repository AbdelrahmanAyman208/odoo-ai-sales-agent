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
        self.assertEqual(total_amount, 500.0)

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
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            approval.action_step2_execute(confirmation_token='CONFIRM')

        self.assertEqual(approval.state, 'stale')
        # Order should NOT have been confirmed
        self.assertEqual(order.state, 'draft')

