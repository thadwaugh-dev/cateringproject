"""Prove two sheets; multi dessert/tea opt-in default off."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "catering_ops" / "qty_engine.py"
spec = importlib.util.spec_from_file_location("qty_engine", ENGINE)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def qty_map(lines):
    return {
        l["item_code"]: l["quantity"]
        for l in lines
        if not l.get("is_section") and l.get("item_code")
    }


def run(**opt):
    rules = engine.BUFFET_RULES + engine.BUFFET_PREMIUM_RULES + engine.SHARED_EXTRAS_RULES
    raw = engine.compute_prep_lines(
        rules,
        25,
        {"chicken": 15, "gyro": 10, "falafel": 0, "steak": 0, "salmon": 0, "lamb": 0},
        hummus=True,
        hummus_count=25,
        pita_style="split",
    )
    opt_in = engine.build_opt_in_extras(guest_count=25, **opt)
    en = engine.enrich_lines(raw, needs_ice=True, include_opt_in=opt_in)
    en = en + engine.build_service_lines(
        en,
        sweet_tea_qty=opt.get("sweet_tea_qty") or 0.0,
        unsweet_tea_qty=opt.get("unsweet_tea_qty") or 0.0,
        needs_ice=True,
    )
    return qty_map(engine.lines_for_sheet(en, "food")), qty_map(engine.lines_for_sheet(en, "driver"))


def main():
    f, d = run()
    for code in ("cookie", "baklava", "mini_baklava", "dessert_triangle", "sweet_tea", "unsweet_tea"):
        assert code not in f, code
    assert "dessert_plate" not in d
    assert abs(f["pita_grilled"] - 7.8125) < 1e-9
    assert "ice" not in f
    assert "ice" not in d
    assert "cup" not in d

    f2, d2 = run(
        cookie_qty=25,
        baklava_qty=10,
        mini_baklava_qty=12,
        dessert_triangle_qty=5,
        sweet_tea_qty=2.0,
        unsweet_tea_qty=1.0,
    )
    assert abs(f2["cookie"] - 25) < 1e-9
    assert abs(f2["baklava"] - 10) < 1e-9
    assert abs(f2["mini_baklava"] - 12) < 1e-9
    assert abs(f2["dessert_triangle"] - 5) < 1e-9
    assert abs(f2["sweet_tea"] - 2.0) < 1e-9
    assert abs(f2["unsweet_tea"] - 1.0) < 1e-9
    assert abs(d2["dessert_plate"] - 52) < 1e-9
    assert abs(d2["cup"] - 30) < 1e-9
    assert abs(d2["ice"] - 3) < 1e-9
    assert abs(d2["sweetener"] - 1) < 1e-9

    rules = engine.BUFFET_RULES + engine.BUFFET_PREMIUM_RULES + engine.SHARED_EXTRAS_RULES
    raw = engine.compute_prep_lines(
        rules, 25, {"chicken": 15, "gyro": 10, "falafel": 0, "steak": 0, "salmon": 0, "lamb": 0},
        hummus=True, hummus_count=25, pita_style="split",
    )
    enriched = engine.enrich_lines(raw, needs_ice=False)
    enriched = enriched + engine.build_service_lines(
        enriched, sweet_tea_qty=2.0, unsweet_tea_qty=1.0, needs_ice=False
    )
    food_lines = engine.lines_for_sheet(enriched, "food")
    driver_lines = engine.lines_for_sheet(enriched, "driver")
    assert all(l.get("item_code") != "ice" for l in food_lines)
    assert all(l.get("item_code") != "ice" for l in driver_lines)
    assert all((l.get("qty_display") or "") == "" for l in food_lines if l.get("is_section"))
    print("PASS multi dessert/tea two-sheet proofs")


if __name__ == "__main__":
    main()
