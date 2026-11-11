import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CateringPartnerCard(models.Model):
    """Stripe customer and payment-method ids for one customer at one company.

    A Fayetteville token is a different Stripe account from Little Rock.
    The card number is never stored.
    """

    _name = "catering.partner.card"
    _description = "Catering saved card token"
    _order = "id desc"
    _rec_name = "stripe_payment_method_id"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    stripe_customer_id = fields.Char(required=True, index=True)
    stripe_payment_method_id = fields.Char(required=True)
    brand = fields.Char()
    last4 = fields.Char(size=4)
    exp_month = fields.Integer()
    exp_year = fields.Integer()

    _sql_constraints = [
        (
            "partner_company_uniq",
            "unique(partner_id, company_id)",
            "A customer can have one saved card per company.",
        ),
    ]

    @api.constrains("last4", "stripe_customer_id", "stripe_payment_method_id")
    def _check_token_shape(self):
        for card in self:
            if card.last4 and not re.fullmatch(r"\d{4}", card.last4):
                raise ValidationError("Only the last 4 digits of a card can be stored.")
            if not re.fullmatch(r"cus_[A-Za-z0-9_]+", card.stripe_customer_id or ""):
                raise ValidationError("The saved Stripe customer id is not valid.")
            if not re.fullmatch(r"pm_[A-Za-z0-9_]+", card.stripe_payment_method_id or ""):
                raise ValidationError("The saved Stripe payment method id is not valid.")
