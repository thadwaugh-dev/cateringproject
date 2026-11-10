"""Fill a blank catering.venue State from an external-id mapping.

The CaterZen import stored postal codes such as AR. Odoo 18 has several
res.country.state rows with that code, so the import left State empty.
This looks the code up again with the country, and only writes when that
pair matches exactly one state.
"""

import csv
import logging
import os

_logger = logging.getLogger(__name__)


def packaged_mapping_path():
    return os.path.join(
        os.path.dirname(__file__),
        "migrations",
        "18.0.1.6.1",
        "venue_state_backfill.csv",
    )


def load_mapping_rows(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            rows.append(
                {
                    "xmlid": (raw.get("id") or "").strip(),
                    "state_code": (raw.get("state_code") or "").strip().upper(),
                    "country_code": (raw.get("country_code") or "").strip().upper(),
                }
            )
    return rows


def _resolve_state(env, country_code, state_code):
    """Return (state, reason). state is a record only when the pair is unique."""
    if not country_code or not state_code:
        return env["res.country.state"], "missing_code"
    states = env["res.country.state"].search(
        [
            ("country_id.code", "=", country_code),
            ("code", "=", state_code),
        ]
    )
    if len(states) == 1:
        return states, ""
    if not states:
        return states, "no_match"
    return env["res.country.state"], "ambiguous"


def backfill_venue_states(env, rows):
    """Set state_id from mapping rows. Never overwrite a State that is already set.

    Venues that are not listed in rows are not read or written.
    """
    report = {
        "updated": 0,
        "skipped_already_set": 0,
        "left_blank": 0,
        "xmlid_not_found": 0,
        "still_blank_in_mapping": 0,
        "still_blank_all_venues": 0,
    }
    blank_details = []
    seen_venues = env["catering.venue"]

    for row in rows:
        xmlid = row.get("xmlid") or ""
        state_code = row.get("state_code") or ""
        country_code = row.get("country_code") or ""
        if not xmlid or "." not in xmlid:
            report["xmlid_not_found"] += 1
            blank_details.append((xmlid or "(blank id)", "xmlid_not_found", country_code, state_code))
            continue
        venue = env.ref(xmlid, raise_if_not_found=False)
        if not venue or venue._name != "catering.venue":
            report["xmlid_not_found"] += 1
            blank_details.append((xmlid, "xmlid_not_found", country_code, state_code))
            continue
        venue = venue.with_context(active_test=False)
        if not venue.exists():
            report["xmlid_not_found"] += 1
            blank_details.append((xmlid, "xmlid_not_found", country_code, state_code))
            continue
        seen_venues |= venue
        if venue.state_id:
            report["skipped_already_set"] += 1
            continue
        state, reason = _resolve_state(env, country_code, state_code)
        if not state:
            report["left_blank"] += 1
            blank_details.append((xmlid, reason, country_code, state_code))
            continue
        if venue.country_id and venue.country_id != state.country_id:
            report["left_blank"] += 1
            blank_details.append((xmlid, "country_mismatch", country_code, state_code))
            continue
        venue.state_id = state
        report["updated"] += 1

    report["still_blank_in_mapping"] = len(seen_venues.filtered(lambda venue: not venue.state_id))
    report["still_blank_all_venues"] = env["catering.venue"].with_context(active_test=False).search_count(
        [("state_id", "=", False)]
    )
    _logger.info(
        "catering.venue state backfill: updated=%s skipped_already_set=%s "
        "left_blank=%s xmlid_not_found=%s still_blank_in_mapping=%s still_blank_all_venues=%s",
        report["updated"],
        report["skipped_already_set"],
        report["left_blank"],
        report["xmlid_not_found"],
        report["still_blank_in_mapping"],
        report["still_blank_all_venues"],
    )
    for xmlid, reason, country_code, state_code in blank_details:
        _logger.info(
            "catering.venue state backfill left untouched %s reason=%s country=%s state=%s",
            xmlid,
            reason,
            country_code or "-",
            state_code or "-",
        )
    return report


def backfill_venue_states_from_csv(env, path):
    return backfill_venue_states(env, load_mapping_rows(path))
