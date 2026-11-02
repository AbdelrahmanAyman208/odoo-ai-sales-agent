from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_ai_followup_email(self):
        self.ensure_one()
        wizard = self.env['ai.sale.followup.wizard'].create({
            'order_id': self.id,
            'partner_id': self.partner_id.id,
        })
        # Auto-generate draft on opening
        wizard.action_generate_draft()
        return {
            'name': 'AI Follow-up Email',
            'type': 'ir.actions.act_window',
            'res_model': 'ai.sale.followup.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
