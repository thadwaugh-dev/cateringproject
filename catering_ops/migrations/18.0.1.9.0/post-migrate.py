"""Apply CaterZen comparison rule updates on upgrade.

Runs only when the installed version is older than 18.0.1.9.0.
The same method is also called from data/cz_comparison_update.xml so a
fresh install and every later Upgrade stay in sync. Both calls are
idempotent: they create missing BYOP topping rules, refresh those three
quantities, and deactivate cup/ice/tong/spoon rules. Other rules are left
as they are.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["catering.package.rule"].apply_cz_comparison_updates()
    _logger.info(
        "catering_ops 18.0.1.9.0 comparison rules applied (upgraded from %s)",
        version,
    )
