from odoo import fields, models


class CateringPackageType(models.Model):
    _name = "catering.package.type"
    _description = "Catering Package Type"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    rule_ids = fields.One2many("catering.package.rule", "package_type_id", string="Rules")
