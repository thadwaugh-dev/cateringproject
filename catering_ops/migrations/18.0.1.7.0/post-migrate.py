from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    from odoo.addons.catering_ops.company_locations import setup_locations

    env = api.Environment(cr, SUPERUSER_ID, {})
    setup_locations(env)
