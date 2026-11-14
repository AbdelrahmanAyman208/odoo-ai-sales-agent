# -*- coding: utf-8 -*-
"""
Traceability back-references for AI operations (Global Decision 8).
Adds ai_use_case_id and ai_task_id across core models so every generated or updated
record traces back cleanly to its originating AI context.

Complexity:
- Time: O(1) field access.
- Space: O(1) relational pointer with DB index.
"""
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    ai_use_case_id = fields.Many2one(
        'ai.agent.use.case',
        string='AI Use Case',
        index=True,
        ondelete='set null',
        copy=False,
        help='Originating AI Agent high-level goal.'
    )
    ai_task_id = fields.Many2one(
        'ai.agent.task',
        string='AI Sub-Task',
        index=True,
        ondelete='set null',
        copy=False,
        help='Specific AI decomposed task executing this action.'
    )


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sale_warning_text = fields.Char(
        string='Sales Warning',
        compute='_compute_sale_warning_text',
        help='Compatibility field for web client view caching.'
    )

    def _compute_sale_warning_text(self):
        for rec in self:
            rec.sale_warning_text = False

    ai_use_case_id = fields.Many2one(
        'ai.agent.use.case',
        string='AI Use Case',
        index=True,
        ondelete='set null',
        copy=False
    )
    ai_task_id = fields.Many2one(
        'ai.agent.task',
        string='AI Sub-Task',
        index=True,
        ondelete='set null',
        copy=False
    )


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    ai_use_case_id = fields.Many2one(
        'ai.agent.use.case',
        string='AI Use Case',
        index=True,
        ondelete='set null',
        copy=False
    )
    ai_task_id = fields.Many2one(
        'ai.agent.task',
        string='AI Sub-Task',
        index=True,
        ondelete='set null',
        copy=False
    )


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    ai_use_case_id = fields.Many2one(
        'ai.agent.use.case',
        string='AI Use Case',
        index=True,
        ondelete='set null',
        copy=False
    )
    ai_task_id = fields.Many2one(
        'ai.agent.task',
        string='AI Sub-Task',
        index=True,
        ondelete='set null',
        copy=False
    )


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    ai_use_case_id = fields.Many2one(
        'ai.agent.use.case',
        string='AI Use Case',
        index=True,
        ondelete='set null',
        copy=False
    )
    ai_task_id = fields.Many2one(
        'ai.agent.task',
        string='AI Sub-Task',
        index=True,
        ondelete='set null',
        copy=False
    )
