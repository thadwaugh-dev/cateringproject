"""Prove a 20-guest Greek Salad order. Buffet and BYOP stay frozen."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "catering_ops" / "qty_engine.py"
spec = importlib.util.spec_from_file_location("qty_engine", ENGINE)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def main():
    lines = engine.compute_prep_lines(
        engine.GREEK_SALAD_RULES,
        guest_count=20,
        option_counts={"chicken": 10, "gyro": 10, "falafel": 0},
        hummus=True,
        pita_style="split",
    )
    print("Greek Salad | guests=20 | chicken=10 | gyro=10 | falafel=0 | hummus=on | pita=split")
    print("-" * 56)
    print(f"{'Item':<28} {'Qty':>10} {'UoM':>12}")
    for line in lines:
        print(f"{line['name']:<28} {line['quantity']:>10.3f} {line['uom_name']:>12}")
    expected = {
        "chicken_breast": (10.0, "breast"),
        "gyro_oz": (3.125, "lb"),
        "pita_grilled": (6.25, "pita"),
        "pita_fried": (6.25, "pita"),
        "hummus_lb": (2.0, "lb"),
        "tzatziki_lb": (2.0, "lb"),
        "dressing_lb": (2.0, "lb"),
        "salad_pan": (1.0, "pan"),
        "cup": (20.0, "each"),
        "plate": (20.0, "each"),
        "napkin": (20.0, "each"),
        "plasticware": (20.0, "each"),
    }
    got = {line["item_code"]: (line["quantity"], line["uom_name"]) for line in lines}
    forbidden = ["falafel_ball", "rice_scoop", "chicken_skewer", "pita_whole", "pita_base", "pita_hummus"]
    bad = [k for k in forbidden if k in got]
    missing = [k for k in expected if k not in got]
    extra = [k for k in got if k not in expected]
    mismatches = []
    for k, (qty, uom) in expected.items():
        if k not in got:
            continue
        gqty, guom = got[k]
        if abs(gqty - qty) > 1e-9 or guom != uom:
            mismatches.append("%s: expected %s %s, got %s %s" % (k, qty, uom, gqty, guom))
    if missing or extra or bad or mismatches:
        raise SystemExit(
            "FAIL\nmissing=%s\nextra=%s\nforbidden=%s\nmismatches=%s"
            % (missing, extra, bad, mismatches)
        )
    # regressions
    buffet = engine.compute_prep_lines(
        engine.BUFFET_RULES, 25, {"chicken": 15, "gyro": 10, "falafel": 0}, hummus=True, pita_style="split"
    )
    bgot = {l["item_code"]: l["quantity"] for l in buffet}
    assert abs(bgot["pita_grilled"] - 7.8125) < 1e-9 and abs(bgot["salad_pan"] - 1.25) < 1e-9
    byop = engine.compute_prep_lines(
        engine.BYOP_RULES, 20, {"chicken": 12, "gyro": 8, "falafel": 0}, hummus=True, pita_style="split"
    )
    ygot = {l["item_code"]: l["quantity"] for l in byop}
    assert abs(ygot["chicken_breast"] - 12.0) < 1e-9 and abs(ygot["pita_whole"] - 20.0) < 1e-9
    assert abs(ygot["pita_grilled"] - 5.0) < 1e-9
    print("-" * 56)
    print("PASS (Greek Salad + Buffet/BYOP regression)")


if __name__ == "__main__":
    main()
