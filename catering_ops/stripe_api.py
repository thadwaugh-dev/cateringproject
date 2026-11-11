"""Stripe REST calls for catering charges.

The secret key is read from the Odoo config file or an environment variable.
It is never written to the database or to the log. Card numbers are not
accepted by this module. Webhooks are not required for a localhost proof;
the return route loads the Checkout Session from Stripe. A webhook can be
added later when Odoo is hosted on a public URL.
"""

import os
import re

import requests
from odoo.exceptions import UserError
from odoo.tools import config

STRIPE_API = "https://api.stripe.com"
STRIPE_VERSION = "2024-06-20"
_PAN_RE = re.compile(r"\d(?:[ -]?\d){12,18}")


def company_config_key(company):
    slug = re.sub(r"[^a-z0-9]+", "_", (company.name or "").lower()).strip("_")
    return "catering_stripe_secret_key_%s" % (slug or "company")


def get_stripe_secret_key(company):
    """Return the restricted key for this company only. Never fall back to another company."""
    name = company_config_key(company)
    raw = config.get(name)
    if raw in (None, False, True, ""):
        raw = os.environ.get(name.upper())
    if isinstance(raw, str):
        raw = raw.strip()
    if not raw or not isinstance(raw, str):
        raise UserError(
            "No Stripe key is configured for %s. Add %s under [options] in odoo.conf, "
            "or set the environment variable %s. This order was not charged."
            % (company.display_name, name, name.upper())
        )
    return raw


def public_message(message):
    """Drop anything that looks like a full card number before it is shown or stored."""
    return _PAN_RE.sub("[redacted]", message or "Stripe could not charge this order.")


class StripeError(Exception):
    def __init__(self, message, code=None, payment_intent_id=None):
        self.public_message = public_message(message)
        self.code = code or ""
        self.payment_intent_id = payment_intent_id or ""
        super().__init__(self.public_message)

    @property
    def needs_authentication(self):
        return self.code == "authentication_required"


class StripeClient:
    def __init__(self, secret_key):
        self._secret_key = secret_key

    def create_off_session_payment(self, amount, currency, customer, payment_method, description, metadata, idempotency_key):
        data = {
            "amount": str(amount),
            "currency": currency,
            "customer": customer,
            "payment_method": payment_method,
            "confirm": "true",
            "off_session": "true",
            "description": description,
            "expand[]": "payment_method",
        }
        for key, value in (metadata or {}).items():
            data["metadata[%s]" % key] = value
        return self._request("POST", "/v1/payment_intents", data, idempotency_key)

    def create_checkout_session(self, payload, idempotency_key):
        return self._request("POST", "/v1/checkout/sessions", payload, idempotency_key)

    def retrieve_checkout_session(self, session_id):
        _check_id(session_id, "cs_")
        return self._request(
            "GET",
            "/v1/checkout/sessions/%s" % session_id,
            expand=["payment_intent", "payment_intent.payment_method"],
        )

    def retrieve_payment_intent(self, intent_id):
        _check_id(intent_id, "pi_")
        return self._request(
            "GET",
            "/v1/payment_intents/%s" % intent_id,
            expand=["payment_method"],
        )

    def retrieve_payment_method(self, method_id):
        _check_id(method_id, "pm_")
        return self._request("GET", "/v1/payment_methods/%s" % method_id)

    def _request(self, method, path, data=None, idempotency_key=None, params=None, expand=None):
        headers = {
            "Authorization": "Bearer %s" % self._secret_key,
            "Stripe-Version": STRIPE_VERSION,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key[:255]
        query = []
        if isinstance(params, dict):
            query.extend(params.items())
        elif params:
            query.extend(list(params))
        for item in expand or []:
            query.append(("expand[]", item))
        try:
            response = requests.request(
                method,
                STRIPE_API + path,
                data=data,
                params=query or None,
                headers=headers,
                timeout=60,
            )
        except requests.RequestException:
            raise StripeError("Could not reach Stripe. Nothing was marked paid.") from None
        try:
            body = response.json()
        except ValueError:
            raise StripeError("Stripe returned an unreadable response. Nothing was marked paid.") from None
        if response.status_code >= 400:
            err = body.get("error") or {}
            intent = err.get("payment_intent")
            intent_id = ""
            if isinstance(intent, dict):
                intent_id = intent.get("id") or ""
            elif isinstance(intent, str):
                intent_id = intent
            code = err.get("code") or ""
            if isinstance(intent, dict) and intent.get("status") == "requires_action":
                code = code or "authentication_required"
            raise StripeError(
                err.get("message") or "Stripe declined the charge.",
                code=code,
                payment_intent_id=intent_id,
            )
        return body


def _check_id(value, prefix):
    if not value or not str(value).startswith(prefix) or not re.fullmatch(r"[A-Za-z0-9_]+", str(value)):
        raise StripeError("Stripe returned an unexpected id. Nothing was marked paid.")
