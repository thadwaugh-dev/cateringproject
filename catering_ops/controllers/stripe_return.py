from odoo import http
from odoo.exceptions import UserError
from odoo.http import request


class CateringStripeController(http.Controller):
    """Checkout returns here. Status is confirmed with Stripe, not trusted from the query string.

    A webhook is not used. Add one later when this database is on a public URL.
    """

    @http.route("/catering/stripe/return", type="http", auth="user", methods=["GET"], csrf=False)
    def stripe_return(self, order_id=None, session_id=None, **kwargs):
        order = self._order(order_id)
        if not order or not session_id:
            return request.not_found()
        try:
            order.action_catering_confirm_checkout(session_id)
        except UserError:
            # Mismatched session: nothing was written. Show the error page.
            raise
        return request.redirect("/web#id=%s&model=sale.order&view_type=form" % order.id)

    @http.route("/catering/stripe/cancel", type="http", auth="user", methods=["GET"], csrf=False)
    def stripe_cancel(self, order_id=None, **kwargs):
        order = self._order(order_id)
        if not order:
            return request.not_found()
        order.action_catering_checkout_cancelled()
        return request.redirect("/web#id=%s&model=sale.order&view_type=form" % order.id)

    def _order(self, order_id):
        try:
            order_int = int(order_id)
        except (TypeError, ValueError):
            return request.env["sale.order"]
        # The browser may return with one company selected. The user may still
        # be allowed to see the order's company.
        allowed = request.env.user.company_ids.ids
        return (
            request.env["sale.order"]
            .with_context(allowed_company_ids=allowed)
            .browse(order_int)
            .exists()
        )
