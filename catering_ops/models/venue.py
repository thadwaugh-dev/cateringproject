from odoo import api, fields, models


class CateringVenue(models.Model):
    """Delivery destination. Shared across customers; not a copy of the ordering contact."""

    _name = "catering.venue"
    _description = "Catering Venue"
    _order = "name, id"
    _rec_names_search = ["name", "contact_name", "street", "city", "zip", "phone"]

    name = fields.Char(required=True, index=True)
    contact_name = fields.Char(string="Contact", index=True)
    street = fields.Char()
    city = fields.Char(index=True)
    state_id = fields.Many2one(
        "res.country.state",
        string="State",
        domain="[('country_id', '=?', country_id)]",
    )
    zip = fields.Char(string="ZIP")
    country_id = fields.Many2one(
        "res.country",
        string="Country",
        default=lambda self: self.env.company.country_id,
    )
    phone = fields.Char()
    notes = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    partner_ids = fields.Many2many(
        "res.partner",
        "catering_venue_partner_rel",
        "venue_id",
        "partner_id",
        string="Preferred by",
        help="Customers who marked this venue as preferred. Any customer can still order here.",
    )
    order_ids = fields.One2many("sale.order", "catering_venue_id", string="Orders")
    order_count = fields.Integer(string="Orders", compute="_compute_order_count")

    @api.depends("name", "city")
    def _compute_display_name(self):
        for venue in self:
            if venue.name and venue.city:
                venue.display_name = "%s (%s)" % (venue.name, venue.city)
            else:
                venue.display_name = venue.name or ""

    @api.depends("order_ids")
    def _compute_order_count(self):
        for venue in self:
            venue.order_count = len(venue.order_ids)

    @api.onchange("country_id")
    def _onchange_country_id(self):
        for venue in self:
            if venue.state_id and venue.state_id.country_id != venue.country_id:
                venue.state_id = False

    def action_view_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Orders",
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("catering_venue_id", "=", self.id)],
            "context": {"default_catering_venue_id": self.id},
        }
