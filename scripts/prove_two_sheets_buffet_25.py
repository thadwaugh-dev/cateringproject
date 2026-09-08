"""Prove CaterZen-style two sheets for Buffet 25-guest order."""
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


def main():
    rules = engine.BUFFET_RULES + engine.BUFFET_PREMIUM_RULES + engine.SHARED_EXTRAS_RULES
    raw = engine.compute_prep_lines(
        rules,
        25,
        {"chicken": 15, "gyro": 10, "falafel": 0, "steak": 0, "salmon": 0, "lamb": 0},
        hummus=True,
        pita_style="split",
    )
    en = engine.enrich_lines(raw, needs_ice=True)
    food = engine.lines_for_sheet(en, "food")
    driver = engine.lines_for_sheet(en, "driver")
    f = qty_map(food)
    d = qty_map(driver)
    assert abs(f["chicken_skewer"] - 30) < 1e-9
    assert abs(f["gyro_oz"] - 3.75) < 1e-9
    assert abs(f["pita_grilled"] - 7.8125) < 1e-9
    assert abs(f["pita_fried"] - 7.8125) < 1e-9
    assert abs(f["salad_pan"] - 1.25) < 1e-9
    assert abs(f["cookie"] - 25) < 1e-9
    assert abs(f["sweet_tea"] - 2.0) < 1e-9
    assert abs(d["ice"] - 2.0) < 1e-9
    assert abs(d["plate"] - 25) < 1e-9
    assert abs(d["napkin"] - 25) < 1e-9
    assert abs(d["plasticware"] - 25) < 1e-9 or abs(d.get("silverware", 0) - 25) < 1e-9
    assert abs(d["dessert_plate"] - 25) < 1e-9
    assert abs(d["cup"] - 25) < 1e-9
    assert abs(d["small_spoon"] - 2) < 1e-9
    assert abs(d["medium_spoon"] - 2) < 1e-9
    assert abs(d["tongs"] - 5) < 1e-9
    # section order food
    food_sections = [l["name"] for l in food if l.get("is_section")]
    assert food_sections == ["MEAT", "PITABREAD", "SIDES", "EXTRAS", "DESSERTS", "DRINKS"]
    driver_sections = [l["name"] for l in driver if l.get("is_section")]
    assert driver_sections == ["DRINKS", "PAPER GOODS", "SERVING UTENSILS"]

    # steak proof
    raw2 = engine.compute_prep_lines(
        rules,
        25,
        {"chicken": 13, "gyro": 0, "falafel": 0, "steak": 12, "salmon": 0, "lamb": 0},
        hummus=True,
        pita_style="split",
    )
    meat = qty_map(engine.lines_for_sheet(engine.enrich_lines(raw2, True), "food"))
    assert abs(meat["chicken_skewer"] - 26) < 1e-9
    assert abs(meat["steak_skewer"] - 24) < 1e-9

    # ice off
    en3 = engine.enrich_lines(raw, needs_ice=False)
    d3 = qty_map(engine.lines_for_sheet(en3, "driver"))
    assert "ice" not in d3

    print("PASS two-sheet Buffet proofs")


if __name__ == "__main__":
    main()
