"""Customer + venue lookup.

Proof data, created inside the test transaction:

- Customer "Test Rep"
- Venues "Clinic A" and "Clinic B"
- Order 1: Test Rep + Clinic A
- Order 2: Test Rep + Clinic B

Test Rep's orders are both orders. Clinic A's orders are only order 1.
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("catering_ops", "post_install", "-at_install")
class TestCateringCustomerVenue(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.package = cls.env["catering.package.type"].create(
            {
                "name": "Test Package",
                "code": "test_pkg_venue",
            }
        )
        cls.rep = cls.env["res.partner"].create(
            {
                "name": "Test Rep",
                "customer_rank": 1,
            }
        )
        cls.other = cls.env["res.partner"].create(
            {
                "name": "Other Rep",
                "customer_rank": 1,
            }
        )
        cls.clinic_a = cls.env["catering.venue"].create(
            {
                "name": "Clinic A",
                "contact_name": "Front desk",
                "street": "1 Clinic Way",
                "city": "Little Rock",
                "zip": "72201",
                "phone": "501-555-0101",
                "notes": "Side entrance",
            }
        )
        cls.clinic_b = cls.env["catering.venue"].create(
            {
                "name": "Clinic B",
                "contact_name": "Nurse station",
                "street": "2 Clinic Way",
                "city": "Fayetteville",
                "zip": "72701",
                "phone": "479-555-0102",
                "notes": "Call on arrival",
            }
        )

    def _order(self, partner, venue=None, package=None):
        vals = {"partner_id": partner.id}
        if venue:
            vals["catering_venue_id"] = venue.id
        if package:
            vals["catering_package_type_id"] = package.id
        return self.env["sale.order"].create(vals)

    def test_rep_sees_both_orders_and_clinic_a_sees_only_order_1(self):
        order1 = self._order(self.rep, self.clinic_a, self.package)
        order2 = self._order(self.rep, self.clinic_b, self.package)

        self.assertEqual(self.rep.sale_order_ids, order1 | order2)
        self.assertEqual(self.clinic_a.order_ids, order1)
        self.assertEqual(self.clinic_b.order_ids, order2)
        self.assertEqual(order1.partner_id, self.rep)
        self.assertEqual(order1.catering_venue_id, self.clinic_a)
        self.assertEqual(order2.catering_venue_id, self.clinic_b)

        by_customer = self.env["sale.order"].search([("partner_id", "=", self.rep.id)])
        by_clinic_a = self.env["sale.order"].search(
            [("catering_venue_id", "=", self.clinic_a.id)]
        )
        self.assertEqual(by_customer, order1 | order2)
        self.assertEqual(by_clinic_a, order1)

    def test_venue_is_shared_and_preferred_does_not_limit_the_global_list(self):
        self.rep.catering_preferred_venue_ids = self.clinic_a
        self.assertEqual(self.clinic_a.partner_ids, self.rep)
        self.assertFalse(self.clinic_b.partner_ids)

        order_rep_at_b = self._order(self.rep, self.clinic_b, self.package)
        order_other_at_a = self._order(self.other, self.clinic_a, self.package)

        self.assertEqual(order_rep_at_b.catering_venue_id, self.clinic_b)
        self.assertEqual(order_rep_at_b.partner_id, self.rep)
        self.assertEqual(self.clinic_a.order_ids, order_other_at_a)
        self.assertEqual(self.other.sale_order_ids, order_other_at_a)
        self.assertNotIn(order_rep_at_b, self.clinic_a.order_ids)

    def test_package_order_requires_venue_plain_order_does_not(self):
        plain = self._order(self.rep)
        self.assertFalse(plain.catering_package_type_id)
        self.assertFalse(plain.catering_venue_id)

        with self.assertRaises(ValidationError):
            self._order(self.rep, venue=None, package=self.package)

        plain.write(
            {
                "catering_package_type_id": self.package.id,
                "catering_venue_id": self.clinic_a.id,
            }
        )
        self.assertEqual(plain.catering_venue_id, self.clinic_a)

        with self.assertRaises(ValidationError):
            plain.write({"catering_venue_id": False})

        plain.write(
            {
                "catering_package_type_id": False,
                "catering_venue_id": False,
            }
        )
        self.assertFalse(plain.catering_venue_id)

    def test_venue_search_matches_contact_city_and_phone(self):
        by_phone = self.env["catering.venue"].name_search("501-555-0101")
        by_city = self.env["catering.venue"].name_search("Fayetteville")
        self.assertIn(self.clinic_a.id, [row[0] for row in by_phone])
        self.assertIn(self.clinic_b.id, [row[0] for row in by_city])
        self.assertEqual(self.clinic_a.display_name, "Clinic A (Little Rock)")

        found = self.env["catering.venue"].search(
            [
                "|",
                "|",
                ("contact_name", "ilike", "Front desk"),
                ("city", "=", "Little Rock"),
                ("phone", "ilike", "555-0101"),
            ]
        )
        self.assertIn(self.clinic_a, found)
        self.assertNotIn(self.clinic_b, found)

    def test_menus_and_order_search_views_expose_customer_and_venue(self):
        self.assertEqual(
            self.env.ref("catering_ops.action_catering_customers").res_model,
            "res.partner",
        )
        self.assertEqual(
            self.env.ref("catering_ops.action_catering_venue").res_model,
            "catering.venue",
        )
        orders = self.env.ref("catering_ops.action_catering_orders")
        self.assertEqual(orders.res_model, "sale.order")
        self.assertIn("list", orders.view_mode)
        self.assertNotIn("calendar", orders.view_mode)

        for xml_id in (
            "catering_ops.menu_catering_customers",
            "catering_ops.menu_catering_venues",
            "catering_ops.menu_catering_orders",
        ):
            menu = self.env.ref(xml_id)
            self.assertEqual(menu.parent_id, self.env.ref("catering_ops.menu_catering_ops_root"))

        def arch(model, view_xmlid=None, view_type="form"):
            view_id = self.env.ref(view_xmlid).id if view_xmlid else None
            raw = self.env[model].get_view(view_id=view_id, view_type=view_type)["arch"]
            return raw if isinstance(raw, str) else str(raw)

        order_search = arch("sale.order", "sale.view_sales_order_filter", "search")
        quote_search = arch(
            "sale.order", "sale.sale_order_view_search_inherit_quotation", "search"
        )
        order_list = arch("sale.order", "sale.view_quotation_tree", "list")
        order_form = arch("sale.order", "sale.view_order_form", "form")
        for view_arch in (order_search, quote_search, order_list, order_form):
            self.assertIn("partner_id", view_arch)
            self.assertIn("catering_venue_id", view_arch)
        self.assertIn("group_catering_venue", order_search)
        self.assertIn('required="catering_package_type_id"', order_form)

        venue_search = arch("catering.venue", "catering_ops.view_catering_venue_search", "search")
        for token in (
            "contact_name",
            "street",
            "city",
            "state_id",
            "zip",
            "phone",
            "notes",
        ):
            self.assertIn(token, venue_search)

        partner_form = arch("res.partner", "base.view_partner_form", "form")
        self.assertIn("catering_preferred_venue_ids", partner_form)
        self.assertIn("sale_order_ids", partner_form)
        self.assertIn("catering_venue_id", partner_form)
        partner_search = arch("res.partner", "base.view_res_partner_filter", "search")
        for token in ("name", "city", "street", "zip", "catering_preferred_venue_ids"):
            self.assertIn(token, partner_search)
        self.assertIn('name="catering_customer"', partner_search)
        inherit_arch = self.env.ref("catering_ops.view_res_partner_filter_catering_ops").arch
        self.assertIn('name="name"', inherit_arch)
        self.assertNotIn('name="phone"', inherit_arch)

        access = self.env.ref("catering_ops.access_catering_venue_user")
        self.assertTrue(access.perm_read and access.perm_write and access.perm_create)
        self.assertFalse(access.perm_unlink)
