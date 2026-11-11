import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CateringPayment(models.Model):
    _name = "catering.payment"
    _description = "Catering card payment"
    _order = "id desc"

    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(
        "res.company", related="order_id.company_id", store=True, index=True
    )
    currency_id = fields.Many2one("res.currency", related="order_id.currency_id", store=True)
    amount = fields.Monetary()
    stripe_payment_intent_id = fields.Char(index=True)
    stripe_checkout_session_id = fields.Char()
    brand = fields.Char()
    last4 = fields.Char(size=4)
    status = fields.Selection(
        [("paid", "Paid"), ("failed", "Failed")],
        required=True,
        default="failed",
    )
    error_message = fields.Text()
    payment_date = fields.Datetime(default=fields.Datetime.now)
    idempotency_key = fields.Char()

    @api.constrains("last4", "stripe_payment_intent_id", "stripe_checkout_session_id")
    def _check_stored_card_bits(self):
        for payment in self:
            if payment.last4 and not re.fullmatch(r"\d{4}", payment.last4):
                raise ValidationError("Only the last 4 digits of a card can be stored.")
            intent = payment.stripe_payment_intent_id
            if intent and not re.fullmatch(r"pi_[A-Za-z0-9_]+", intent):
                raise ValidationError("The Stripe payment id is not valid.")
            session = payment.stripe_checkout_session_id
            if session and not re.fullmatch(r"cs_[A-Za-z0-9_]+", session):
                raise ValidationError("The Stripe checkout id is not valid.")
