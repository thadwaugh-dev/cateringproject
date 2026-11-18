import os

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    from odoo.addons.catering_ops.venue_state_backfill import backfill_venue_states_from_csv

    env = api.Environment(cr, SUPERUSER_ID, {})
    mapping = os.path.join(os.path.dirname(__file__), "venue_state_backfill.csv")
    backfill_venue_states_from_csv(env, mapping)
