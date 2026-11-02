from odoo import api, fields, models


class ProductComboLine(models.Model):
    _name = 'product.combo.line'
    _description = 'Composite Product Component Line'
    _order = 'sequence, id'

    parent_tmpl_id = fields.Many2one('product.template', string='Parent Product', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string='Component Product', required=True)
    quantity = fields.Float(string='Component Quantity', default=1.0, required=True)
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unit of Measure', readonly=True)
    cost_price = fields.Float(related='product_id.standard_price', string='Unit Cost', readonly=True)
    sequence = fields.Integer(string='Sequence', default=10)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_composite = fields.Boolean(
        string='Is Composite / Assembly',
        help='Indicates this product consists of multiple component sub-products (e.g. Desk = Table Top + Legs).',
    )
    component_line_ids = fields.One2many(
        'product.combo.line',
        'parent_tmpl_id',
        string='Components / Bill of Materials',
        copy=True,
    )
    total_components_cost = fields.Float(
        string='Calculated Components Cost',
        compute='_compute_total_components_cost',
        store=True,
    )

    @api.depends('component_line_ids', 'component_line_ids.quantity', 'component_line_ids.product_id')
    def _compute_total_components_cost(self):
        for tmpl in self:
            total = 0.0
            for line in tmpl.component_line_ids:
                total += (line.quantity * (line.product_id.standard_price or line.product_id.list_price or 0.0))
            tmpl.total_components_cost = total
