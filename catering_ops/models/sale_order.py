from odoo import api, fields, models

from ..qty_engine import build_opt_in_extras, compute_prep_lines, enrich_lines, lines_for_sheet

CATERING_WRITE_FIELDS = {
    "catering_package_type_id",
    "catering_guest_count",
    "catering_chicken_count",
    "catering_gyro_count",
    "catering_falafel_count",
    "catering_steak_count",
    "catering_salmon_count",
    "catering_lamb_count",
    "catering_hummus",
    "catering_pita_cut_style",
    "catering_pita_grilled",
    "catering_pita_fried",
    "catering_needs_ice",
    "catering_dessert",
    "catering_cookie_qty",
    "catering_sweet_tea",
    "catering_sweet_tea_qty",
}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    catering_package_type_id = fields.Many2one("catering.package.type", string="Package")
    catering_guest_count = fields.Integer(string="Guest count")
    catering_chicken_count = fields.Integer(string="Chicken guests")
    catering_gyro_count = fields.Integer(string="Gyro guests")
    catering_falafel_count = fields.Integer(string="Falafel guests")
    catering_steak_count = fields.Integer(string="Steak guests")
    catering_salmon_count = fields.Integer(string="Salmon guests")
    catering_lamb_count = fields.Integer(string="Lamb guests")
    catering_hummus = fields.Boolean(string="Hummus add-on")
    catering_needs_ice = fields.Boolean(string="Needs ice", default=True)
    catering_dessert = fields.Selection(
        [
            ("none", "None"),
            ("cookie", "Chocolate chip cookie"),
        ],
        string="Dessert",
        default="none",
        required=True,
    )
    catering_cookie_qty = fields.Float(string="Cookie qty")
    catering_sweet_tea = fields.Boolean(string="Sweet tea", default=False)
    catering_sweet_tea_qty = fields.Float(string="Sweet tea (gal)")
    catering_pita_cut_style = fields.Selection(
        [
            ("grilled", "Grilled"),
            ("fried", "Fried"),
            ("split", "Split grilled / fried"),
        ],
        string="Cut pita style",
        default="split",
    )
    catering_pita_grilled = fields.Float(string="Split: grilled pita")
    catering_pita_fried = fields.Float(string="Split: fried pita")
    catering_food_sheet_id = fields.Many2one(
        "catering.prep.sheet", string="Food Sheet", copy=False
    )
    catering_driver_sheet_id = fields.Many2one(
        "catering.prep.sheet", string="Driver Pull Sheet", copy=False
    )
    # legacy alias kept so old views/data do not explode
    catering_prep_sheet_id = fields.Many2one(
        related="catering_food_sheet_id", string="Prep sheet", readonly=False
    )
    catering_food_line_ids = fields.One2many(
        related="catering_food_sheet_id.line_ids",
        string="Food sheet lines",
        readonly=False,
    )
    catering_driver_line_ids = fields.One2many(
        related="catering_driver_sheet_id.line_ids",
        string="Driver sheet lines",
        readonly=False,
    )
    catering_prep_line_ids = fields.One2many(
        related="catering_food_sheet_id.line_ids",
        string="Prep quantities",
        readonly=False,
    )


    @api.onchange("catering_dessert", "catering_guest_count")
    def _onchange_catering_dessert(self):
        for order in self:
            if order.catering_dessert == "cookie":
                if not order.catering_cookie_qty:
                    order.catering_cookie_qty = order.catering_guest_count or 0.0
            else:
                order.catering_cookie_qty = 0.0

    @api.onchange("catering_sweet_tea", "catering_guest_count")
    def _onchange_catering_sweet_tea(self):
        for order in self:
            if order.catering_sweet_tea:
                if not order.catering_sweet_tea_qty:
                    order.catering_sweet_tea_qty = 0.08 * (order.catering_guest_count or 0.0)
            else:
                order.catering_sweet_tea_qty = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders.filtered("catering_package_type_id").action_compute_catering_prep()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_catering_prep"):
            return res
        if CATERING_WRITE_FIELDS & set(vals):
            self.with_context(skip_catering_prep=True).action_compute_catering_prep()
        return res

    def _catering_header_vals(self, sheet_type):
        self.ensure_one()
        partner = self.partner_id
        vals = {
            "header_order_number": self.name or "",
            "guest_count": self.catering_guest_count or 0,
        }
        if sheet_type == "driver":
            vals["header_partner_name"] = partner.display_name if partner else ""
            vals["header_partner_phone"] = partner.phone or partner.mobile or ""
            if partner:
                parts = [
                    partner.street or "",
                    partner.street2 or "",
                    partner.city or "",
                    partner.state_id.name if partner.state_id else "",
                    partner.zip or "",
                ]
                vals["header_partner_address"] = ", ".join(p for p in parts if p)
            else:
                vals["header_partner_address"] = ""
        else:
            # food sheet: use commitment/date fields if present
            event = getattr(self, "commitment_date", False) or self.date_order
            vals["header_event_date"] = str(event) if event else ""
            vals["header_ready_time"] = ""
        return vals

    def _ensure_sheet(self, sheet_type, existing):
        PrepSheet = self.env["catering.prep.sheet"]
        title = "Food Sheet" if sheet_type == "food" else "Driver Pull Sheet"
        header = self._catering_header_vals(sheet_type)
        if not existing:
            sheet = PrepSheet.create(
                {
                    "name": "%s %s" % (title, self.name or "draft"),
                    "sheet_type": sheet_type,
                    "order_id": self.id,
                    **header,
                }
            )
            return sheet
        existing.write({"name": "%s %s" % (title, self.name or "draft"), **header})
        existing.line_ids.unlink()
        return existing

    def action_compute_catering_prep(self):
        PrepLine = self.env["catering.prep.sheet.line"]
        for order in self:
            pkg = order.catering_package_type_id
            if not pkg:
                for sheet in (order.catering_food_sheet_id | order.catering_driver_sheet_id):
                    sheet.line_ids.unlink()
                continue
            rules = self.env["catering.package.rule"].search(
                [("package_type_id", "=", pkg.id), ("active", "=", True)],
                order="sequence, id",
            )
            option_counts = {
                "chicken": order.catering_chicken_count or 0,
                "gyro": order.catering_gyro_count or 0,
                "falafel": order.catering_falafel_count or 0,
                "steak": order.catering_steak_count or 0,
                "salmon": order.catering_salmon_count or 0,
                "lamb": order.catering_lamb_count or 0,
            }
            rule_dicts = []
            for rule in rules:
                rule_dicts.append(
                    {
                        "name": rule.name,
                        "item_code": rule.item_code,
                        "uom_name": rule.uom_name,
                        "apply_mode": rule.apply_mode,
                        "qty": rule.qty,
                        "is_addon": rule.is_addon,
                        "option_code": rule.main_option_id.code
                        if rule.main_option_id
                        else None,
                        "sequence": rule.sequence,
                        "display_uom_name": rule.display_uom_name,
                        "display_divisor": rule.display_divisor,
                        "display_round": rule.display_round,
                        "merge_group": rule.merge_group,
                    }
                )
            raw = compute_prep_lines(
                rule_dicts,
                guest_count=order.catering_guest_count or 0,
                option_counts=option_counts,
                hummus=order.catering_hummus,
                pita_style=order.catering_pita_cut_style or "split",
                pita_grilled=order.catering_pita_grilled or 0.0,
                pita_fried=order.catering_pita_fried or 0.0,
            )
            # Never pull cookie/tea/dessert plates from package rules; inject from order toggles.
            raw = [r for r in raw if r.get("item_code") not in ("cookie", "sweet_tea", "dessert_plate")]
            opt_in = build_opt_in_extras(
                dessert=order.catering_dessert or "none",
                cookie_qty=order.catering_cookie_qty or 0.0,
                sweet_tea=order.catering_sweet_tea,
                sweet_tea_qty=order.catering_sweet_tea_qty or 0.0,
                guest_count=order.catering_guest_count or 0,
            )
            enriched = enrich_lines(
                raw,
                needs_ice=order.catering_needs_ice,
                include_opt_in=opt_in,
            )

            food = order._ensure_sheet("food", order.catering_food_sheet_id)
            driver = order._ensure_sheet("driver", order.catering_driver_sheet_id)
            order.with_context(skip_catering_prep=True).write(
                {
                    "catering_food_sheet_id": food.id,
                    "catering_driver_sheet_id": driver.id,
                }
            )
            for sheet_type, sheet in (("food", food), ("driver", driver)):
                vals_list = []
                for line in lines_for_sheet(enriched, sheet_type):
                    vals_list.append(
                        {
                            "sheet_id": sheet.id,
                            "sequence": line["sequence"],
                            "name": line["name"],
                            "item_code": line.get("item_code"),
                            "quantity": 0.0 if line.get("is_section") else line["quantity"],
                            "uom_name": line.get("uom_name") or "",
                            "category": line.get("category"),
                            "is_section": bool(line.get("is_section")),
                        }
                    )
                if vals_list:
                    PrepLine.create(vals_list)
        return True

    def action_open_food_sheet(self):
        self.ensure_one()
        if not self.catering_food_sheet_id:
            self.action_compute_catering_prep()
        return {
            "type": "ir.actions.act_window",
            "name": "Food Sheet",
            "res_model": "catering.prep.sheet",
            "view_mode": "form",
            "res_id": self.catering_food_sheet_id.id,
            "target": "current",
        }

    def action_open_driver_sheet(self):
        self.ensure_one()
        if not self.catering_driver_sheet_id:
            self.action_compute_catering_prep()
        return {
            "type": "ir.actions.act_window",
            "name": "Driver Pull Sheet",
            "res_model": "catering.prep.sheet",
            "view_mode": "form",
            "res_id": self.catering_driver_sheet_id.id,
            "target": "current",
        }
