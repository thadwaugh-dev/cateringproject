"""Little Rock owns existing clients. Fayetteville does not see them."""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.catering_ops.company_locations import ADMIN_LOGIN, setup_locations


@tagged("catering_ops", "post_install", "-at_install")
class TestCompanyLocations(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.package = cls.env["catering.package.type"].create(
            {"name": "Location Test Package", "code": "loc_pkg"}
        )

    def _switch(self, user, company):
        return self.env(user=user).with_context(allowed_company_ids=[company.id])

    def _null_company(self, venue):
        self.env.cr.execute(
            "UPDATE catering_venue SET company_id = NULL WHERE id = %s",
            (venue.id,),
        )
        venue.invalidate_recordset(["company_id"])

    def test_locations_isolate_existing_records_and_second_run_is_a_noop(self):
        main = self.env.ref("base.main_company")
        self.assertEqual(main.name, "My Company")
        admin = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Thad",
                "login": ADMIN_LOGIN,
                "email": ADMIN_LOGIN,
                "company_id": main.id,
                "company_ids": [(6, 0, [main.id])],
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("sales_team.group_sale_salesman").id,
                        ],
                    )
                ],
            }
        )
        customer = self.env["res.partner"].create(
            {"name": "Test Rep", "customer_rank": 1, "company_id": False}
        )
        imported = self.env["res.partner"].create(
            {"name": "Imported Clinic Co", "is_company": True, "company_id": False}
        )
        self.env["ir.model.data"]._update_xmlids(
            [
                {
                    "xml_id": "__import__.cz_partner_test_rep",
                    "record": customer,
                    "noupdate": True,
                }
            ]
        )
        clinic = self.env["catering.venue"].create({"name": "Clinic A", "company_id": main.id})
        self._null_company(clinic)
        clinic.partner_ids = customer
        order = self.env["sale.order"].create(
            {
                "partner_id": customer.id,
                "company_id": main.id,
                "catering_venue_id": clinic.id,
                "catering_package_type_id": self.package.id,
            }
        )

        report = setup_locations(self.env)
        little_rock = self.env["res.company"].browse(report["little_rock_id"])
        fayetteville = self.env["res.company"].browse(report["fayetteville_id"])

        self.assertEqual(little_rock.name, "Little Rock")
        self.assertEqual(fayetteville.name, "Fayetteville")
        self.assertEqual(main, little_rock)
        self.assertTrue(report["renamed_starter_company"])
        self.assertTrue(report["fayetteville_created"])
        self.assertEqual(customer.company_id, little_rock)
        self.assertEqual(imported.company_id, little_rock)
        self.assertEqual(clinic.company_id, little_rock)
        self.assertEqual(order.company_id, little_rock)
        self.assertFalse(admin.partner_id.company_id)
        self.assertEqual(set(admin.company_ids.ids), {little_rock.id, fayetteville.id})
        self.assertEqual(admin.company_id, little_rock)
        self.assertEqual(report["admin_status"], "both")
        self.assertFalse(
            self.env["catering.venue"].search([("company_id", "=", fayetteville.id)])
        )
        self.assertFalse(
            self.env["res.partner"].search(
                [("company_id", "=", fayetteville.id), ("id", "in", (customer | imported).ids)]
            )
        )

        fay = self._switch(admin, fayetteville)
        self.assertFalse(fay["res.partner"].browse(customer.id).exists())
        self.assertFalse(fay["res.partner"].browse(imported.id).exists())
        self.assertFalse(fay["catering.venue"].browse(clinic.id).exists())
        self.assertFalse(fay["sale.order"].browse(order.id).exists())
        self.assertFalse(fay["catering.venue"].search([("partner_ids", "in", customer.id)]))

        rock = self._switch(admin, little_rock)
        self.assertEqual(rock["res.partner"].search([("id", "=", customer.id)]), customer)
        self.assertEqual(rock["catering.venue"].search([("id", "=", clinic.id)]), clinic)
        self.assertEqual(rock["sale.order"].search([("id", "=", order.id)]), order)
        self.assertIn(clinic, customer.with_env(rock).catering_preferred_venue_ids)

        fay_only = self.env["res.partner"].with_context(allowed_company_ids=[fayetteville.id]).create(
            {"name": "Fayetteville Rep", "company_id": fayetteville.id}
        )
        again = setup_locations(self.env)
        self.assertFalse(again["fayetteville_created"])
        self.assertFalse(again["renamed_starter_company"])
        self.assertEqual(again["partners_assigned"], 0)
        self.assertEqual(again["venues_assigned"], 0)
        self.assertEqual(again["orders_assigned"], 0)
        self.assertEqual(customer.company_id, little_rock)
        self.assertEqual(clinic.company_id, little_rock)
        self.assertEqual(order.company_id, little_rock)
        self.assertEqual(fay_only.company_id, fayetteville)
        self.assertEqual(self.env["res.company"].search_count([("name", "=", "Fayetteville")]), 1)
        self.assertEqual(self.env["res.company"].search_count([("name", "=", "Little Rock")]), 1)
