"""Pure quantity engine. No Odoo import. Rules live in data/initial_rules.xml."""


def compute_rule_qty(
    apply_mode,
    qty,
    is_addon=False,
    option_code=None,
    guest_count=0,
    option_counts=None,
    hummus=False,
):
    if is_addon and not hummus:
        return 0.0
    qty = float(qty or 0.0)
    guest_count = float(guest_count or 0.0)
    option_counts = option_counts or {}
    if apply_mode == "per_option_guest":
        return qty * float(option_counts.get(option_code or "", 0) or 0)
    if apply_mode == "per_guest":
        return qty * guest_count
    if apply_mode == "per_10_guests":
        return qty * guest_count / 10.0
    if apply_mode == "per_20_guests":
        return qty * guest_count / 20.0
    return 0.0


def compute_prep_lines(rules, guest_count, option_counts, hummus=False):
    """rules: iterable of dicts with name, item_code, uom_name, apply_mode, qty, is_addon, option_code."""
    lines = []
    seq = 10
    for rule in rules:
        quantity = compute_rule_qty(
            apply_mode=rule["apply_mode"],
            qty=rule["qty"],
            is_addon=rule.get("is_addon", False),
            option_code=rule.get("option_code"),
            guest_count=guest_count,
            option_counts=option_counts,
            hummus=hummus,
        )
        if not quantity:
            continue
        lines.append(
            {
                "sequence": seq,
                "name": rule["name"],
                "item_code": rule["item_code"],
                "quantity": quantity,
                "uom_name": rule["uom_name"],
            }
        )
        seq += 10
    return lines


# Mirrors data/initial_rules.xml (Buffet only). Keep in sync.
BUFFET_RULES = [
    {"name": "Chicken skewers", "item_code": "chicken_skewer", "uom_name": "skewer", "apply_mode": "per_option_guest", "qty": 2.0, "is_addon": False, "option_code": "chicken"},
    {"name": "Gyro meat", "item_code": "gyro_oz", "uom_name": "oz", "apply_mode": "per_option_guest", "qty": 6.0, "is_addon": False, "option_code": "gyro"},
    {"name": "Falafel", "item_code": "falafel_ball", "uom_name": "ball", "apply_mode": "per_option_guest", "qty": 5.0, "is_addon": False, "option_code": "falafel"},
    {"name": "Rice", "item_code": "rice_scoop", "uom_name": "scoop", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None},
    {"name": "Cut pita (base)", "item_code": "pita_base", "uom_name": "pita", "apply_mode": "per_guest", "qty": 0.5, "is_addon": False, "option_code": None},
    {"name": "Hummus", "item_code": "hummus_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": True, "option_code": None},
    {"name": "Cut pita (hummus add-on)", "item_code": "pita_hummus", "uom_name": "pita", "apply_mode": "per_guest", "qty": 0.25, "is_addon": True, "option_code": None},
    {"name": "Tzatziki", "item_code": "tzatziki_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": False, "option_code": None},
    {"name": "Greek dressing", "item_code": "dressing_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": False, "option_code": None},
    {"name": "Greek salad side", "item_code": "salad_pan", "uom_name": "pan", "apply_mode": "per_10_guests", "qty": 0.5, "is_addon": False, "option_code": None},
    {"name": "Cups", "item_code": "cup", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None},
    {"name": "Plates", "item_code": "plate", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None},
    {"name": "Napkins", "item_code": "napkin", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None},
    {"name": "Plasticware", "item_code": "plasticware", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None},
]
