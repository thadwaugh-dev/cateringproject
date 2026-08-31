"""Pure quantity engine. No Odoo import. Rules live in data XML."""
import math


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


def apply_display(quantity, rule):
    qty = float(quantity or 0.0)
    divisor = float(rule.get("display_divisor") or 0.0)
    if divisor:
        qty = qty / divisor
    round_mode = rule.get("display_round") or "none"
    if round_mode == "up_0_5":
        qty = math.ceil(qty * 2.0 - 1e-12) / 2.0
    uom = rule.get("display_uom_name") or rule.get("uom_name") or ""
    return qty, uom


def split_pita(cut_total, pita_style="grilled", pita_grilled=0.0, pita_fried=0.0):
    """Return (grilled, fried, whole). Whole pita is 0 on Buffet for now."""
    cut_total = float(cut_total or 0.0)
    style = pita_style or "grilled"
    if cut_total <= 0:
        return 0.0, 0.0, 0.0
    if style == "fried":
        return 0.0, cut_total, 0.0
    if style == "split":
        grilled = float(pita_grilled or 0.0)
        fried = float(pita_fried or 0.0)
        if grilled == 0.0 and fried == 0.0:
            return cut_total, 0.0, 0.0
        return grilled, fried, 0.0
    return cut_total, 0.0, 0.0


def compute_prep_lines(
    rules,
    guest_count,
    option_counts,
    hummus=False,
    pita_style="grilled",
    pita_grilled=0.0,
    pita_fried=0.0,
):
    """Build kitchen sheet lines. merge_group pita_cut is summed then split by style."""
    pita_total = 0.0
    pita_seq = 50
    pita_uom = "pita"
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
        quantity, uom = apply_display(quantity, rule)
        merge = rule.get("merge_group") or ""
        if merge == "pita_cut":
            pita_total += quantity
            pita_seq = min(pita_seq, int(rule.get("sequence") or seq))
            pita_uom = uom or pita_uom
            continue
        if not quantity:
            continue
        lines.append(
            {
                "sequence": int(rule.get("sequence") or seq),
                "name": rule["name"],
                "item_code": rule["item_code"],
                "quantity": quantity,
                "uom_name": uom,
            }
        )
        seq += 10

    grilled, fried, whole = split_pita(
        pita_total, pita_style=pita_style, pita_grilled=pita_grilled, pita_fried=pita_fried
    )
    pita_lines = []
    if grilled:
        pita_lines.append(
            {
                "sequence": pita_seq,
                "name": "Grilled cut pita",
                "item_code": "pita_grilled",
                "quantity": grilled,
                "uom_name": pita_uom,
            }
        )
    if fried:
        pita_lines.append(
            {
                "sequence": pita_seq + 1,
                "name": "Fried cut pita",
                "item_code": "pita_fried",
                "quantity": fried,
                "uom_name": pita_uom,
            }
        )
    if whole:
        pita_lines.append(
            {
                "sequence": pita_seq + 2,
                "name": "Whole pita",
                "item_code": "pita_whole",
                "quantity": whole,
                "uom_name": pita_uom,
            }
        )
    lines.extend(pita_lines)
    lines.sort(key=lambda row: row["sequence"])
    for i, row in enumerate(lines):
        row["sequence"] = (i + 1) * 10
    return lines


# Mirrors data/initial_rules.xml (Buffet only). Keep in sync.
BUFFET_RULES = [
    {"name": "Chicken skewers", "item_code": "chicken_skewer", "uom_name": "skewer", "apply_mode": "per_option_guest", "qty": 2.0, "is_addon": False, "option_code": "chicken", "sequence": 10},
    {"name": "Gyro meat", "item_code": "gyro_oz", "uom_name": "oz", "apply_mode": "per_option_guest", "qty": 6.0, "is_addon": False, "option_code": "gyro", "sequence": 20, "display_uom_name": "lb", "display_divisor": 16.0},
    {"name": "Falafel", "item_code": "falafel_ball", "uom_name": "ball", "apply_mode": "per_option_guest", "qty": 5.0, "is_addon": False, "option_code": "falafel", "sequence": 30},
    {"name": "Rice", "item_code": "rice_scoop", "uom_name": "scoop", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 40},
    {"name": "Cut pita (base)", "item_code": "pita_base", "uom_name": "pita", "apply_mode": "per_guest", "qty": 0.5, "is_addon": False, "option_code": None, "sequence": 50, "merge_group": "pita_cut"},
    {"name": "Hummus", "item_code": "hummus_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": True, "option_code": None, "sequence": 60},
    {"name": "Cut pita (hummus add-on)", "item_code": "pita_hummus", "uom_name": "pita", "apply_mode": "per_guest", "qty": 0.25, "is_addon": True, "option_code": None, "sequence": 70, "merge_group": "pita_cut"},
    {"name": "Tzatziki", "item_code": "tzatziki_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 80},
    {"name": "Greek dressing", "item_code": "dressing_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 90},
    {"name": "Greek salad side", "item_code": "salad_pan", "uom_name": "pan", "apply_mode": "per_10_guests", "qty": 0.5, "is_addon": False, "option_code": None, "sequence": 100, "display_round": "up_0_5"},
    {"name": "Cups", "item_code": "cup", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 110},
    {"name": "Plates", "item_code": "plate", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 120},
    {"name": "Napkins", "item_code": "napkin", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 130},
    {"name": "Plasticware", "item_code": "plasticware", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 140},
]
