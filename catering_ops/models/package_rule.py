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
        ],
        required=True,
        default="per_guest",
    )
    qty = fields.Float(required=True, default=1.0)
    is_addon = fields.Boolean(default=False)
    display_uom_name = fields.Char(
        help="If set, prep sheet uses this UoM after display_divisor."
    )
    display_divisor = fields.Float(
        help="Divide raw qty by this for the sheet. Gyro: 16 (oz to lb)."
    )
    display_round = fields.Selection(
        [
            ("none", "None"),
            ("up_0_5", "Round up to nearest 0.5"),
        ],
        default="none",
        required=True,
    )
    merge_group = fields.Char(
        help="Rules with the same group are summed before the sheet prints. pita_cut combines base + hummus extra."
    )

    def apply_kitchen_display_defaults(self):
        """Force kitchen-display flags. Seed XML is noupdate so Upgrade skips those records."""
        rules = self.search([]) if not self else self
        mapping = {
            "gyro_oz": {"display_uom_name": "lb", "display_divisor": 16.0},
            "pita_base": {"merge_group": "pita_cut"},
            "pita_hummus": {"merge_group": "pita_cut"},
            "salad_pan": {"display_round": "up_0_5"},
        }
        for rule in rules:
            vals = mapping.get(rule.item_code)
            if vals:
                rule.write(vals)
        return True

