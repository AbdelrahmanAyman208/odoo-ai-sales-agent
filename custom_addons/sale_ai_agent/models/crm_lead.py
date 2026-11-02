from odoo import models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def action_ai_lead_followup(self):
        self.ensure_one()
        partner_id = self.partner_id.id if self.partner_id else False
        wizard = self.env['ai.sale.followup.wizard'].create({
            'lead_id': self.id,
            'partner_id': partner_id,
        })
        wizard.action_generate_draft()
        return {
            'name': 'AI Follow-up Email',
            'type': 'ir.actions.act_window',
            'res_model': 'ai.sale.followup.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
