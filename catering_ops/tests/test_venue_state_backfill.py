"""One-time backfill of a blank venue State from the import external ids."""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.catering_ops.venue_state_backfill import (
    backfill_venue_states,
    load_mapping_rows,
    packaged_mapping_path,
)


@tagged("catering_ops", "post_install", "-at_install")
class TestVenueStateBackfill(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.us = cls.env.ref("base.us")
        cls.arkansas = cls.env.ref("base.state_us_4")
        cls.california = cls.env["res.country.state"].search(
            [("country_id", "=", cls.us.id), ("code", "=", "CA")]
        )

    def _xmlid(self, venue, name):
        xmlid = "__import__.%s" % name
        self.env["ir.model.data"]._update_xmlids(
            [{"xml_id": xmlid, "record": venue, "noupdate": True}]
        )
        return xmlid

    def test_arkansas_xmlid_is_the_numbered_us_state(self):
        self.assertEqual(self.arkansas.code, "AR")
        self.assertEqual(self.arkansas.country_id, self.us)
        self.assertEqual(self.arkansas.name, "Arkansas")
        self.assertEqual(len(self.california), 1)

    def test_empty_state_is_filled_and_second_run_is_a_noop(self):
        empty = self.env["catering.venue"].create(
            {"name": "Import Blank", "country_id": self.us.id}
        )
        preset = self.env["catering.venue"].create(
            {
                "name": "Import Preset",
                "country_id": self.us.id,
                "state_id": self.california.id,
            }
        )
        missing = self.env["catering.venue"].create(
            {"name": "Import Missing Code", "country_id": self.us.id}
        )
        ambiguous = self.env["catering.venue"].create(
            {"name": "Import Ambiguous Code", "country_id": self.us.id}
        )
        clinic = self.env["catering.venue"].create({"name": "Clinic A"})
        rows = [
            {
                "xmlid": self._xmlid(empty, "cz_venue_test_blank"),
                "state_code": "AR",
                "country_code": "US",
            },
            {
                "xmlid": self._xmlid(preset, "cz_venue_test_set"),
                "state_code": "AR",
                "country_code": "US",
            },
            {
                "xmlid": self._xmlid(missing, "cz_venue_test_missing"),
                "state_code": "",
                "country_code": "US",
            },
            {
                "xmlid": self._xmlid(ambiguous, "cz_venue_test_ambiguous"),
                "state_code": "AR",
                "country_code": "",
            },
        ]

        report = backfill_venue_states(self.env, rows)

        self.assertEqual(empty.state_id, self.arkansas)
        self.assertEqual(preset.state_id, self.california)
        self.assertFalse(missing.state_id)
        self.assertFalse(ambiguous.state_id)
        self.assertFalse(clinic.state_id)
        self.assertEqual(report["updated"], 1)
        self.assertEqual(report["skipped_already_set"], 1)
        self.assertEqual(report["left_blank"], 2)
        self.assertEqual(report["still_blank_in_mapping"], 2)

        again = backfill_venue_states(self.env, rows)

        self.assertEqual(again["updated"], 0)
        self.assertEqual(again["skipped_already_set"], 2)
        self.assertEqual(again["left_blank"], 2)
        self.assertEqual(empty.state_id, self.arkansas)
        self.assertEqual(preset.state_id, self.california)
        self.assertFalse(missing.state_id)
        self.assertFalse(ambiguous.state_id)
        self.assertFalse(clinic.state_id)

    def test_packaged_mapping_updates_only_listed_external_ids(self):
        rows = load_mapping_rows(packaged_mapping_path())
        self.assertEqual(len(rows), 166)
        self.assertTrue(all(row["state_code"] == "AR" and row["country_code"] == "US" for row in rows))
        self.assertEqual(rows[0]["xmlid"], "__import__.cz_venue_0002")

        listed = self.env["catering.venue"].create(
            {"name": "Imported venue", "country_id": self.us.id}
        )
        self._xmlid(listed, "cz_venue_0002")
        clinic = self.env["catering.venue"].create({"name": "Clinic B"})

        report = backfill_venue_states(self.env, rows)
        again = backfill_venue_states(self.env, rows)

        self.assertEqual(listed.state_id, self.arkansas)
        self.assertFalse(clinic.state_id)
        self.assertEqual(report["updated"], 1)
        self.assertEqual(report["xmlid_not_found"], 165)
        self.assertEqual(again["updated"], 0)
        self.assertEqual(again["skipped_already_set"], 1)
        self.assertEqual(listed.state_id, self.arkansas)
        self.assertFalse(clinic.state_id)
