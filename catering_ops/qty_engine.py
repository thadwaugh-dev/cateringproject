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
    hummus_count=None,
):
    """Hummus add-on rules scale off hummus_count (people), not order guest_count."""
    qty = float(qty or 0.0)
    guest_count = float(guest_count or 0.0)
    option_counts = option_counts or {}
    if is_addon:
        if hummus_count is not None:
            base = float(hummus_count or 0.0)
            if base <= 0:
                return 0.0
            guest_count = base
        elif hummus:
            pass  # use order guest_count
        else:
            return 0.0
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
    """Return (grilled, fried, whole) pita quantities. Whole is 0 on Buffet for now.

    pita_grilled / pita_fried are PEOPLE counts for a split override (not raw pitas).
    Example: 20 guests, 15 grilled people + 5 fried people → cut_total split 15/20 and 5/20.
    Default / split with both people fields empty = half grilled, half fried.
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
    grilled_people = float(pita_grilled or 0.0)
    fried_people = float(pita_fried or 0.0)
    if grilled_people == 0.0 and fried_people == 0.0:
        half = cut_total / 2.0
        return half, half, 0.0
    people_total = grilled_people + fried_people
    if people_total <= 0:
        half = cut_total / 2.0
        return half, half, 0.0
    return (
        cut_total * (grilled_people / people_total),
        cut_total * (fried_people / people_total),
        0.0,
    )


def compute_prep_lines(
    rules,
    guest_count,
    option_counts,
    hummus=False,
    hummus_count=None,
    pita_style="split",
    pita_grilled=0.0,
    pita_fried=0.0,
):
    """Build kitchen sheet lines. merge_group pita_cut is summed then split by style.

    hummus_count = people the hummus add-on is for. If None and hummus=True,
    falls back to guest_count (legacy prove scripts).
    """
    if hummus_count is None:
        hummus_count = float(guest_count or 0.0) if hummus else 0.0
    else:
        hummus_count = float(hummus_count or 0.0)
    hummus = hummus_count > 0
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
            hummus_count=hummus_count,
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
    # food / TOPPINGS (BYOP only)
    "byop_lettuce": ("food", "toppings"),
    "byop_tomato": ("food", "toppings"),
    "byop_onion": ("food", "toppings"),
    # food / SIDES
    "rice_scoop": ("food", "sides"),
    "salad_pan": ("food", "sides"),
    # food / EXTRAS (dips stay here; order add-ons use addons)
    "hummus_lb": ("food", "extras"),
    "tzatziki_lb": ("food", "extras"),
    "dressing_lb": ("food", "extras"),
    "order_extra": ("food", "addons"),
    # food / DESSERTS + DRINKS
    "cookie": ("food", "desserts"),
    "baklava": ("food", "desserts"),
    "mini_baklava": ("food", "desserts"),
    "dessert_triangle": ("food", "desserts"),
    "sweet_tea": ("food", "drinks"),
    "unsweet_tea": ("food", "drinks"),
    # driver
    "ice": ("driver", "drinks"),
    "sweetener": ("driver", "drinks"),
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

FOOD_CATEGORY_ORDER = [
    "meat",
    "pitabread",
    "toppings",
    "sides",
    "extras",
    "addons",
    "desserts",
    "drinks",
]
DRIVER_CATEGORY_ORDER = ["drinks", "paper_goods", "serving_utensils"]
CATEGORY_LABEL = {
    "meat": "MEAT",
    "pitabread": "PITABREAD",
    "toppings": "TOPPINGS",
    "sides": "SIDES",
    "extras": "EXTRAS",
    "addons": "EXTRAS/ADD-ONS",
    "desserts": "DESSERTS",
    "drinks": "DRINKS",
    "paper_goods": "PAPER GOODS",
    "serving_utensils": "SERVING UTENSILS",
}
# Package-rule copies of these codes are ignored. build_service_lines owns them.
SERVICE_RULE_CODES = {"cup", "ice", "small_spoon", "medium_spoon", "tongs"}
PROTEIN_TONG_CODES = (
    "chicken_skewer",
    "chicken_breast",
    "gyro_oz",
    "falafel_ball",
    "steak_skewer",
    "salmon_skewer",
    "lamb_skewer",
)
TOPPING_TONG_CODES = ("byop_lettuce", "byop_tomato", "byop_onion")
DIP_SPOON_CODES = ("hummus_lb", "tzatziki_lb", "dressing_lb")
DISPLAY_NAME_OVERRIDE = {
    "plasticware": "Silverware packets",
    "silverware": "Silverware packets",
}


def place_line(item_code):
    return ITEM_PLACEMENT.get(item_code or "", ("food", "extras"))


def enrich_lines(lines, needs_ice=True, include_opt_in=None):
    """Attach sheet_type/category and rename labels.

    Desserts / gallon teas / dessert plates are order opt-in only. Any leftover
    package-rule lines for those codes are stripped unless injected via
    include_opt_in.

    Cups, ice, tongs, and spoons from package rules are stripped here.
    build_service_lines adds the tea-based and per-dish counts. needs_ice is
    kept so older callers still pass it; it no longer prints Ice YES.
    """
    del needs_ice  # ice count is decided in build_service_lines
    opt_in_codes = {"cookie", "baklava", "mini_baklava", "dessert_triangle", "sweet_tea", "unsweet_tea", "dessert_plate"}
    out = []
    for line in lines:
        code = line.get("item_code") or ""
        if code in opt_in_codes or code in SERVICE_RULE_CODES:
            continue
        sheet_type, category = place_line(code)
        name = DISPLAY_NAME_OVERRIDE.get(code, line.get("name"))
        row = dict(line)
        row["name"] = name
        row["sheet_type"] = sheet_type
        row["category"] = category
        row["is_section"] = False
        if not row.get("qty_display"):
            q = float(row.get("quantity") or 0.0)
            row["qty_display"] = ("%s" % q).rstrip("0").rstrip(".") if q else ""
        out.append(row)
    for line in include_opt_in or []:
        code = line.get("item_code") or ""
        if not float(line.get("quantity") or 0):
            continue
        sheet_type, category = place_line(code)
        name = DISPLAY_NAME_OVERRIDE.get(code, line.get("name"))
        row = dict(line)
        row["name"] = name
        row["sheet_type"] = sheet_type
        row["category"] = category
        row["is_section"] = False
        q = float(row.get("quantity") or 0.0)
        row["qty_display"] = ("%s" % q).rstrip("0").rstrip(".") if q else ""
        out.append(row)
    return out


def _line_visible_on_sheet(line):
    if line.get("qty_display"):
        return True
    return float(line.get("quantity") or 0) > 0


def lines_for_sheet(lines, sheet_type):
    """Return section headers + lines for one sheet. Empty categories omitted.

    Section headers have blank qty_display (no 0.0).
    """
    order = FOOD_CATEGORY_ORDER if sheet_type == "food" else DRIVER_CATEGORY_ORDER
    selected = [
        l
        for l in lines
        if l.get("sheet_type") == sheet_type and _line_visible_on_sheet(l)
    ]
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
                "qty_display": "",
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
            if not r.get("qty_display") and not r.get("is_section"):
                q = float(r.get("quantity") or 0.0)
                r["qty_display"] = ("%s" % q).rstrip("0").rstrip(".") if q else ""
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
    {"name": "Shredded lettuce", "item_code": "byop_lettuce", "uom_name": "handful", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 92},
    {"name": "Sliced tomato", "item_code": "byop_tomato", "uom_name": "slice", "apply_mode": "per_guest", "qty": 2.0, "is_addon": False, "option_code": None, "sequence": 93},
    {"name": "Sliced onion", "item_code": "byop_onion", "uom_name": "ring", "apply_mode": "per_guest", "qty": 3.0, "is_addon": False, "option_code": None, "sequence": 94},
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
    {"name": "Plates", "item_code": "plate", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 110},
    {"name": "Napkins", "item_code": "napkin", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 120},
    {"name": "Plasticware", "item_code": "plasticware", "uom_name": "each", "apply_mode": "per_guest", "qty": 1.0, "is_addon": False, "option_code": None, "sequence": 130},
]

# Cups, ice, and utensils are no longer per-guest package rules.
# build_service_lines computes them. Kept as an empty list so older prove scripts still import it.
SHARED_EXTRAS_RULES = []


def build_opt_in_extras(
    cookie_qty=0.0,
    baklava_qty=0.0,
    mini_baklava_qty=0.0,
    dessert_triangle_qty=0.0,
    sweet_tea_qty=0.0,
    unsweet_tea_qty=0.0,
    guest_count=0,
):
    """Optional dessert/tea lines. Qty > 0 means on the ticket; multiple allowed.

    Dessert plates equal the dessert pieces (cookies + baklava + mini baklava
    + dessert triangles), not the guest count. guest_count is unused and kept
    so existing callers do not break.
    """
    del guest_count
    lines = []
    seq = 200
    desserts = [
        ("cookie", "Chocolate chip cookie", "each", float(cookie_qty or 0.0)),
        ("baklava", "Baklava", "each", float(baklava_qty or 0.0)),
        ("mini_baklava", "Mini baklava", "each", float(mini_baklava_qty or 0.0)),
        ("dessert_triangle", "Assorted Dessert Triangles", "each", float(dessert_triangle_qty or 0.0)),
    ]
    dessert_total = 0.0
    for code, name, uom, qty in desserts:
        if qty > 0:
            dessert_total += qty
            lines.append(
                {
                    "sequence": seq,
                    "name": name,
                    "item_code": code,
                    "quantity": qty,
                    "uom_name": uom,
                }
            )
            seq += 10
    if dessert_total > 0:
        lines.append(
            {
                "sequence": seq,
                "name": "Dessert plates",
                "item_code": "dessert_plate",
                "quantity": dessert_total,
                "uom_name": "each",
            }
        )
        seq += 10
    teas = [
        ("sweet_tea", "Sweet tea", float(sweet_tea_qty or 0.0)),
        ("unsweet_tea", "Unsweet tea", float(unsweet_tea_qty or 0.0)),
    ]
    for code, name, qty in teas:
        if qty > 0:
            lines.append(
                {
                    "sequence": seq,
                    "name": name,
                    "item_code": code,
                    "quantity": qty,
                    "uom_name": "gallon",
                }
            )
            seq += 10
    return lines


def _qty_for(lines, code):
    total = 0.0
    for line in lines:
        if line.get("is_section"):
            continue
        if (line.get("item_code") or "") == code:
            total += float(line.get("quantity") or 0.0)
    return total


def _display_qty(qty):
    qty = float(qty or 0.0)
    if not qty:
        return ""
    return ("%s" % qty).rstrip("0").rstrip(".")


def build_service_lines(lines, sweet_tea_qty=0.0, unsweet_tea_qty=0.0, needs_ice=True):
    """Driver cups, ice, sweeteners, tongs, and spoons.

    Cups = 10 per gallon of sweet + unsweet tea.
    Ice = 1 per gallon, as a count on the Driver Pull Sheet. Omitted when
    needs_ice is off (count 0) or when there is no tea.
    Sweeteners = 1 per gallon of unsweet tea only.
    No tea means no cups, ice, or sweeteners.

    Tongs (whole numbers, one per dish, not per guest):
    - 1 per protein type with quantity > 0
    - 1 if the salad pan quantity is > 0
    - 1 per BYOP topping line with quantity > 0 (lettuce, tomato, onion)
    - 1 if any cut pita (grilled or fried) is > 0
    Whole pita does not add a tong.

    Small spoons: 1 per dip with quantity > 0 (hummus, tzatziki, dressing).
    Medium spoons: 1 if rice scoops are > 0 (Buffet). Order extras never count.
    """
    sweet = float(sweet_tea_qty or 0.0)
    unsweet = float(unsweet_tea_qty or 0.0)
    gallons = sweet + unsweet
    out = []

    def add(seq, name, code, qty, uom, sheet, category):
        qty = float(qty or 0.0)
        if qty <= 0:
            return
        out.append(
            {
                "sequence": seq,
                "name": name,
                "item_code": code,
                "quantity": qty,
                "uom_name": uom,
                "sheet_type": sheet,
                "category": category,
                "is_section": False,
                "qty_display": _display_qty(qty),
            }
        )

    if gallons > 0:
        add(800, "Cups", "cup", gallons * 10.0, "each", "driver", "paper_goods")
        if needs_ice:
            add(810, "Ice", "ice", gallons, "each", "driver", "drinks")
        add(820, "Sweeteners", "sweetener", unsweet, "each", "driver", "drinks")

    tongs = 0
    for code in PROTEIN_TONG_CODES:
        if _qty_for(lines, code) > 0:
            tongs += 1
    if _qty_for(lines, "salad_pan") > 0:
        tongs += 1
    for code in TOPPING_TONG_CODES:
        if _qty_for(lines, code) > 0:
            tongs += 1
    if _qty_for(lines, "pita_grilled") + _qty_for(lines, "pita_fried") > 0:
        tongs += 1
    small = 0
    for code in DIP_SPOON_CODES:
        if _qty_for(lines, code) > 0:
            small += 1
    medium = 1 if _qty_for(lines, "rice_scoop") > 0 else 0
    add(830, "Tongs", "tongs", tongs, "each", "driver", "serving_utensils")
    add(840, "Small spoons", "small_spoon", small, "each", "driver", "serving_utensils")
    add(850, "Medium spoons", "medium_spoon", medium, "each", "driver", "serving_utensils")
    return out


def append_order_extras(lines, extras):
    """Print order add-ons on the Food Sheet. Does not change any other line."""
    out = [dict(line) for line in lines]
    seq = 9000
    for extra in extras or []:
        name = (extra.get("name") or "").strip()
        qty = float(extra.get("quantity") or 0.0)
        if not name or qty <= 0:
            continue
        note = (extra.get("note") or "").strip()
        label = name if not note else "%s — %s" % (name, note)
        out.append(
            {
                "sequence": seq,
                "name": label,
                "item_code": "order_extra",
                "quantity": qty,
                "uom_name": extra.get("uom_name") or "",
                "sheet_type": "food",
                "category": "addons",
                "is_section": False,
                "qty_display": _display_qty(qty),
            }
        )
        seq += 10
    return out


BUFFET_PREMIUM_RULES = [
    {"name": "Steak skewers", "item_code": "steak_skewer", "uom_name": "skewer", "apply_mode": "per_option_guest", "qty": 2.0, "is_addon": False, "option_code": "steak", "sequence": 15},
    {"name": "Salmon skewers", "item_code": "salmon_skewer", "uom_name": "skewer", "apply_mode": "per_option_guest", "qty": 2.0, "is_addon": False, "option_code": "salmon", "sequence": 16},
    {"name": "Lamb skewers", "item_code": "lamb_skewer", "uom_name": "skewer", "apply_mode": "per_option_guest", "qty": 2.0, "is_addon": False, "option_code": "lamb", "sequence": 17},
]

