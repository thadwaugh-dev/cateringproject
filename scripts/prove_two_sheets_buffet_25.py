"""Prove two sheets; cookies/tea opt-in default off."""
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


def run(dessert="none", cookie_qty=0, tea=False, tea_qty=0, needs_ice=True):
    rules = engine.BUFFET_RULES + engine.BUFFET_PREMIUM_RULES + engine.SHARED_EXTRAS_RULES
    raw = engine.compute_prep_lines(
        rules,
        25,
        {"chicken": 15, "gyro": 10, "falafel": 0, "steak": 0, "salmon": 0, "lamb": 0},
        hummus=True,
        pita_style="split",
    )
    opt = engine.build_opt_in_extras(
        dessert=dessert,
        cookie_qty=cookie_qty,
        sweet_tea=tea,
        sweet_tea_qty=tea_qty,
        guest_count=25,
    )
    en = engine.enrich_lines(raw, needs_ice=needs_ice, include_opt_in=opt)
    return qty_map(engine.lines_for_sheet(en, "food")), qty_map(engine.lines_for_sheet(en, "driver"))


def main():
    f, d = run()
    assert "cookie" not in f and "sweet_tea" not in f
    assert "dessert_plate" not in d
    assert abs(f["pita_grilled"] - 7.8125) < 1e-9
    assert abs(f["salad_pan"] - 1.25) < 1e-9
    assert abs(d["ice"] - 2.0) < 1e-9
    assert abs(d["tongs"] - 5) < 1e-9

    f2, d2 = run(dessert="cookie", cookie_qty=25, tea=True, tea_qty=2.0)
    assert abs(f2["cookie"] - 25) < 1e-9
    assert abs(f2["sweet_tea"] - 2.0) < 1e-9
    assert abs(d2["dessert_plate"] - 25) < 1e-9

    print("PASS opt-in dessert/tea two-sheet proofs")


if __name__ == "__main__":
    main()
