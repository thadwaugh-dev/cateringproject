from odoo import fields, models


class CateringOrderExtra(models.Model):
    _name = "catering.order.extra"
    _description = "Catering order extra"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    order_id = fields.Many2one(
        "sale.order", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company",
        related="order_id.company_id",
        store=True,
        index=True,
    )
    name = fields.Char(string="Item", required=True)
    quantity = fields.Float(default=1.0)
    uom_name = fields.Char(string="Unit")
    note = fields.Char(string="Note")
