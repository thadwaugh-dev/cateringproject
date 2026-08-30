from odoo import fields, models


class CateringMainOption(models.Model):
    _name = "catering.main.option"
    _description = "Catering Main Option"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    is_protein = fields.Boolean(default=True)
    active = fields.Boolean(default=True)
