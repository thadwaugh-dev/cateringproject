"""Prove a 25-guest Buffet order computes prep quantities. No Odoo required."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "catering_ops" / "qty_engine.py"

spec = importlib.util.spec_from_file_location("qty_engine", ENGINE)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def main():
    guest_count = 25
    option_counts = {"chicken": 15, "gyro": 10, "falafel": 0}
    hummus = True
    lines = engine.compute_prep_lines(
        engine.BUFFET_RULES,
        guest_count,
        option_counts,
        hummus=hummus,
        pita_style="grilled",
    )
    print("Buffet | guests=25 | chicken=15 | gyro=10 | falafel=0 | hummus=on | pita=grilled")
    print("-" * 56)
    print(f"{'Item':<28} {'Qty':>10} {'UoM':>12}")
    for line in lines:
        print(f"{line['name']:<28} {line['quantity']:>10.2f} {line['uom_name']:>12}")
    expected = {
        "chicken_skewer": (30.0, "skewer"),
        "gyro_oz": (3.75, "lb"),
        "rice_scoop": (25.0, "scoop"),
        "pita_grilled": (18.75, "pita"),
        "hummus_lb": (2.5, "lb"),
        "tzatziki_lb": (2.5, "lb"),
        "dressing_lb": (2.5, "lb"),
        "salad_pan": (1.5, "pan"),
        "cup": (25.0, "each"),
        "plate": (25.0, "each"),
        "napkin": (25.0, "each"),
        "plasticware": (25.0, "each"),
    }
    got = {line["item_code"]: (line["quantity"], line["uom_name"]) for line in lines}
    forbidden = ["falafel_ball", "pita_base", "pita_hummus", "pita_fried", "pita_whole"]
    extra_bad = [k for k in forbidden if k in got]
    missing = [k for k in expected if k not in got]
    extra = [k for k in got if k not in expected]
    mismatches = []
    for k, (qty, uom) in expected.items():
        if k not in got:
            continue
        gqty, guom = got[k]
        if abs(gqty - qty) > 1e-9 or guom != uom:
            mismatches.append("%s: expected %s %s, got %s %s" % (k, qty, uom, gqty, guom))
    if missing or extra or extra_bad or mismatches:
        raise SystemExit(
            "FAIL\nmissing=%s\nextra=%s\nforbidden=%s\nmismatches=%s"
            % (missing, extra, extra_bad, mismatches)
        )
    print("-" * 56)
    print("PASS")


if __name__ == "__main__":
    main()
