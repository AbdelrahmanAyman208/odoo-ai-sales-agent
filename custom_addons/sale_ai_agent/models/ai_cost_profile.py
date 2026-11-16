# -*- coding: utf-8 -*-
"""
AI Work Center Cost Profile Model (Phase 5 & Addendum 4).
Maintains date-stamped, auditable breakdowns of work center hourly costs:
labor, machine power (kW) x electricity tariff, depreciation, rent/utilities overhead.

Complexity:
- Time: O(1) creation/read.
- Space: O(1) record size.
"""
from odoo import api, fields, models


class AiCostProfile(models.Model):
    _name = 'ai.cost.profile'
    _description = 'Work Center AI Cost Profile & Breakdown'
    _order = 'date desc, id desc'

    workcenter_id = fields.Many2one('mrp.workcenter', string='Work Center', required=True, ondelete='cascade', index=True)
    date = fields.Date(string='Calculation Date', default=fields.Date.context_today, required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id, required=True)

    # Cost breakdown components
    labor_cost_hour = fields.Monetary(string='Labor Cost / Hour', default=0.0)
    power_kw = fields.Float(string='Machine Power (kW)', default=0.0)
    electricity_tariff = fields.Float(string='Electricity Tariff / kWh', default=0.0)
    power_cost_hour = fields.Monetary(string='Electricity Cost / Hour', compute='_compute_power_cost', store=True)

    depreciation_cost_hour = fields.Monetary(string='Machine Depreciation / Hour', default=0.0)
    rent_utilities_hour = fields.Monetary(string='Rent & Utilities Allocation / Hour', default=0.0)
    consumables_hour = fields.Monetary(string='Consumables & Maintenance / Hour', default=0.0)
    other_overhead_hour = fields.Monetary(string='Other Overhead / Hour', default=0.0)

    total_cost_hour = fields.Monetary(string='Total Computed Cost / Hour', compute='_compute_total_cost', store=True)

    components_json = fields.Text(string='Raw Spec & Components (JSON)', default='{}')
    notes = fields.Text(string='Calculation Notes & Assumptions')
    user_id = fields.Many2one('res.users', string='Calculated By', default=lambda self: self.env.user)
    use_case_id = fields.Many2one('ai.agent.use.case', string='Related Use Case', ondelete='set null')

    @api.depends('power_kw', 'electricity_tariff')
    def _compute_power_cost(self):
        for rec in self:
            rec.power_cost_hour = (rec.power_kw or 0.0) * (rec.electricity_tariff or 0.0)

    @api.depends('labor_cost_hour', 'power_cost_hour', 'depreciation_cost_hour', 'rent_utilities_hour', 'consumables_hour', 'other_overhead_hour')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost_hour = (
                (rec.labor_cost_hour or 0.0) +
                (rec.power_cost_hour or 0.0) +
                (rec.depreciation_cost_hour or 0.0) +
                (rec.rent_utilities_hour or 0.0) +
                (rec.consumables_hour or 0.0) +
                (rec.other_overhead_hour or 0.0)
            )
