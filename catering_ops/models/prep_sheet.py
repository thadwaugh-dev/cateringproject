from odoo import fields, models


class CateringPrepSheet(models.Model):
    _name = "catering.prep.sheet"
    _description = "Catering Prep Sheet"
    _order = "id desc"

    name = fields.Char(required=True, default="Prep Sheet")
    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    guest_count = fields.Integer()
    line_ids = fields.One2many(
        "catering.prep.sheet.line", "sheet_id", string="Lines"
    )


class CateringPrepSheetLine(models.Model):
    _name = "catering.prep.sheet.line"
    _description = "Catering Prep Sheet Line"
    _order = "sequence, id"

    sheet_id = fields.Many2one(
        "catering.prep.sheet", required=True, ondelete="cascade"
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    item_code = fields.Char()
    quantity = fields.Float()
    uom_name = fields.Char()
