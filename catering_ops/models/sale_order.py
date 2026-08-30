from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    catering_package_type_id = fields.Many2one("catering.package.type", string="Package")
    catering_guest_count = fields.Integer(string="Guest count")
    catering_chicken_count = fields.Integer(string="Chicken guests")
    catering_gyro_count = fields.Integer(string="Gyro guests")
    catering_falafel_count = fields.Integer(string="Falafel guests")
    catering_hummus = fields.Boolean(string="Hummus add-on")
    catering_prep_sheet_id = fields.Many2one(
        "catering.prep.sheet", string="Prep sheet", copy=False
    )
    catering_prep_line_ids = fields.One2many(
        related="catering_prep_sheet_id.line_ids", string="Prep quantities"
    )

    def action_compute_catering_prep(self):
        """Phase 3: Buffet quantity calculation. Stub in skeleton."""
        return True
