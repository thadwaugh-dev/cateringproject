from odoo import api, fields, models
from odoo.exceptions import UserError

from ..stripe_api import StripeClient, StripeError, get_stripe_secret_key, public_message


def _digits4(value):
    text = str(value or "").strip()
    if len(text) == 4 and text.isdigit():
        return text
    return ""


def _brand_label(value):
    letters = "".join(ch for ch in (value or "") if ch.isalpha() or ch == " ").strip()
    return letters.title()[:32]


def _card_dict(payment_method, intent):
    if isinstance(payment_method, dict) and isinstance(payment_method.get("card"), dict):
        if _digits4((payment_method.get("card") or {}).get("last4")):
            return payment_method.get("card") or {}
    if isinstance(intent, dict):
        latest = intent.get("latest_charge")
        if isinstance(latest, dict):
            details = (latest.get("payment_method_details") or {}).get("card") or {}
            if _digits4(details.get("last4")):
                return details
    if isinstance(payment_method, dict):
        return payment_method.get("card") or {}
    return {}


def _card_last4(payment_method, intent):
    return _digits4(_card_dict(payment_method, intent).get("last4"))


def _card_fields(payment_method, intent):
    card = _card_dict(payment_method, intent)
    last4 = _digits4(card.get("last4"))
    brand = _brand_label(card.get("display_brand") or card.get("brand"))
    try:
        exp_month = int(card.get("exp_month") or 0)
    except (TypeError, ValueError):
        exp_month = 0
    try:
        exp_year = int(card.get("exp_year") or 0)
    except (TypeError, ValueError):
        exp_year = 0
    return last4, brand, exp_month, exp_year


class SaleOrderCharge(models.Model):
    _inherit = "sale.order"

    catering_paid = fields.Boolean(string="Paid", copy=False, default=False)
    catering_payment_error = fields.Text(string="Charge error", copy=False)
    catering_charge_attempt = fields.Integer(copy=False, default=1)
    catering_checkout_session_id = fields.Char(copy=False)
    catering_payment_ids = fields.One2many("catering.payment", "order_id", string="Card payments")
    catering_card_brand = fields.Char(
        string="Card brand", compute="_compute_catering_card_display"
    )
    catering_card_last4 = fields.Char(
        string="Card last 4", compute="_compute_catering_card_display"
    )

    @api.depends(
        "catering_payment_ids.status",
        "catering_payment_ids.brand",
        "catering_payment_ids.last4",
    )
    def _compute_catering_card_display(self):
        for order in self:
            payment = order._catering_paid_payment()
            order.catering_card_brand = payment.brand or ""
            order.catering_card_last4 = payment.last4 or ""

    def _catering_paid_payment(self):
        self.ensure_one()
        return self.catering_payment_ids.filtered(lambda payment: payment.status == "paid")[:1]

    def _catering_receipt_total(self):
        self.ensure_one()
        currency = self.currency_id.name or ""
        return "%.2f %s" % (self.amount_total or 0.0, currency)

    def action_catering_stripe_charge(self):
        self.ensure_one()
        self._catering_check_can_charge()
        secret = get_stripe_secret_key(self.company_id)
        client = StripeClient(secret)
        card = self._catering_saved_card()
        if card:
            try:
                intent = client.create_off_session_payment(
                    amount=self._catering_stripe_amount()[0],
                    currency=self._catering_stripe_amount()[1],
                    customer=card.stripe_customer_id,
                    payment_method=card.stripe_payment_method_id,
                    description="Little Greek catering %s" % (self.name or ""),
                    metadata=self._catering_stripe_metadata(),
                    idempotency_key=self._catering_idempotency_key(),
                )
            except StripeError as err:
                if err.needs_authentication:
                    return self._catering_open_checkout(client)
                self._catering_mark_failed(err.public_message, intent_id=err.payment_intent_id)
                return self._catering_failed_action(err.public_message)
            if intent.get("status") == "succeeded":
                payment_method = self._catering_load_payment_method(client, intent)
                self._catering_mark_paid(intent, payment_method=payment_method)
                return self._catering_reload()
            if intent.get("status") in ("requires_action", "requires_confirmation"):
                return self._catering_open_checkout(client)
            self._catering_mark_failed(
                "Stripe did not capture the payment.",
                intent_id=intent.get("id") or "",
            )
            return self._catering_failed_action(self.catering_payment_error)
        return self._catering_open_checkout(client)

    def action_catering_confirm_checkout(self, session_id):
        """Load the Checkout Session from Stripe and record the result. The query string is not trusted."""
        self.ensure_one()
        if self.catering_paid:
            return
        self._catering_check_can_charge()
        client = StripeClient(get_stripe_secret_key(self.company_id))
        session = client.retrieve_checkout_session(session_id)
        meta = session.get("metadata") or {}
        if str(meta.get("order_id") or "") != str(self.id) or str(meta.get("company_id") or "") != str(
            self.company_id.id
        ):
            raise UserError("Stripe did not return this order. Nothing was marked paid.")
        intent = session.get("payment_intent") or {}
        if isinstance(intent, str):
            intent = client.retrieve_payment_intent(intent)
        paid = session.get("payment_status") == "paid" or intent.get("status") == "succeeded"
        if not paid:
            message = "Stripe did not capture this payment."
            last_error = (intent.get("last_payment_error") or {}).get("message")
            if last_error:
                message = public_message(last_error)
            self._catering_mark_failed(message, intent_id=intent.get("id") or "", session_id=session_id)
            return
        payment_method = self._catering_load_payment_method(client, intent)
        customer_id = session.get("customer") or intent.get("customer") or ""
        self._catering_save_card(customer_id, payment_method)
        self._catering_mark_paid(intent, session_id=session_id, payment_method=payment_method)
        self.catering_paid = True

    def action_catering_checkout_cancelled(self):
        self.ensure_one()
        if self.catering_paid:
            return
        self.catering_charge_attempt = (self.catering_charge_attempt or 1) + 1
        self.catering_checkout_session_id = False
        self.message_post(body="Card entry was cancelled. Nothing was charged.")

    def _catering_check_can_charge(self):
        self.ensure_one()
        if not self.catering_package_type_id:
            raise UserError("Set a Package on the Catering tab before charging.")
        if not self.partner_id:
            raise UserError("Set a customer before charging.")
        if self.catering_paid or self._catering_paid_payment():
            raise UserError("This order is already paid. It was not charged again.")

    def _catering_saved_card(self):
        self.ensure_one()
        return self.env["catering.partner.card"].search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )

    def _catering_stripe_amount(self):
        self.ensure_one()
        currency = self.currency_id
        decimals = currency.decimal_places if currency else 2
        amount = currency.round(self.amount_total) if currency else (self.amount_total or 0.0)
        minor = int(round(amount * (10 ** decimals)))
        if minor <= 0:
            raise UserError("This order total is zero. Nothing was charged.")
        return minor, (currency.name or "usd").lower()

    def _catering_stripe_metadata(self):
        self.ensure_one()
        return {"order_id": str(self.id), "company_id": str(self.company_id.id)}

    def _catering_idempotency_key(self):
        """Stable for this attempt so a retry after a lost response does not charge twice."""
        self.ensure_one()
        return "catering-%s-%s-%s" % (
            self.company_id.id,
            self.id,
            self.catering_charge_attempt or 1,
        )

    def _catering_base_url(self):
        url = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "http://localhost:8069"
        return url.rstrip("/")

    def _catering_open_checkout(self, client):
        self.ensure_one()
        amount, currency = self._catering_stripe_amount()
        card = self._catering_saved_card()
        base = self._catering_base_url()
        payload = {
            "mode": "payment",
            "success_url": "%s/catering/stripe/return?order_id=%s&session_id={CHECKOUT_SESSION_ID}"
            % (base, self.id),
            "cancel_url": "%s/catering/stripe/cancel?order_id=%s" % (base, self.id),
            "client_reference_id": str(self.id),
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": currency,
            "line_items[0][price_data][unit_amount]": str(amount),
            "line_items[0][price_data][product_data][name]": (
                "Little Greek catering %s" % (self.name or "order")
            )[:120],
            "payment_intent_data[setup_future_usage]": "off_session",
            "payment_method_types[0]": "card",
        }
        for key, value in self._catering_stripe_metadata().items():
            payload["metadata[%s]" % key] = value
            payload["payment_intent_data[metadata][%s]" % key] = value
        if card and card.stripe_customer_id:
            payload["customer"] = card.stripe_customer_id
        else:
            payload["customer_creation"] = "always"
            if self.partner_id.email:
                payload["customer_email"] = self.partner_id.email
        session = client.create_checkout_session(
            payload, self._catering_idempotency_key() + "-checkout"
        )
        url = session.get("url") or ""
        if not url.startswith("https://checkout.stripe.com/"):
            raise UserError("Stripe did not return a hosted payment page. Nothing was charged.")
        session_id = session.get("id") or ""
        if session_id:
            self.catering_checkout_session_id = session_id
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def _catering_save_card(self, customer_id, payment_method):
        self.ensure_one()
        if isinstance(customer_id, dict):
            customer_id = customer_id.get("id") or ""
        if not isinstance(payment_method, dict):
            return
        method_id = payment_method.get("id") or ""
        customer_id = customer_id or ""
        if not method_id.startswith("pm_") or not str(customer_id).startswith("cus_"):
            return
        last4, brand, exp_month, exp_year = _card_fields(payment_method, None)
        vals = {
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "stripe_customer_id": customer_id,
            "stripe_payment_method_id": method_id,
            "brand": brand,
            "last4": last4,
            "exp_month": exp_month,
            "exp_year": exp_year,
        }
        existing = self._catering_saved_card()
        if existing:
            existing.write(vals)
        else:
            self.env["catering.partner.card"].create(vals)

    def _catering_mark_paid(self, intent, session_id=None, payment_method=None):
        self.ensure_one()
        if self.catering_paid:
            return
        brand, last4 = self._catering_card_bits(payment_method, intent)
        intent_id = intent.get("id") if isinstance(intent, dict) else ""
        self.env["catering.payment"].create(
            {
                "order_id": self.id,
                "amount": self.amount_total,
                "stripe_payment_intent_id": intent_id or False,
                "stripe_checkout_session_id": session_id or False,
                "brand": brand,
                "last4": last4,
                "status": "paid",
                "payment_date": fields.Datetime.now(),
                "idempotency_key": self._catering_idempotency_key(),
            }
        )
        if isinstance(payment_method, dict):
            customer_id = ""
            if isinstance(intent, dict):
                customer_id = intent.get("customer") or ""
            self._catering_save_card(customer_id, payment_method)
        self.catering_paid = True
        self.catering_payment_error = False
        self._catering_queue_receipt()

    def _catering_mark_failed(self, message, intent_id="", session_id=""):
        self.ensure_one()
        message = public_message(message)
        self.catering_paid = False
        self.catering_payment_error = message
        vals = {
            "order_id": self.id,
            "amount": self.amount_total,
            "status": "failed",
            "error_message": message,
            "payment_date": fields.Datetime.now(),
            "idempotency_key": self._catering_idempotency_key(),
        }
        if intent_id and str(intent_id).startswith("pi_"):
            vals["stripe_payment_intent_id"] = intent_id
        if session_id and str(session_id).startswith("cs_"):
            vals["stripe_checkout_session_id"] = session_id
        self.env["catering.payment"].create(vals)
        self.catering_charge_attempt = (self.catering_charge_attempt or 1) + 1
        self.message_post(body="Charge failed: %s" % message)

    def _catering_load_payment_method(self, client, intent):
        """Return a payment-method dict that includes card brand and last 4.

        Checkout often leaves payment_method as an id, or as an object without
        the card hash. PaymentMethods Read can load the card. Do not call the
        Charges API.
        """
        payment_method = {}
        if isinstance(intent, dict):
            payment_method = intent.get("payment_method") or {}
        if isinstance(payment_method, str):
            payment_method = client.retrieve_payment_method(payment_method)
        if not isinstance(payment_method, dict):
            payment_method = {}
        if not _card_last4(payment_method, intent):
            method_id = payment_method.get("id") if isinstance(payment_method, dict) else ""
            if method_id:
                payment_method = client.retrieve_payment_method(method_id)
        return payment_method if isinstance(payment_method, dict) else {}

    def _catering_card_bits(self, payment_method, intent=None):
        last4, brand, _month, _year = _card_fields(payment_method, intent)
        if last4:
            return brand, last4
        saved = self._catering_saved_card()
        return (saved.brand or "", saved.last4 or "")

    def _catering_receipt_when(self):
        """Order date in the user timezone, otherwise America/Chicago."""
        self.ensure_one()
        when = self.date_order
        if not when:
            return ""
        tzname = self.env.user.tz or self.company_id.partner_id.tz or "America/Chicago"
        local = fields.Datetime.context_timestamp(self.with_context(tz=tzname), when)
        hour = int(local.strftime("%I"))
        clock = "%d:%s %s" % (hour, local.strftime("%M"), local.strftime("%p"))
        zone = local.tzname() or ""
        text = "%s %d, %d %s" % (local.strftime("%b"), local.day, local.year, clock)
        if zone:
            text = "%s %s" % (text, zone)
        return text

    def _catering_receipt_card(self):
        self.ensure_one()
        payment = self._catering_paid_payment()
        brand = payment.brand or ""
        last4 = payment.last4 or ""
        if brand and last4:
            return "%s ending %s" % (brand, last4)
        if last4:
            return "Card ending %s" % last4
        return ""

    def _catering_queue_receipt(self):
        self.ensure_one()
        if not self.partner_id.email:
            self.message_post(
                body="Payment captured. No receipt email was sent because the customer has no email address."
            )
            return
        try:
            template = self.env.ref("catering_ops.mail_template_catering_receipt")
            template.send_mail(self.id, force_send=False)
        except Exception:
            self.message_post(body="Payment captured. The receipt email could not be queued.")
            return
        self.message_post(body="Receipt email queued for %s." % self.partner_id.email)

    def _catering_reload(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }

    def _catering_failed_action(self, message):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Charge failed",
                "message": message,
                "type": "danger",
                "sticky": True,
                "next": self._catering_reload(),
            },
        }
