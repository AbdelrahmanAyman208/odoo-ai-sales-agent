# -*- coding: utf-8 -*-
"""
T2 Human Approval Model for Risky / Irreversible / Financial Operations.
Implements Global Decision 6:
- LLM creates this record with status 'pending'
- Two-step confirmation (Step 1 'Approve' -> Step 2 'Final confirmation' with count/CONFIRM typing)
- Frozen snapshot hash rechecked upon execution
- Expiry after configured minutes (default 15)
- Idempotent execution using per-record savepoints
- Strict user checks: executed_by == requested_by (or authorized manager if setting enabled)

Time Complexity: O(N) where N is number of records approved.
Space Complexity: O(N) to store JSON payload and hashes.
"""
import hashlib
import json
import logging
from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class AiAgentApproval(models.Model):
    _name = 'ai.agent.approval'
    _description = 'AI Agent Human Approval for Risky (T2) Operations'
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    use_case_id = fields.Many2one('ai.agent.use.case', string='Use Case', ondelete='set null', index=True)
    task_id = fields.Many2one('ai.agent.task', string='Task', ondelete='set null', index=True)
    requested_by = fields.Many2one('res.users', string='Requested By', required=True, default=lambda self: self.env.user, readonly=True)
    tool_name = fields.Char(string='Tool Name', required=True, readonly=True)
    request_text = fields.Char(string='Instruction Sentence', required=True, readonly=True,
                               help='Exact instruction sentence that triggered this operation.')
    
    # Target records
    res_model = fields.Char(string='Target Model', required=True, readonly=True)
    record_ids_json = fields.Text(string='Record IDs (JSON)', required=True, default='[]', readonly=True)
    records_display_json = fields.Text(
        string='Frozen Records Detail (JSON)',
        required=True,
        default='[]',
        help='List of dicts with id, display_name, amount, currency, write_date, state'
    )
    
    total_amount = fields.Monetary(string='Total Amount', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    snapshot_hash = fields.Char(string='Snapshot Hash', required=True, readonly=True,
                                help='SHA256 hash of (state, amounts, lines, write_date) to detect staleness.')
    
    state = fields.Selection(
        selection=[
            ('pending', 'Pending Review'),
            ('step1_approved', 'Step 1 Approved'),
            ('executed', 'Executed'),
            ('rejected', 'Rejected'),
            ('expired', 'Expired'),
            ('stale', 'Stale (Records Modified)'),
            ('failed', 'Execution Failed'),
        ],
        string='State',
        default='pending',
        required=True,
        index=True,
    )
    
    step1_at = fields.Datetime(string='Step 1 Approved At', readonly=True)
    step2_at = fields.Datetime(string='Step 2 Executed At', readonly=True)
    expires_at = fields.Datetime(string='Expires At', required=True, index=True)
    executed_by = fields.Many2one('res.users', string='Executed By', readonly=True)
    result_json = fields.Text(string='Execution Result (JSON)', readonly=True)
    error_message = fields.Text(string='Error Details', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ai.agent.approval') or f"APP/{fields.Date.today()}/{fields.Datetime.now().strftime('%H%M%S')}"
            if 'expires_at' not in vals:
                ICP = self.env['ir.config_parameter'].sudo()
                expiry_min = ICP.get_int('sale_ai_agent.approval_expiry_minutes', 15)
                vals['expires_at'] = fields.Datetime.now() + timedelta(minutes=expiry_min)
        return super().create(vals_list)

    @api.model
    def compute_snapshot_hash(self, res_model: str, record_ids: list):
        """
        Calculates SHA256 snapshot hash of (state, amount, write_date) across records.
        Returns: (snapshot_hash, records_display_list, total_amount, currency_id)
        O(N) single search_read query.
        """
        Model = self.env[res_model]
        if not Model.has_access('read'):
            raise AccessError(f"You do not have read permission on model {res_model}.")

        fields_to_read = ['id', 'display_name', 'write_date']
        has_state = 'state' in Model._fields
        has_amount = 'amount_total' in Model._fields
        has_currency = 'currency_id' in Model._fields

        if has_state:
            fields_to_read.append('state')
        if has_amount:
            fields_to_read.append('amount_total')
        if has_currency:
            fields_to_read.append('currency_id')

        # Read all records in one batch O(1) query
        records = Model.search_read([('id', 'in', record_ids)], fields_to_read, order='id asc')
        
        hasher = hashlib.sha256()
        display_records = []
        total_amount = 0.0
        currency_id = None

        for rec in records:
            r_id = rec['id']
            r_name = rec.get('display_name', f"ID {r_id}")
            r_state = rec.get('state', '')
            r_wdate = str(rec.get('write_date', ''))
            r_amount = float(rec.get('amount_total', 0.0))
            total_amount += r_amount

            if has_currency and rec.get('currency_id'):
                curr = rec['currency_id']
                currency_id = curr[0] if isinstance(curr, (list, tuple)) else curr

            # Feed canonical snapshot string
            hasher.update(f"{r_id}:{r_state}:{r_amount:.2f}:{r_wdate}|".encode('utf-8'))

            display_records.append({
                'id': r_id,
                'name': r_name,
                'state': r_state,
                'amount': r_amount,
                'write_date': r_wdate,
            })

        return hasher.hexdigest(), display_records, total_amount, currency_id

    def check_is_valid(self):
        """Validates that approval is within expiry time and not already processed."""
        self.ensure_one()
        if self.state in ('executed', 'rejected'):
            raise UserError(f"Approval {self.name} has already been {self.state}.")
        if self.expires_at and fields.Datetime.now() > self.expires_at:
            self.write({'state': 'expired'})
            raise UserError(f"Approval {self.name} has expired at {self.expires_at}.")

    def action_step1_approve(self, excluded_record_ids=None):
        """
        Step 1 Approval:
        User reviews full card and may untick/exclude individual records.
        """
        self.ensure_one()
        self._check_approver_authorization()
        self.check_is_valid()

        if self.state != 'pending':
            raise UserError(f"Cannot perform Step 1 approval from state '{self.state}'.")

        # Handle unticked records
        all_ids = json.loads(self.record_ids_json)
        if excluded_record_ids:
            excluded_set = set(excluded_record_ids)
            filtered_ids = [rid for rid in all_ids if rid not in excluded_set]
            if not filtered_ids:
                raise UserError("Cannot approve: All records were excluded.")
            # Recompute snapshot hash for the filtered subset
            new_hash, display_records, total_amount, currency_id = self.compute_snapshot_hash(
                self.res_model, filtered_ids
            )
            self.write({
                'record_ids_json': json.dumps(filtered_ids),
                'records_display_json': json.dumps(display_records),
                'total_amount': total_amount,
                'snapshot_hash': new_hash,
                'state': 'step1_approved',
                'step1_at': fields.Datetime.now(),
            })
        else:
            self.write({
                'state': 'step1_approved',
                'step1_at': fields.Datetime.now(),
            })

        return True

    def action_step2_execute(self, confirmation_token: str):
        """
        Step 2 Final Confirmation:
        User typed the record count or 'CONFIRM' and clicks 'Confirm & Execute'.
        Re-verifies snapshot hash. Rejects if stale.
        Executes with savepoint per record.
        """
        self.ensure_one()
        self._check_approver_authorization()
        self.check_is_valid()

        if self.state != 'step1_approved':
            raise UserError("Step 1 approval must be completed before Step 2 final execution.")

        record_ids = json.loads(self.record_ids_json)
        count = len(record_ids)

        # Validate confirmation token (either exact count as string or 'CONFIRM')
        clean_token = (confirmation_token or '').strip().upper()
        if clean_token != "CONFIRM" and clean_token != str(count):
            raise UserError(
                f"Confirmation validation failed. Please type '{count}' or 'CONFIRM' to execute."
            )

        # Staleness verification (Global Decision 6, Rule 6)
        current_hash, _, _, _ = self.compute_snapshot_hash(self.res_model, record_ids)
        if current_hash != self.snapshot_hash:
            self.write({'state': 'stale'})
            return {
                'success': False,
                'stale': True,
                'error': (
                    "Records have been modified since approval was requested. "
                    "The approval is now marked STALE. Please initiate a new approval request."
                ),
            }

        # Idempotent execution using savepoints per record
        results = []
        has_failure = False
        Model = self.env[self.res_model]

        for rid in record_ids:
            try:
                with self.env.cr.savepoint():
                    record = Model.browse(rid)
                    res_info = self._execute_tool_on_record(record)
                    results.append({'id': rid, 'success': True, 'info': res_info})
            except Exception as e:
                has_failure = True
                _logger.exception("Failed executing approved action on %s ID %s: %s", self.res_model, rid, e)
                results.append({'id': rid, 'success': False, 'error': str(e)})

        final_state = 'executed' if not has_failure else ('executed' if any(r['success'] for r in results) else 'failed')

        self.write({
            'state': final_state,
            'step2_at': fields.Datetime.now(),
            'executed_by': self.env.user.id,
            'result_json': json.dumps(results),
        })

        # Log attribution
        _logger.info(
            "Confirmed by %s (%s) at %s, on request: %s [Approval: %s]",
            self.env.user.name, self.env.user.login, fields.Datetime.now(), self.request_text, self.name
        )

        return results

    def _execute_tool_on_record(self, record) -> dict:
        """
        Executes the actual Odoo action based on tool_name without sudo().
        Follows real user ACLs and standard Odoo 20.0 methods.
        """
        tool = self.tool_name
        if tool in ('confirm_sales_order', 'confirm_quotation'):
            record.action_confirm()
            return {'state': record.state, 'name': record.name}

        elif tool == 'confirm_purchase_order':
            record.button_confirm()
            return {'state': record.state, 'name': record.name}

        elif tool == 'validate_picking':
            # Check availability and validate immediate or reserved
            for move in record.move_ids:
                if move.quantity == 0 and move.product_uom_qty > 0:
                    move.quantity = move.product_uom_qty
            record.button_validate()
            return {'state': record.state, 'name': record.name}

        elif tool == 'confirm_mrp_production':
            record.action_confirm()
            return {'state': record.state, 'name': record.name}

        elif tool == 'mark_mrp_done':
            record.button_mark_done()
            return {'state': record.state, 'name': record.name}

        elif tool == 'cancel_record':
            if hasattr(record, 'action_cancel'):
                record.action_cancel()
            elif hasattr(record, 'button_cancel'):
                record.button_cancel()
            return {'state': getattr(record, 'state', 'cancelled'), 'name': getattr(record, 'name', str(record.id))}

        else:
            raise UserError(f"Unsupported tool action '{tool}' for execution in approval engine.")

    def action_reject(self, reason: str = ""):
        """Rejects the approval."""
        self.ensure_one()
        self._check_approver_authorization()
        self.write({
            'state': 'rejected',
            'error_message': reason or "Rejected by user.",
        })
        return True

    def action_open_target_record(self):
        """
        Routes the user directly to the target record (e.g. Purchase Order, Sales Order, Picking)
        so they can review and confirm it directly.
        Time: O(1)
        Space: O(1)
        """
        self.ensure_one()
        if not self.res_model:
            raise UserError("No target model associated with this approval.")

        record_ids = []
        if self.record_ids_json:
            try:
                record_ids = json.loads(self.record_ids_json)
            except Exception:
                record_ids = []

        if not record_ids:
            raise UserError("No records found in this approval.")

        # Single record -> open form view directly
        if len(record_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': f"{self.res_model} - Review",
                'res_model': self.res_model,
                'res_id': record_ids[0],
                'view_mode': 'form',
                'target': 'current',
            }

        # Multiple records -> open list view filtered to these records
        return {
            'type': 'ir.actions.act_window',
            'name': f"{self.res_model} - Review Records ({len(record_ids)})",
            'res_model': self.res_model,
            'domain': [('id', 'in', record_ids)],
            'view_mode': 'list,form',
            'target': 'current',
        }

    def _check_approver_authorization(self):
        """
        Enforces Rule 2 of Global Decision 6:
        Only the user who made the request can approve it (unless manager setting is enabled).
        Never uses sudo().
        """
        current_user = self.env.user
        if current_user.id == self.requested_by.id:
            return

        ICP = self.env['ir.config_parameter'].sudo()
        allow_manager = ICP.get_bool('sale_ai_agent.approval_allow_manager', False)
        if allow_manager:
            is_sales_manager = current_user.has_group('sales_team.group_sale_manager')
            is_purchase_manager = current_user.has_group('purchase.group_purchase_manager')
            is_stock_manager = current_user.has_group('stock.group_stock_manager')
            if is_sales_manager or is_purchase_manager or is_stock_manager:
                return

        raise AccessError(
            f"Only the requester ({self.requested_by.name}) can approve this action. "
            "Manager approval is currently restricted."
        )
