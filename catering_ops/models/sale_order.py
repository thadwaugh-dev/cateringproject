from odoo import api, fields, models
from odoo.exceptions import UserError

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
    "catering_hummus_qty",
    "catering_pita_cut_style",
    "catering_pita_grilled",
    "catering_pita_fried",
    "catering_needs_ice",
    "catering_cookie_qty",
    "catering_baklava_qty",
    "catering_mini_baklava_qty",
    "catering_dessert_triangle_qty",
    "catering_sweet_tea_qty",
    "catering_unsweet_tea_qty",
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
    catering_platter_total = fields.Integer(
        string="Platter total",
        compute="_compute_catering_platter_total",
        help="Sum of chicken + gyro + falafel + steak + salmon + lamb. Must equal Guest count.",
    )
    catering_platter_status = fields.Char(
        string="Platter check",
        compute="_compute_catering_platter_total",
    )
    catering_hummus = fields.Boolean(string="Hummus add-on")
    catering_hummus_qty = fields.Integer(
        string="Hummus for (people)",
        default=0,
        help="People the hummus add-on covers. Hummus lb and hummus pita add-on scale from this, not guest count.",
    )
    catering_needs_ice = fields.Boolean(string="Needs ice", default=True)
    # Legacy unused after multi-qty; kept so Upgrade does not explode old views briefly.
    catering_dessert = fields.Selection(
        [
            ("none", "None"),
            ("cookie", "Chocolate chip cookie"),
        ],
        string="Dessert (legacy)",
        default="none",
    )
    catering_sweet_tea = fields.Boolean(string="Sweet tea (legacy)", default=False)
    catering_cookie_qty = fields.Float(string="Chocolate chip cookie", default=0.0)
    catering_baklava_qty = fields.Float(string="Baklava", default=0.0)
    catering_mini_baklava_qty = fields.Float(string="Mini baklava", default=0.0)
    catering_dessert_triangle_qty = fields.Float(string="Assorted Dessert Triangles", default=0.0)
    catering_sweet_tea_qty = fields.Float(string="Sweet tea (gal)", default=0.0)
    catering_unsweet_tea_qty = fields.Float(string="Unsweet tea (gal)", default=0.0)
    catering_pita_cut_style = fields.Selection(
        [
            ("grilled", "Grilled"),
            ("fried", "Fried"),
            ("split", "Split grilled / fried"),
        ],
        string="Cut pita style",
        default="split",
    )
    catering_pita_grilled = fields.Integer(
        string="Split: grilled people",
        help="People who want grilled cut pita. System splits total cut pita by grilled vs fried people. Leave both 0 for half/half.",
    )
    catering_pita_fried = fields.Integer(
        string="Split: fried people",
        help="People who want fried cut pita. System splits total cut pita by grilled vs fried people. Leave both 0 for half/half.",
    )
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

    @api.depends(
        "catering_guest_count",
        "catering_chicken_count",
        "catering_gyro_count",
        "catering_falafel_count",
        "catering_steak_count",
        "catering_salmon_count",
        "catering_lamb_count",
    )
    def _compute_catering_platter_total(self):
        for order in self:
            total = order._platter_guest_total()
            guests = order.catering_guest_count or 0
            order.catering_platter_total = total
            if guests <= 0:
                order.catering_platter_status = "Set Guest count"
            elif total == guests:
                order.catering_platter_status = "OK — matches Guest count"
            else:
                order.catering_platter_status = (
                    "MISMATCH — platter total %s must equal Guest count %s" % (total, guests)
                )

    def _platter_guest_total(self):
        self.ensure_one()
        return (
            (self.catering_chicken_count or 0)
            + (self.catering_gyro_count or 0)
            + (self.catering_falafel_count or 0)
            + (self.catering_steak_count or 0)
            + (self.catering_salmon_count or 0)
            + (self.catering_lamb_count or 0)
        )

    def _check_platter_matches_guests(self):
        """Raise if package/guests missing or platter counts do not equal guest count."""
        for order in self:
            if not order.catering_package_type_id:
                raise UserError("Pick a Package on the Catering tab before Compute Prep Sheet.")
            guests = order.catering_guest_count or 0
            if guests <= 0:
                raise UserError("Set Guest count before Compute Prep Sheet.")
            total = order._platter_guest_total()
            if total != guests:
                raise UserError(
                    "Platter guest counts must equal Guest count.\n\n"
                    "Guest count: %s\n"
                    "Chicken %s + Gyro %s + Falafel %s + Steak %s + Salmon %s + Lamb %s = %s\n\n"
                    "Fix the platter numbers so they add up to Guest count, Save, then Compute again."
                    % (
                        guests,
                        order.catering_chicken_count or 0,
                        order.catering_gyro_count or 0,
                        order.catering_falafel_count or 0,
                        order.catering_steak_count or 0,
                        order.catering_salmon_count or 0,
                        order.catering_lamb_count or 0,
                        total,
                    )
                )

    @api.onchange("catering_hummus")
    def _onchange_catering_hummus(self):
        for order in self:
            if order.catering_hummus:
                order.catering_hummus_qty = order.catering_guest_count or 0
            else:
                order.catering_hummus_qty = 0

    @api.onchange("catering_guest_count")
    def _onchange_guest_count_hummus_default(self):
        for order in self:
            if order.catering_hummus and not order.catering_hummus_qty:
                order.catering_hummus_qty = order.catering_guest_count or 0

    # Compute only from the button (and open-sheet actions). Auto-compute on
    # every write made Save/Compute failures hard to see and easy to desync.

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
        self._check_platter_matches_guests()
        PrepLine = self.env["catering.prep.sheet.line"]
        for order in self:
            pkg = order.catering_package_type_id
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
            hummus_qty = order.catering_hummus_qty or 0
            if order.catering_hummus and not hummus_qty:
                hummus_qty = order.catering_guest_count or 0
            if not order.catering_hummus:
                hummus_qty = 0
            raw = compute_prep_lines(
                rule_dicts,
                guest_count=order.catering_guest_count or 0,
                option_counts=option_counts,
                hummus=bool(order.catering_hummus and hummus_qty),
                hummus_count=hummus_qty,
                pita_style=order.catering_pita_cut_style or "split",
                pita_grilled=order.catering_pita_grilled or 0.0,
                pita_fried=order.catering_pita_fried or 0.0,
            )
            strip_codes = (
                "cookie",
                "baklava",
                "mini_baklava",
                "dessert_triangle",
                "sweet_tea",
                "unsweet_tea",
                "dessert_plate",
            )
            raw = [r for r in raw if r.get("item_code") not in strip_codes]
            opt_in = build_opt_in_extras(
                cookie_qty=order.catering_cookie_qty or 0.0,
                baklava_qty=order.catering_baklava_qty or 0.0,
                mini_baklava_qty=order.catering_mini_baklava_qty or 0.0,
                dessert_triangle_qty=order.catering_dessert_triangle_qty or 0.0,
                sweet_tea_qty=order.catering_sweet_tea_qty or 0.0,
                unsweet_tea_qty=order.catering_unsweet_tea_qty or 0.0,
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
                            "quantity": 0.0 if line.get("is_section") else float(line.get("quantity") or 0.0),
                            "qty_display": ""
                            if line.get("is_section")
                            else (line.get("qty_display") or ""),
                            "uom_name": line.get("uom_name") or "",
                            "category": line.get("category"),
                            "is_section": bool(line.get("is_section")),
                        }
                    )
                if vals_list:
                    PrepLine.create(vals_list)

        # Reload form so related Food/Driver previews refresh.
        self.invalidate_recordset()
        food_n = sum(len(o.catering_food_sheet_id.line_ids) for o in self)
        driver_n = sum(len(o.catering_driver_sheet_id.line_ids) for o in self)
        for order in self:
            order.message_post(
                body=(
                    "Catering prep computed. Food Sheet lines: %s. Driver Pull Sheet lines: %s."
                    % (len(order.catering_food_sheet_id.line_ids), len(order.catering_driver_sheet_id.line_ids))
                )
            )
        # Returning True reloads the form; mismatch/package issues raise UserError (modal).
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Prep sheets computed",
                "message": "Food lines: %s. Driver lines: %s. Scroll down for previews."
                % (food_n, driver_n),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_food_sheet(self):
        self.ensure_one()
        if not self.catering_food_sheet_id:
            self.action_compute_catering_prep()
        if not self.catering_food_sheet_id:
            raise UserError("Compute Prep Sheet first (Package, Guest count, and matching platter totals required).")
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
        if not self.catering_driver_sheet_id:
            raise UserError("Compute Prep Sheet first (Package, Guest count, and matching platter totals required).")
        return {
            "type": "ir.actions.act_window",
            "name": "Driver Pull Sheet",
            "res_model": "catering.prep.sheet",
            "view_mode": "form",
            "res_id": self.catering_driver_sheet_id.id,
            "target": "current",
        }
