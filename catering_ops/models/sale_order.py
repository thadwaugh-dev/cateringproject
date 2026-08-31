from odoo import api, fields, models

from ..qty_engine import compute_prep_lines

CATERING_WRITE_FIELDS = {
    "catering_package_type_id",
    "catering_guest_count",
    "catering_chicken_count",
    "catering_gyro_count",
    "catering_falafel_count",
    "catering_hummus",
    "catering_pita_cut_style",
    "catering_pita_grilled",
    "catering_pita_fried",
}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    catering_package_type_id = fields.Many2one("catering.package.type", string="Package")
    catering_guest_count = fields.Integer(string="Guest count")
    catering_chicken_count = fields.Integer(string="Chicken guests")
    catering_gyro_count = fields.Integer(string="Gyro guests")
    catering_falafel_count = fields.Integer(string="Falafel guests")
    catering_hummus = fields.Boolean(string="Hummus add-on")
    catering_pita_cut_style = fields.Selection(
        [
            ("grilled", "Grilled"),
            ("fried", "Fried"),
            ("split", "Split grilled / fried"),
        ],
        string="Cut pita style",
        default="grilled",
    )
    catering_pita_grilled = fields.Float(string="Split: grilled pita")
    catering_pita_fried = fields.Float(string="Split: fried pita")
    catering_prep_sheet_id = fields.Many2one(
        "catering.prep.sheet", string="Prep sheet", copy=False
    )
    catering_prep_line_ids = fields.One2many(
        related="catering_prep_sheet_id.line_ids",
        string="Prep quantities",
        readonly=False,
    )

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

    def action_compute_catering_prep(self):
        PrepSheet = self.env["catering.prep.sheet"]
        PrepLine = self.env["catering.prep.sheet.line"]
        for order in self:
            pkg = order.catering_package_type_id
            sheet = order.catering_prep_sheet_id
            if not pkg:
                if sheet:
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
            if not sheet:
                sheet = PrepSheet.create(
                    {
                        "name": "Prep %s" % (order.name or "draft"),
                        "order_id": order.id,
                        "guest_count": order.catering_guest_count or 0,
                    }
                )
                order.with_context(skip_catering_prep=True).write(
                    {"catering_prep_sheet_id": sheet.id}
                )
            else:
                sheet.guest_count = order.catering_guest_count or 0
                sheet.line_ids.unlink()
            lines = compute_prep_lines(
                rule_dicts,
                guest_count=order.catering_guest_count or 0,
                option_counts=option_counts,
                hummus=order.catering_hummus,
                pita_style=order.catering_pita_cut_style or "grilled",
                pita_grilled=order.catering_pita_grilled or 0.0,
                pita_fried=order.catering_pita_fried or 0.0,
            )
            vals_list = []
            for line in lines:
                vals_list.append(
                    {
                        "sheet_id": sheet.id,
                        "sequence": line["sequence"],
                        "name": line["name"],
                        "item_code": line["item_code"],
                        "quantity": line["quantity"],
                        "uom_name": line["uom_name"],
                    }
                )
            if vals_list:
                PrepLine.create(vals_list)
        return True
