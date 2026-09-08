from odoo import fields, models


class CateringPrepSheet(models.Model):
    _name = "catering.prep.sheet"
    _description = "Catering Prep Sheet"
    _order = "id desc"

    name = fields.Char(required=True, default="Prep Sheet")
    sheet_type = fields.Selection(
        [
            ("food", "Food Sheet"),
            ("driver", "Driver Pull Sheet"),
        ],
        required=True,
        default="food",
    )
    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    guest_count = fields.Integer()
    # optional header mirrors (filled on compute if available)
    header_order_number = fields.Char()
    header_partner_name = fields.Char()
    header_partner_phone = fields.Char()
    header_partner_address = fields.Char()
    header_event_date = fields.Char()
    header_ready_time = fields.Char()
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
    category = fields.Selection(
        [
            ("meat", "MEAT"),
            ("pitabread", "PITABREAD"),
            ("sides", "SIDES"),
            ("extras", "EXTRAS"),
            ("desserts", "DESSERTS"),
            ("drinks", "DRINKS"),
            ("paper_goods", "PAPER GOODS"),
            ("serving_utensils", "SERVING UTENSILS"),
        ],
    )
    is_section = fields.Boolean(default=False)
