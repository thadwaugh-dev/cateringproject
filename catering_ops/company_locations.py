"""Little Rock and Fayetteville company split.

Renames the starter company when it is still called My Company, so existing
sale orders, journals, and sequences stay on that same company record.
Shared customers and venues are then owned by Little Rock. Fayetteville is
created empty. A later run does not move records that already have a company.
"""

import logging

_logger = logging.getLogger(__name__)

LITTLE_ROCK_NAME = "Little Rock"
FAYETTEVILLE_NAME = "Fayetteville"
ADMIN_LOGIN = "thad@mylittlegreek.com"
STARTER_COMPANY_NAMES = ("My Company", "YourCompany")


def setup_locations(env):
    little_rock, renamed = _ensure_little_rock(env)
    fayetteville, fayetteville_created = _ensure_fayetteville(env, little_rock)
    partner_count = _assign_shared_partners(env, little_rock)
    venue_count = _assign_shared_venues(env, little_rock)
    order_count = _assign_other_orders(env, little_rock, fayetteville)
    admin_status = _grant_admin(env, little_rock, fayetteville)
    report = {
        "little_rock_id": little_rock.id,
        "fayetteville_id": fayetteville.id,
        "renamed_starter_company": renamed,
        "fayetteville_created": fayetteville_created,
        "partners_assigned": partner_count,
        "venues_assigned": venue_count,
        "orders_assigned": order_count,
        "admin_status": admin_status,
    }
    _logger.info(
        "catering location setup: little_rock=%s (%s) renamed_starter=%s "
        "fayetteville=%s (%s) created=%s partners_assigned=%s venues_assigned=%s "
        "orders_assigned=%s admin=%s",
        little_rock.name,
        little_rock.id,
        renamed,
        fayetteville.name,
        fayetteville.id,
        fayetteville_created,
        partner_count,
        venue_count,
        order_count,
        admin_status,
    )
    return report


def _ensure_little_rock(env):
    Company = env["res.company"].with_context(active_test=False)
    existing = Company.search([("name", "=", LITTLE_ROCK_NAME)], limit=1)
    if existing:
        return existing, False
    main = env.ref("base.main_company", raise_if_not_found=False)
    if main and main.name in STARTER_COMPANY_NAMES:
        main.name = LITTLE_ROCK_NAME
        return main, True
    starter = Company.search([("name", "in", list(STARTER_COMPANY_NAMES))], limit=1)
    if starter:
        starter.name = LITTLE_ROCK_NAME
        return starter, True
    if main and main.name != FAYETTEVILLE_NAME and Company.search_count([]) == 1:
        main.name = LITTLE_ROCK_NAME
        return main, True
    currency = (main or Company.search([], limit=1)).currency_id
    created = Company.create(
        {
            "name": LITTLE_ROCK_NAME,
            "currency_id": currency.id,
        }
    )
    return created, False


def _ensure_fayetteville(env, little_rock):
    Company = env["res.company"].with_context(active_test=False)
    existing = Company.search([("name", "=", FAYETTEVILLE_NAME)], limit=1)
    if existing:
        return existing, False
    vals = {
        "name": FAYETTEVILLE_NAME,
        "currency_id": little_rock.currency_id.id,
    }
    if little_rock.country_id:
        vals["country_id"] = little_rock.country_id.id
    return Company.create(vals), True


def _shared_partner_domain(env):
    company_partner_ids = env["res.company"].with_context(active_test=False).search([]).partner_id.ids
    user_partner_ids = env["res.users"].with_context(active_test=False).search([]).partner_id.ids
    skip_ids = list(set(company_partner_ids) | set(user_partner_ids))
    domain = [("company_id", "=", False)]
    if skip_ids:
        domain.append(("id", "not in", skip_ids))
    return domain


def _assign_shared_partners(env, little_rock):
    partners = env["res.partner"].with_context(active_test=False).search(_shared_partner_domain(env))
    if partners:
        partners.write({"company_id": little_rock.id})
    return len(partners)


def _assign_shared_venues(env, little_rock):
    venues = env["catering.venue"].with_context(active_test=False).search([("company_id", "=", False)])
    if venues:
        venues.write({"company_id": little_rock.id})
    return len(venues)


def _assign_other_orders(env, little_rock, fayetteville):
    """Move only orders that are on neither location. Do not pull Fayetteville back."""
    orders = env["sale.order"].with_context(active_test=False).search(
        [("company_id", "not in", (little_rock | fayetteville).ids)]
    )
    if orders:
        orders.write({"company_id": little_rock.id})
    return len(orders)


def _grant_admin(env, little_rock, fayetteville):
    user = env["res.users"].with_context(active_test=False).search(
        [("login", "=", ADMIN_LOGIN)], limit=1
    )
    if not user:
        _logger.info(
            "catering location setup: no user with login %s; allowed companies were not changed",
            ADMIN_LOGIN,
        )
        return "missing"
    user.write({"company_ids": [(4, little_rock.id), (4, fayetteville.id)]})
    if user.company_id not in (little_rock | fayetteville):
        user.company_id = little_rock
    multi_company = env.ref("base.group_multi_company", raise_if_not_found=False)
    if multi_company:
        user.write({"groups_id": [(4, multi_company.id)]})
    return "both"
