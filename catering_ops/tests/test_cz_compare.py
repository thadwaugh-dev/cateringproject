"""Upgrade hook for the CaterZen comparison rules.

The quantity checks live in scripts/prove_cz_compare_five.py because they
do not need a database. This case checks the database write: missing BYOP
topping rules are created, those three quantities are set, per-guest cup
and utensil rules are deactivated, and pita / protein rules are left alone.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("catering_ops", "post_install", "-at_install")
class TestCzComparisonUpgrade(TransactionCase):
    def test_rule_update_is_idempotent_and_does_not_wipe_pita(self):
        Rule = self.env["catering.package.rule"]
        buffet = self.env["catering.package.type"].search([("code", "=", "buffet")], limit=1)
        byop = self.env["catering.package.type"].search([("code", "=", "byop")], limit=1)
        self.assertTrue(buffet and byop)
        pita = Rule.search(
            [("package_type_id", "=", buffet.id), ("item_code", "=", "pita_base")],
            limit=1,
        )
        pita_qty = pita.qty
        chicken = Rule.search(
            [("package_type_id", "=", buffet.id), ("item_code", "=", "chicken_skewer")],
            limit=1,
        )
        chicken_qty = chicken.qty

        Rule.apply_cz_comparison_updates()
        Rule.apply_cz_comparison_updates()

        self.assertEqual(pita.qty, pita_qty)
        self.assertEqual(chicken.qty, chicken_qty)
        lettuce = Rule.search(
            [("package_type_id", "=", byop.id), ("item_code", "=", "byop_lettuce")]
        )
        tomato = Rule.search(
            [("package_type_id", "=", byop.id), ("item_code", "=", "byop_tomato")]
        )
        onion = Rule.search(
            [("package_type_id", "=", byop.id), ("item_code", "=", "byop_onion")]
        )
        self.assertEqual(len(lettuce), 1)
        self.assertEqual(lettuce.qty, 1.0)
        self.assertEqual(lettuce.uom_name, "handful")
        self.assertEqual(tomato.qty, 2.0)
        self.assertEqual(tomato.uom_name, "slice")
        self.assertEqual(onion.qty, 3.0)
        self.assertEqual(onion.uom_name, "ring")
        retired = Rule.with_context(active_test=False).search(
            [("item_code", "in", ["cup", "ice", "small_spoon", "medium_spoon", "tongs"])]
        )
        self.assertTrue(retired)
        self.assertFalse(any(retired.mapped("active")))

    def test_order_extra_follows_the_order_company(self):
        partner = self.env["res.partner"].create({"name": "Extra Compare"})
        order = self.env["sale.order"].create({"partner_id": partner.id})
        extra = self.env["catering.order.extra"].create(
            {
                "order_id": order.id,
                "name": "Spinach pie platter",
                "quantity": 1,
                "uom_name": "platter",
                "note": "separate",
            }
        )
        self.assertEqual(extra.company_id, order.company_id)
        self.assertEqual(order.catering_extra_ids, extra)
