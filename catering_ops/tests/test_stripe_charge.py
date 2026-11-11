"""Stripe charges with HTTP mocked. No card number is stored."""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.catering_ops.stripe_api import get_stripe_secret_key


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def _intent(status="succeeded"):
    return {
        "id": "pi_test_success",
        "status": status,
        "customer": "cus_test_guest",
        "payment_method": {
            "id": "pm_test_card",
            "card": {"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2030},
        },
    }


@tagged("catering_ops", "post_install", "-at_install")
class TestStripeCharge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create(
            {"name": "Catering charge test", "list_price": 25.0}
        )

    def _company(self, name):
        found = self.env["res.company"].search([("name", "=", name)], limit=1)
        if found:
            return found
        return self.env["res.company"].create({"name": name})

    def _order(self, company):
        partner = self.env["res.partner"].create(
            {
                "name": "Charge Guest",
                "email": "guest@example.com",
                "company_id": company.id,
                "customer_rank": 1,
            }
        )
        venue = self.env["catering.venue"].create(
            {"name": "Charge Hall", "company_id": company.id}
        )
        package = self.env["catering.package.type"].create(
            {"name": "Buffet", "code": "charge_buffet_%s" % company.id}
        )
        order = self.env["sale.order"].with_company(company).create(
            {
                "partner_id": partner.id,
                "company_id": company.id,
                "catering_venue_id": venue.id,
                "catering_package_type_id": package.id,
                "catering_guest_count": 4,
            }
        )
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 25.0,
            }
        )
        return order

    def _saved_card(self, order):
        return self.env["catering.partner.card"].create(
            {
                "partner_id": order.partner_id.id,
                "company_id": order.company_id.id,
                "stripe_customer_id": "cus_test_guest",
                "stripe_payment_method_id": "pm_test_card",
                "brand": "visa",
                "last4": "4242",
            }
        )

    def test_no_model_field_can_hold_a_card_number(self):
        forbidden = ("pan", "cvv", "cvc", "card_number", "cardnumber", "full_number")
        models = (
            "sale.order",
            "res.partner",
            "catering.payment",
            "catering.partner.card",
        )
        for model in models:
            for name in self.env[model]._fields:
                low = name.lower()
                self.assertFalse(
                    any(token in low for token in forbidden),
                    "%s.%s looks like a card-number field" % (model, name),
                )

    def test_off_session_success_marks_paid_and_queues_receipt(self):
        company = self._company("Fayetteville")
        order = self._order(company)
        self._saved_card(order)
        calls = []

        def fake_request(method, url, data=None, params=None, headers=None, timeout=None):
            calls.append({"method": method, "url": url, "data": data, "headers": headers})
            self.assertNotIn("4242424242424242", str(data))
            self.assertTrue(headers.get("Idempotency-Key"))
            self.assertEqual(headers.get("Authorization"), "Bearer rk_test_dummy")
            return FakeResponse(200, _intent())

        with patch(
            "odoo.addons.catering_ops.models.sale_order_charge.get_stripe_secret_key",
            return_value="rk_test_dummy",
        ), patch("odoo.addons.catering_ops.stripe_api.requests.request", side_effect=fake_request):
            order.action_catering_stripe_charge()
            with self.assertRaises(UserError):
                order.action_catering_stripe_charge()

        self.assertEqual(len(calls), 1)
        self.assertIn("/v1/payment_intents", calls[0]["url"])
        self.assertTrue(order.catering_paid)
        self.assertFalse(order.catering_payment_error)
        payment = order._catering_paid_payment()
        self.assertEqual(payment.status, "paid")
        self.assertEqual(payment.brand, "visa")
        self.assertEqual(payment.last4, "4242")
        self.assertEqual(payment.stripe_payment_intent_id, "pi_test_success")
        self.assertEqual(payment.company_id, company)
        self.assertEqual(payment.amount, order.amount_total)
        self.assertEqual(order.catering_card_brand, "visa")
        self.assertEqual(order.catering_card_last4, "4242")
        mail = self.env["mail.mail"].search(
            [("model", "=", "sale.order"), ("res_id", "=", order.id)]
        )
        self.assertTrue(mail)
        body = mail.body_html or ""
        self.assertIn("Little Greek", body)
        self.assertIn("4242", body)
        self.assertNotIn("4242424242424242", body)
        self.assertIn("Receipt email queued", " ".join(order.message_ids.mapped("body")))
        for record in (order, payment, order._catering_saved_card()):
            for value in record.read()[0].values():
                self.assertNotIn("4242424242424242", str(value))

    def test_decline_is_stored_and_order_stays_unpaid(self):
        company = self._company("Fayetteville")
        order = self._order(company)
        self._saved_card(order)

        def fake_request(method, url, data=None, params=None, headers=None, timeout=None):
            return FakeResponse(
                402,
                {
                    "error": {
                        "message": "Your card was declined.",
                        "code": "card_declined",
                        "payment_intent": "pi_test_declined",
                    }
                },
            )

        with patch(
            "odoo.addons.catering_ops.models.sale_order_charge.get_stripe_secret_key",
            return_value="rk_test_dummy",
        ), patch("odoo.addons.catering_ops.stripe_api.requests.request", side_effect=fake_request):
            action = order.action_catering_stripe_charge()

        self.assertFalse(order.catering_paid)
        self.assertIn("declined", order.catering_payment_error)
        failed = order.catering_payment_ids.filtered(lambda payment: payment.status == "failed")
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed.stripe_payment_intent_id, "pi_test_declined")
        self.assertEqual(action["params"]["type"], "danger")
        self.assertIn("Charge failed", " ".join(order.message_ids.mapped("body")))

    def test_authentication_required_opens_hosted_checkout(self):
        company = self._company("Fayetteville")
        order = self._order(company)
        self._saved_card(order)
        calls = []

        def fake_request(method, url, data=None, params=None, headers=None, timeout=None):
            calls.append(url)
            if url.endswith("/v1/payment_intents"):
                return FakeResponse(
                    402,
                    {
                        "error": {
                            "message": "Authentication is required.",
                            "code": "authentication_required",
                        }
                    },
                )
            return FakeResponse(
                200,
                {
                    "id": "cs_test_checkout",
                    "url": "https://checkout.stripe.com/c/pay/cs_test_checkout",
                },
            )

        with patch(
            "odoo.addons.catering_ops.models.sale_order_charge.get_stripe_secret_key",
            return_value="rk_test_dummy",
        ), patch("odoo.addons.catering_ops.stripe_api.requests.request", side_effect=fake_request):
            action = order.action_catering_stripe_charge()

        self.assertFalse(order.catering_paid)
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertTrue(action["url"].startswith("https://checkout.stripe.com/"))
        self.assertEqual(len(calls), 2)

    def test_checkout_return_saves_token_and_marks_paid(self):
        company = self._company("Fayetteville")
        order = self._order(company)
        session = {
            "id": "cs_test_return",
            "payment_status": "paid",
            "customer": "cus_test_guest",
            "metadata": {"order_id": str(order.id), "company_id": str(company.id)},
            "payment_intent": _intent(),
        }

        def fake_request(method, url, data=None, params=None, headers=None, timeout=None):
            self.assertNotIn("4242424242424242", str(params))
            return FakeResponse(200, session)

        with patch(
            "odoo.addons.catering_ops.models.sale_order_charge.get_stripe_secret_key",
            return_value="rk_test_dummy",
        ), patch("odoo.addons.catering_ops.stripe_api.requests.request", side_effect=fake_request):
            order.action_catering_confirm_checkout("cs_test_return")

        self.assertTrue(order.catering_paid)
        card = order._catering_saved_card()
        self.assertEqual(card.stripe_customer_id, "cus_test_guest")
        self.assertEqual(card.stripe_payment_method_id, "pm_test_card")
        self.assertEqual(card.company_id, company)
        self.assertEqual(card.last4, "4242")
        self.assertNotIn("4242424242424242", str(card.read()))

    def test_little_rock_without_a_key_is_not_charged_with_fayetteville(self):
        fayetteville = self._company("Fayetteville")
        little_rock = self._company("Little Rock")
        order = self._order(little_rock)

        def fake_get(key, default=None):
            if key == "catering_stripe_secret_key_fayetteville":
                return "rk_test_fayetteville_only"
            return default

        with patch("odoo.addons.catering_ops.stripe_api.config") as cfg, patch.dict(
            os.environ,
            {
                "CATERING_STRIPE_SECRET_KEY_LITTLE_ROCK": "",
                "CATERING_STRIPE_SECRET_KEY_FAYETTEVILLE": "",
            },
        ), patch("odoo.addons.catering_ops.stripe_api.requests.request") as req:
            cfg.get.side_effect = fake_get
            self.assertEqual(get_stripe_secret_key(fayetteville), "rk_test_fayetteville_only")
            with self.assertRaises(UserError) as caught:
                order.action_catering_stripe_charge()
            self.assertIn("catering_stripe_secret_key_little_rock", str(caught.exception))
            self.assertNotIn("rk_test_fayetteville_only", str(caught.exception))
            req.assert_not_called()
        self.assertFalse(order.catering_paid)
        self.assertFalse(order.catering_payment_ids)
