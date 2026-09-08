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


def apply_item_fallbacks(rule):
    """Temporary fallback if seed records were not updated (noupdate)."""
    rule = dict(rule)
    code = rule.get("item_code")
    if code == "gyro_oz":
        if not rule.get("display_uom_name"):
            rule["display_uom_name"] = "lb"
        if not float(rule.get("display_divisor") or 0):
            rule["display_divisor"] = 16.0
    if code in ("pita_base", "pita_hummus", "pita_cut_hummus"):
        if not rule.get("merge_group"):
            rule["merge_group"] = "pita_cut"
    if code == "pita_hummus":
        # Wife-review: hummus adds 0.125 pita/guest (0.5 + 0.125 = 0.625), not 0.25.
        rule["qty"] = 0.125
    if code == "salad_pan":
        # Wife-review: print raw pans; do not round up.
        rule["display_round"] = "none"
    return rule


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


def split_pita(cut_total, pita_style="split", pita_grilled=0.0, pita_fried=0.0):
    """Return (grilled, fried, whole). Whole pita is 0 on Buffet for now.

    Default / split with empty fields = half grilled, half fried.
    grilled style = 100% grilled; fried style = 100% fried.
    """
    cut_total = float(cut_total or 0.0)
    style = pita_style or "split"
    if cut_total <= 0:
        return 0.0, 0.0, 0.0
    if style == "grilled":
        return cut_total, 0.0, 0.0
    if style == "fried":
        return 0.0, cut_total, 0.0
    # split or any other default: half/half unless both split fields set
    grilled = float(pita_grilled or 0.0)
    fried = float(pita_fried or 0.0)
    if grilled == 0.0 and fried == 0.0:
        half = cut_total / 2.0
        return half, half, 0.0
    return grilled, fried, 0.0


def compute_prep_lines(
    rules,
    guest_count,
    option_counts,
    hummus=False,
    pita_style="split",
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
        rule = apply_item_fallbacks(rule)
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




ITEM_PLACEMENT = {
    # food / MEAT
    "chicken_skewer": ("food", "meat"),
    "chicken_breast": ("food", "meat"),
    "gyro_oz": ("food", "meat"),
    "falafel_ball": ("food", "meat"),
    "steak_skewer": ("food", "meat"),
    "salmon_skewer": ("food", "meat"),
    "lamb_skewer": ("food", "meat"),
    # food / PITABREAD
    "pita_whole": ("food", "pitabread"),
    "pita_grilled": ("food", "pitabread"),
    "pita_fried": ("food", "pitabread"),
    # food / SIDES
    "rice_scoop": ("food", "sides"),
    "salad_pan": ("food", "sides"),
    # food / EXTRAS
    "hummus_lb": ("food", "extras"),
    "tzatziki_lb": ("food", "extras"),
    "dressing_lb": ("food", "extras"),
    # food / DESSERTS + DRINKS
    "cookie": ("food", "desserts"),
    "sweet_tea": ("food", "drinks"),
    # driver
    "ice": ("driver", "drinks"),
    "plate": ("driver", "paper_goods"),
    "napkin": ("driver", "paper_goods"),
    "plasticware": ("driver", "paper_goods"),
    "silverware": ("driver", "paper_goods"),
    "dessert_plate": ("driver", "paper_goods"),
    "cup": ("driver", "paper_goods"),
    "small_spoon": ("driver", "serving_utensils"),
    "medium_spoon": ("driver", "serving_utensils"),
    "tongs": ("driver", "serving_utensils"),
}

FOOD_CATEGORY_ORDER = ["meat", "pitabread", "sides", "extras", "desserts", "drinks"]
DRIVER_CATEGORY_ORDER = ["drinks", "paper_goods", "serving_utensils"]
CATEGORY_LABEL = {
    "meat": "MEAT",
    "pitabread": "PITABREAD",
    "sides": "SIDES",
    "extras": "EXTRAS",
    "desserts": "DESSERTS",
    "drinks": "DRINKS",
    "paper_goods": "PAPER GOODS",
    "serving_utensils": "SERVING UTENSILS",
}
DISPLAY_NAME_OVERRIDE = {
    "plasticware": "Silverware packets",
    "silverware": "Silverware packets",
}


def place_line(item_code):
    return ITEM_PLACEMENT.get(item_code or "", ("food", "extras"))


def enrich_lines(lines, needs_ice=True):
    """Attach sheet_type/category, rename labels, drop ice if not needed."""
    out = []
    for line in lines:
        code = line.get("item_code") or ""
        if code == "ice" and not needs_ice:
            continue
        sheet_type, category = place_line(code)
        name = DISPLAY_NAME_OVERRIDE.get(code, line.get("name"))
        row = dict(line)
        row["name"] = name
        row["sheet_type"] = sheet_type
        row["category"] = category
        row["is_section"] = False
        out.append(row)
    return out


def lines_for_sheet(lines, sheet_type):
    """Return section headers + lines for one sheet. Empty categories omitted."""
    order = FOOD_CATEGORY_ORDER if sheet_type == "food" else DRIVER_CATEGORY_ORDER
    selected = [l for l in lines if l.get("sheet_type") == sheet_type and float(l.get("quantity") or 0) > 0]
    by_cat = {}
    for line in selected:
        by_cat.setdefault(line["category"], []).append(line)
    result = []
    seq = 10
    for cat in order:
        rows = by_cat.get(cat) or []
        if not rows:
            continue
        result.append(
            {
                "sequence": seq,
                "name": CATEGORY_LABEL.get(cat, cat.upper()),
                "item_code": "section_%s" % cat,
                "quantity": 0.0,
                "uom_name": "",
                "sheet_type": sheet_type,
                "category": cat,
                "is_section": True,
            }
        )
        seq += 10
        for row in rows:
            r = dict(row)
            r["sequence"] = seq
            r["is_section"] = False
            result.append(r)
            seq += 10
    return result


# Mirrors data/initial_rules.xml (Buffet only). Keep in sync.
BUFFET_RULES = [
    {"name": "Chicken skewers", "item_code": "chicken_skewer", "uom_name": "skewer", "apply_mode": "per_option_guest", "qty": 2.0, "is_addon": False, "option_code": "chicken", "sequence": 10},
    {"name": "Gyro meat", "item_code": "gyro_oz", "uom_name": "oz", "apply_mode": "per_option_guest", "qty": 6.0, "is_addon": False, "option_code": "gyro", "sequence": 20, "display_uom_name": "lb", "display_divisor": 16.0},
    {"name": "Falafel", "item_code": "falafel_ball", "uom_name": "ball", "apply_mode": "per_option_guest", "qty": 5.0, "is_addon": False, "option_code": "falafel", "sequence": 30},
    {"name": "Rice", "item_code": "rice_scoop", "uom_name": "scoop", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 40},
    {"name": "Cut pita (base)", "item_code": "pita_base", "uom_name": "pita", "apply_mode": "per_guest", "qty": 0.5, "is_addon": False, "option_code": None, "sequence": 50, "merge_group": "pita_cut"},
    {"name": "Hummus", "item_code": "hummus_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": True, "option_code": None, "sequence": 60},
    {"name": "Cut pita (hummus add-on)", "item_code": "pita_hummus", "uom_name": "pita", "apply_mode": "per_guest", "qty": 0.125, "is_addon": True, "option_code": None, "sequence": 70, "merge_group": "pita_cut"},
    {"name": "Tzatziki", "item_code": "tzatziki_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 80},
    {"name": "Greek dressing", "item_code": "dressing_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 90},
    {"name": "Greek salad side", "item_code": "salad_pan", "uom_name": "pan", "apply_mode": "per_10_guests", "qty": 0.5, "is_addon": False, "option_code": None, "sequence": 100, "display_round": "none"},
    {"name": "Cups", "item_code": "cup", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 110},
    {"name": "Plates", "item_code": "plate", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 120},
    {"name": "Napkins", "item_code": "napkin", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 130},
    {"name": "Plasticware", "item_code": "plasticware", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 140},
]


# BYOP seed mirror. Keep in sync with data/byop_rules.xml. Do not change Buffet rules above.
BYOP_RULES = [
    {"name": "Chicken breast", "item_code": "chicken_breast", "uom_name": "breast", "apply_mode": "per_option_guest", "qty": 1.0, "is_addon": False, "option_code": "chicken", "sequence": 10},
    {"name": "Gyro meat", "item_code": "gyro_oz", "uom_name": "oz", "apply_mode": "per_option_guest", "qty": 5.0, "is_addon": False, "option_code": "gyro", "sequence": 20, "display_uom_name": "lb", "display_divisor": 16.0},
    {"name": "Falafel", "item_code": "falafel_ball", "uom_name": "ball", "apply_mode": "per_option_guest", "qty": 4.0, "is_addon": False, "option_code": "falafel", "sequence": 30},
    {"name": "Whole pita", "item_code": "pita_whole", "uom_name": "pita", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 40},
    {"name": "Hummus", "item_code": "hummus_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": True, "option_code": None, "sequence": 50},
    {"name": "Cut pita (hummus add-on)", "item_code": "pita_cut_hummus", "uom_name": "pita", "apply_mode": "per_guest", "qty": 0.5, "is_addon": True, "option_code": None, "sequence": 60, "merge_group": "pita_cut"},
    {"name": "Tzatziki", "item_code": "tzatziki_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 70},
    {"name": "Greek dressing", "item_code": "dressing_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 80},
    {"name": "Greek salad side", "item_code": "salad_pan", "uom_name": "pan", "apply_mode": "per_10_guests", "qty": 0.5, "is_addon": False, "option_code": None, "sequence": 90, "display_round": "none"},
    {"name": "Cups", "item_code": "cup", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 100},
    {"name": "Plates", "item_code": "plate", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 110},
    {"name": "Napkins", "item_code": "napkin", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 120},
    {"name": "Plasticware", "item_code": "plasticware", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 130},
]


# Greek Salad seed mirror. Keep in sync with data/greek_salad_rules.xml.
# Buffet and BYOP rules above stay frozen.
GREEK_SALAD_RULES = [
    {"name": "Chicken breast", "item_code": "chicken_breast", "uom_name": "breast", "apply_mode": "per_option_guest", "qty": 1.0, "is_addon": False, "option_code": "chicken", "sequence": 10},
    {"name": "Gyro meat", "item_code": "gyro_oz", "uom_name": "oz", "apply_mode": "per_option_guest", "qty": 5.0, "is_addon": False, "option_code": "gyro", "sequence": 20, "display_uom_name": "lb", "display_divisor": 16.0},
    {"name": "Falafel", "item_code": "falafel_ball", "uom_name": "ball", "apply_mode": "per_option_guest", "qty": 5.0, "is_addon": False, "option_code": "falafel", "sequence": 30},
    {"name": "Cut pita (base)", "item_code": "pita_base", "uom_name": "pita", "apply_mode": "per_guest", "qty": 0.5, "is_addon": False, "option_code": None, "sequence": 40, "merge_group": "pita_cut"},
    {"name": "Hummus", "item_code": "hummus_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": True, "option_code": None, "sequence": 50},
    {"name": "Cut pita (hummus add-on)", "item_code": "pita_hummus", "uom_name": "pita", "apply_mode": "per_guest", "qty": 0.125, "is_addon": True, "option_code": None, "sequence": 60, "merge_group": "pita_cut"},
    {"name": "Tzatziki", "item_code": "tzatziki_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 70},
    {"name": "Greek dressing", "item_code": "dressing_lb", "uom_name": "lb", "apply_mode": "per_10_guests", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 80},
    {"name": "Greek salad", "item_code": "salad_pan", "uom_name": "pan", "apply_mode": "per_10_guests", "qty": 0.5, "is_addon": False, "option_code": None, "sequence": 90, "display_round": "none"},
    {"name": "Cups", "item_code": "cup", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 100},
    {"name": "Plates", "item_code": "plate", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 110},
    {"name": "Napkins", "item_code": "napkin", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 120},
    {"name": "Plasticware", "item_code": "plasticware", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 130},
]

# Shared extras (cookies/tea/ice/utensils/dessert plates). Applied per package in XML.
SHARED_EXTRAS_RULES = [
    {"name": "Chocolate chip cookie", "item_code": "cookie", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 200},
    {"name": "Sweet tea", "item_code": "sweet_tea", "uom_name": "gallon", "apply_mode": "per_guest", "qty": 0.08, "is_addon": False, "option_code": None, "sequence": 210},
    {"name": "Ice", "item_code": "ice", "uom_name": "each", "apply_mode": "per_guest", "qty": 0.08, "is_addon": False, "option_code": None, "sequence": 220},
    {"name": "Dessert plates", "item_code": "dessert_plate", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 230},
    {"name": "Small spoon", "item_code": "small_spoon", "uom_name": "each", "apply_mode": "per_guest", "qty": 0.08, "is_addon": False, "option_code": None, "sequence": 240},
    {"name": "Medium spoon", "item_code": "medium_spoon", "uom_name": "each", "apply_mode": "per_guest", "qty": 0.08, "is_addon": False, "option_code": None, "sequence": 250},
    {"name": "Tongs", "item_code": "tongs", "uom_name": "each", "apply_mode": "per_guest", "qty": 0.20, "is_addon": False, "option_code": None, "sequence": 260},
]

BUFFET_PREMIUM_RULES = [
    {"name": "Steak skewers", "item_code": "steak_skewer", "uom_name": "skewer", "apply_mode": "per_option_guest", "qty": 2.0, "is_addon": False, "option_code": "steak", "sequence": 15},
    {"name": "Salmon skewers", "item_code": "salmon_skewer", "uom_name": "skewer", "apply_mode": "per_option_guest", "qty": 2.0, "is_addon": False, "option_code": "salmon", "sequence": 16},
    {"name": "Lamb skewers", "item_code": "lamb_skewer", "uom_name": "skewer", "apply_mode": "per_option_guest", "qty": 2.0, "is_addon": False, "option_code": "lamb", "sequence": 17},
]

