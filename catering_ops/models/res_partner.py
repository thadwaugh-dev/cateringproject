from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    catering_preferred_venue_ids = fields.Many2many(
        "catering.venue",
        "catering_venue_partner_rel",
        "partner_id",
        "venue_id",
        string="Preferred venues",
        groups="sales_team.group_sale_salesman",
        help="Venues this customer often uses. An order can still deliver to any venue.",
    )
