"""CaterZen comparison checks for S00020-S00024. Pure Python, no Odoo."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qty_engine", ROOT / "catering_ops" / "qty_engine.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def qty_map(lines):
    out = {}
    for line in lines:
        if line.get("is_section") or not line.get("item_code"):
            continue
        code = line["item_code"]
        if code == "order_extra":
            out.setdefault("order_extra", []).append((line["name"], line["quantity"], line.get("uom_name") or ""))
            continue
        out[code] = line["quantity"]
    return out


def build(package, guests, options, hummus_count, style, sweet, unsweet, needs_ice, desserts=None, extras=None, stale_cup=False):
    rules = {
        "buffet": engine.BUFFET_RULES + engine.BUFFET_PREMIUM_RULES,
        "byop": engine.BYOP_RULES,
    }[package]
    raw = engine.compute_prep_lines(
        rules,
        guests,
        options,
        hummus=hummus_count > 0,
        hummus_count=hummus_count,
        pita_style=style,
    )
    if stale_cup:
        raw = list(raw) + [
            {"sequence": 1, "name": "Cups", "item_code": "cup", "quantity": float(guests), "uom_name": "each"}
        ]
    desserts = desserts or {}
    opt_in = engine.build_opt_in_extras(
        cookie_qty=desserts.get("cookie", 0),
        baklava_qty=desserts.get("baklava", 0),
        mini_baklava_qty=desserts.get("mini_baklava", 0),
        dessert_triangle_qty=desserts.get("dessert_triangle", 0),
        sweet_tea_qty=sweet,
        unsweet_tea_qty=unsweet,
        guest_count=guests,
    )
    enriched = engine.enrich_lines(raw, needs_ice=needs_ice, include_opt_in=opt_in)
    before = {
        (line.get("item_code"), float(line.get("quantity") or 0))
        for line in enriched
        if not line.get("is_section") and line.get("item_code") != "order_extra"
    }
    enriched = enriched + engine.build_service_lines(
        enriched,
        sweet_tea_qty=sweet,
        unsweet_tea_qty=unsweet,
        needs_ice=needs_ice,
    )
    enriched = engine.append_order_extras(enriched, extras or [])
    after = {
        (line.get("item_code"), float(line.get("quantity") or 0))
        for line in enriched
        if not line.get("is_section")
        and line.get("item_code") not in ("order_extra", "cup", "ice", "sweetener", "tongs", "small_spoon", "medium_spoon")
    }
    assert before == after, (before - after, after - before)
    food = qty_map(engine.lines_for_sheet(enriched, "food"))
    driver = qty_map(engine.lines_for_sheet(enriched, "driver"))
    return food, driver


def near(got, code, expected):
    actual = float(got.get(code, 0.0) or 0.0)
    assert abs(actual - expected) < 1e-9, "%s got %s expected %s" % (code, actual, expected)


def main():
    # 1. S00020 Buffet 25 chicken, hummus 25, split, tea 1/1, ice yes.
    f, d = build(
        "buffet", 25, {"chicken": 25, "gyro": 0, "steak": 0}, 25, "split", 1, 1, True
    )
    near(f, "chicken_skewer", 50)
    near(f, "rice_scoop", 25)
    near(f, "pita_grilled", 7.8125)
    near(f, "pita_fried", 7.8125)
    near(f, "hummus_lb", 2.5)
    near(f, "tzatziki_lb", 2.5)
    near(f, "dressing_lb", 2.5)
    near(f, "salad_pan", 1.25)
    assert "byop_lettuce" not in f and "byop_tomato" not in f and "byop_onion" not in f
    near(d, "plate", 25)
    near(d, "cup", 20)
    near(d, "ice", 2)
    near(d, "sweetener", 1)
    assert "dessert_plate" not in d
    near(d, "tongs", 3)
    near(d, "small_spoon", 3)
    near(d, "medium_spoon", 1)
    assert "ice" not in f

    # 2. S00021 Buffet mixed proteins, cookie 25, tea 2/1.
    f, d = build(
        "buffet",
        25,
        {"chicken": 13, "steak": 8, "gyro": 4},
        25,
        "split",
        2,
        1,
        True,
        desserts={"cookie": 25},
    )
    near(f, "chicken_skewer", 26)
    near(f, "steak_skewer", 16)
    near(f, "gyro_oz", 1.5)
    near(f, "rice_scoop", 25)
    near(f, "pita_grilled", 7.8125)
    near(f, "pita_fried", 7.8125)
    near(f, "cookie", 25)
    near(d, "dessert_plate", 25)
    near(d, "cup", 30)
    near(d, "ice", 3)
    near(d, "sweetener", 1)
    near(d, "tongs", 5)
    near(d, "small_spoon", 3)
    near(d, "medium_spoon", 1)

    # 3. S00022 BYOP fried pita. Extras must not change chicken or add rice/spoons.
    extras = [
        {"name": "Vegetable & dip platter", "quantity": 1, "uom_name": "platter", "note": "hummus dip, extra cucumbers"},
        {"name": "Extra chicken breast", "quantity": 3, "uom_name": "breast"},
        {"name": "Side salad", "quantity": 1, "uom_name": "salad", "note": "no feta or potato salad"},
        {"name": "Greek rice", "quantity": 1, "uom_name": "small pan", "note": "NO ONIONS ON ENTIRE ORDER"},
    ]
    f, d = build(
        "byop",
        20,
        {"chicken": 14, "gyro": 6},
        20,
        "fried",
        1,
        1,
        True,
        extras=extras,
        stale_cup=True,
    )
    near(f, "chicken_breast", 14)
    near(f, "gyro_oz", 1.875)
    near(f, "pita_whole", 20)
    near(f, "pita_fried", 10)
    assert "pita_grilled" not in f
    near(f, "byop_lettuce", 20)
    near(f, "byop_tomato", 40)
    near(f, "byop_onion", 60)
    near(f, "salad_pan", 1.0)
    near(f, "hummus_lb", 2.0)
    assert "rice_scoop" not in f
    assert len(f["order_extra"]) == 4
    assert any("NO ONIONS" in name for name, _qty, _uom in f["order_extra"])
    near(d, "cup", 20)
    near(d, "ice", 2)
    near(d, "sweetener", 1)
    near(d, "tongs", 7)
    near(d, "small_spoon", 3)
    assert "medium_spoon" not in d

    # 4. S00023 BYOP 50 guests, hummus 30, baklava 30, tea 2/2. Plates follow dessert, not guests.
    f, d = build(
        "byop",
        50,
        {"chicken": 30, "gyro": 20},
        30,
        "split",
        2,
        2,
        True,
        desserts={"baklava": 30},
    )
    near(f, "chicken_breast", 30)
    near(f, "gyro_oz", 6.25)
    near(f, "pita_whole", 50)
    near(f, "pita_grilled", 7.5)
    near(f, "pita_fried", 7.5)
    near(f, "hummus_lb", 3.0)
    near(f, "tzatziki_lb", 5.0)
    near(f, "dressing_lb", 5.0)
    near(f, "salad_pan", 2.5)
    near(f, "byop_lettuce", 50)
    near(f, "byop_tomato", 100)
    near(f, "byop_onion", 150)
    near(f, "baklava", 30)
    near(d, "dessert_plate", 30)
    near(d, "plate", 50)
    near(d, "cup", 40)
    near(d, "ice", 4)
    near(d, "sweetener", 2)
    near(d, "tongs", 7)
    near(d, "small_spoon", 3)
    assert "medium_spoon" not in d

    # Mixed desserts: plates are the sum, not the guest count.
    _f, d = build(
        "buffet",
        50,
        {"chicken": 50},
        0,
        "split",
        0,
        0,
        False,
        desserts={"cookie": 10, "baklava": 5, "mini_baklava": 2, "dessert_triangle": 3},
    )
    near(d, "dessert_plate", 20)
    assert "cup" not in d and "ice" not in d and "sweetener" not in d

    # 5. S00024 BYOP gyro only, no tea, needs ice off.
    f, d = build(
        "byop",
        12,
        {"gyro": 12, "chicken": 0},
        12,
        "split",
        0,
        0,
        False,
        extras=[{"name": "Spinach pie platter", "quantity": 1, "uom_name": "platter"}],
        stale_cup=True,
    )
    near(f, "gyro_oz", 3.75)
    assert "chicken_breast" not in f
    near(f, "pita_whole", 12)
    near(f, "pita_grilled", 3)
    near(f, "pita_fried", 3)
    near(f, "hummus_lb", 1.2)
    near(f, "tzatziki_lb", 1.2)
    near(f, "dressing_lb", 1.2)
    near(f, "salad_pan", 0.6)
    near(f, "byop_lettuce", 12)
    near(f, "byop_tomato", 24)
    near(f, "byop_onion", 36)
    assert f["order_extra"] == [("Spinach pie platter", 1.0, "platter")]
    near(d, "plate", 12)
    assert "cup" not in d and "ice" not in d and "sweetener" not in d
    assert "ice" not in f
    near(d, "tongs", 6)
    near(d, "small_spoon", 3)
    assert "medium_spoon" not in d and "dessert_plate" not in d

    # Ice off still prints cups and sweeteners when tea is ordered.
    _f, d = build("buffet", 10, {"chicken": 10}, 10, "split", 1, 2, False)
    near(d, "cup", 30)
    near(d, "sweetener", 2)
    assert "ice" not in d

    print("PASS S00020-S00024 comparison rules")


if __name__ == "__main__":
    main()
