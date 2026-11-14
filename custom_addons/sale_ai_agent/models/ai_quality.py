# -*- coding: utf-8 -*-
"""
Lightweight Quality Inspection Models for Community Edition (Phase 11, Global Decision 7).
Provides Quality Points and Quality Checks linked to Manufacturing Orders (MRP) and Stock Pickings.

Complexity:
- Time: O(1) creation and state transition.
- Space: O(1) relational record.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class AiQualityPoint(models.Model):
    _name = 'ai.quality.point'
    _description = 'AI Quality Control Point'
    _order = 'sequence, id'

    name = fields.Char(string='Title', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    product_id = fields.Many2one('product.product', string='Product', index=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template')
    bom_id = fields.Many2one('mrp.bom', string='Bill of Materials')
    check_type = fields.Selection([
        ('pass_fail', 'Pass / Fail'),
        ('measure', 'Measurement / Tolerance'),
    ], string='Check Type', default='pass_fail', required=True)
    tolerance_min = fields.Float(string='Min Tolerance')
    tolerance_max = fields.Float(string='Max Tolerance')
    norm = fields.Float(string='Norm / Target Value')
    norm_unit = fields.Char(string='Unit of Measure')
    is_mandatory = fields.Boolean(string='Mandatory', default=True, help='If true, MO cannot be marked done until passed.')
    active = fields.Boolean(default=True)
    note = fields.Text(string='Instructions')


class AiQualityCheck(models.Model):
    _name = 'ai.quality.check'
    _description = 'AI Quality Check Record'
    _order = 'id desc'

    name = fields.Char(string='Check Reference', required=True, default=lambda self: self.env['ir.sequence'].next_by_code('ai.quality.check') or 'QC-NEW')
    point_id = fields.Many2one('ai.quality.point', string='Control Point', ondelete='restrict')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', index=True, ondelete='cascade')
    picking_id = fields.Many2one('stock.picking', string='Stock Transfer', index=True, ondelete='cascade')
    state = fields.Selection([
        ('todo', 'To Do'),
        ('pass', 'Passed'),
        ('fail', 'Failed'),
    ], string='Status', default='todo', required=True)
    check_type = fields.Selection(related='point_id.check_type', readonly=True)
    measured_value = fields.Float(string='Measured Value')
    is_mandatory = fields.Boolean(related='point_id.is_mandatory', readonly=True)
    user_id = fields.Many2one('res.users', string='Checked By', default=lambda self: self.env.user)
    notes = fields.Text(string='Inspection Notes')

    def action_pass(self):
        for check in self:
            check.write({'state': 'pass', 'user_id': self.env.user.id})

    def action_fail(self):
        for check in self:
            check.write({'state': 'fail', 'user_id': self.env.user.id})
