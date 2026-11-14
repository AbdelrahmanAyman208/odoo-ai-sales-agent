# -*- coding: utf-8 -*-
"""
CSRF-protected HTTP / JSON-RPC Controller for Human Approval Engine.
Implements Rule 1 & Rule 2 of Global Decision 6:
- Only real user bound to session can trigger execution
- NOT exposed as an LLM tool
"""
import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AiAgentApprovalController(http.Controller):

    @http.route('/sale_ai_agent/approval/card_data', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def get_approval_card(self, approval_id: int):
        """
        Fetches approval card data strictly from DB.
        Rule 4: The card is rendered ONLY from database data, never from LLM text.
        """
        approval = request.env['ai.agent.approval'].browse(approval_id)
        if not approval.exists():
            return {'success': False, 'error': 'Approval record not found.'}

        try:
            approval.check_is_valid()
        except Exception as e:
            return {'success': False, 'error': str(e), 'state': approval.state}

        # Check permission
        user = request.env.user
        ICP = request.env['ir.config_parameter'].sudo()
        allow_manager = ICP.get_bool('sale_ai_agent.approval_allow_manager', False)

        can_approve = (user.id == approval.requested_by.id) or (
            allow_manager and (
                user.has_group('sales_team.group_sale_manager') or
                user.has_group('purchase.group_purchase_manager') or
                user.has_group('stock.group_stock_manager')
            )
        )

        records_detail = []
        if approval.records_display_json:
            try:
                records_detail = json.loads(approval.records_display_json)
            except Exception:
                pass

        return {
            'success': True,
            'approval_id': approval.id,
            'name': approval.name,
            'state': approval.state,
            'can_approve': can_approve,
            'tool_name': approval.tool_name,
            'request_text': approval.request_text,
            'requested_by': {
                'id': approval.requested_by.id,
                'name': approval.requested_by.name,
                'login': approval.requested_by.login,
                'company': approval.requested_by.company_id.name,
            },
            'target_model': approval.res_model,
            'records_count': len(records_detail),
            'records': records_detail,
            'total_amount': approval.total_amount,
            'currency': approval.currency_id.symbol if approval.currency_id else '',
            'created_at': str(approval.create_date),
            'expires_at': str(approval.expires_at),
        }

    @http.route('/sale_ai_agent/approval/step1', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def step1_approve(self, approval_id: int, excluded_ids: list = None):
        """Step 1 Approval execution."""
        approval = request.env['ai.agent.approval'].browse(approval_id)
        if not approval.exists():
            return {'success': False, 'error': 'Approval record not found.'}

        try:
            approval.action_step1_approve(excluded_record_ids=excluded_ids)
            return {
                'success': True,
                'approval_id': approval.id,
                'state': approval.state,
                'total_amount': approval.total_amount,
                'remaining_count': len(json.loads(approval.record_ids_json)),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/sale_ai_agent/approval/step2', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def step2_execute(self, approval_id: int, confirmation_token: str, password: str = None):
        """Step 2 Final Execution."""
        approval = request.env['ai.agent.approval'].browse(approval_id)
        if not approval.exists():
            return {'success': False, 'error': 'Approval record not found.'}

        # Optional setting: check password re-authentication if configured
        ICP = request.env['ir.config_parameter'].sudo()
        require_reauth = ICP.get_bool('sale_ai_agent.approval_require_reauth', False)
        if require_reauth:
            if not password:
                return {'success': False, 'error': 'Password re-authentication is required to complete execution.'}
            try:
                request.env.user._check_credentials(password, {'interactive': True})
            except Exception:
                return {'success': False, 'error': 'Password authentication failed.'}

        try:
            results = approval.action_step2_execute(confirmation_token=confirmation_token)
            return {
                'success': True,
                'approval_id': approval.id,
                'state': approval.state,
                'results': results,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/sale_ai_agent/approval/reject', type='jsonrpc', auth='user', methods=['POST'], csrf=True)
    def reject_approval(self, approval_id: int, reason: str = ""):
        """Reject approval."""
        approval = request.env['ai.agent.approval'].browse(approval_id)
        if not approval.exists():
            return {'success': False, 'error': 'Approval record not found.'}

        try:
            approval.action_reject(reason=reason)
            return {'success': True, 'approval_id': approval.id, 'state': approval.state}
        except Exception as e:
            return {'success': False, 'error': str(e)}
