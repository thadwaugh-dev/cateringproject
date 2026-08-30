from odoo import fields, models


class CateringPackageRule(models.Model):
    _name = "catering.package.rule"
    _description = "Catering Package Quantity Rule"
    _order = "package_type_id, sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    package_type_id = fields.Many2one(
        "catering.package.type", required=True, ondelete="cascade"
    )
    main_option_id = fields.Many2one("catering.main.option", ondelete="cascade")
    item_code = fields.Char(required=True)
    uom_name = fields.Char(required=True, default="unit")
    apply_mode = fields.Selection(
        [
            ("per_option_guest", "Per guest on this option"),
            ("per_guest", "Per guest (all)"),
            ("per_10_guests", "Per 10 guests"),
            ("per_20_guests", "Per 20 guests"),
            ("addon", "Add-on"),
        ],
        required=True,
        default="per_guest",
    )
    qty = fields.Float(required=True, default=1.0)
    is_addon = fields.Boolean(default=False)
