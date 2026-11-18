from odoo import api, fields, models


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

    @api.model
    def apply_kitchen_display_defaults(self):
        """Force Buffet kitchen-display flags only. Seed XML is noupdate so Upgrade skips those records."""
        mapping = {
            "gyro_oz": {"display_uom_name": "lb", "display_divisor": 16.0},
            "pita_base": {"merge_group": "pita_cut", "qty": 0.5},
            "pita_hummus": {"merge_group": "pita_cut", "qty": 0.125},
            "salad_pan": {"display_round": "none"},
        }
        for item_code, vals in mapping.items():
            self.search(
                [
                    ("item_code", "=", item_code),
                    ("package_type_id.code", "=", "buffet"),
                ]
            ).write(vals)
        return True

    @api.model
    def apply_cz_comparison_updates(self):
        """Apply the 2026-11-18 CaterZen comparison rules on install and upgrade.

        Seed XML for Buffet is noupdate, so editing those files does not change
        an existing database. This method only writes the approved rows:

        - BYOP toppings (create if missing, otherwise set the approved qty)
        - deactivate per-guest cup, ice, tong, and spoon rules

        Protein, salad, hummus, tzatziki, dressing, rice, and pita rules are
        not written. Nothing is deleted.
        """
        toppings = (
            ("byop_lettuce", "Shredded lettuce", "handful", 1.0, 92),
            ("byop_tomato", "Sliced tomato", "slice", 2.0, 93),
            ("byop_onion", "Sliced onion", "ring", 3.0, 94),
        )
        package = self.env["catering.package.type"].search([("code", "=", "byop")], limit=1)
        if package:
            for item_code, name, uom_name, qty, sequence in toppings:
                vals = {
                    "name": name,
                    "package_type_id": package.id,
                    "item_code": item_code,
                    "uom_name": uom_name,
                    "apply_mode": "per_guest",
                    "qty": qty,
                    "sequence": sequence,
                    "active": True,
                    "is_addon": False,
                    "display_round": "none",
                }
                existing = self.with_context(active_test=False).search(
                    [
                        ("package_type_id", "=", package.id),
                        ("item_code", "=", item_code),
                    ],
                    limit=1,
                )
                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)
        retired = self.with_context(active_test=False).search(
            [("item_code", "in", ["cup", "ice", "small_spoon", "medium_spoon", "tongs"])]
        )
        if retired:
            retired.write({"active": False})
        return True
