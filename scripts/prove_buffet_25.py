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
        engine.BUFFET_RULES, guest_count, option_counts, hummus=hummus
    )
    print("Buffet | guests=25 | chicken=15 | gyro=10 | falafel=0 | hummus=on")
    print("-" * 56)
    print(f"{'Item':<28} {'Qty':>10} {'UoM':>12}")
    for line in lines:
        print(f"{line['name']:<28} {line['quantity']:>10.2f} {line['uom_name']:>12}")
    expected = {
        "chicken_skewer": 30.0,
        "gyro_oz": 60.0,
        "rice_scoop": 25.0,
        "pita_base": 12.5,
        "hummus_lb": 2.5,
        "pita_hummus": 6.25,
        "tzatziki_lb": 2.5,
        "dressing_lb": 2.5,
        "salad_pan": 1.25,
        "cup": 25.0,
        "plate": 25.0,
        "napkin": 25.0,
        "plasticware": 25.0,
    }
    got = {line["item_code"]: line["quantity"] for line in lines}
    assert "falafel_ball" not in got
    missing = [k for k in expected if k not in got]
    extra = [k for k in got if k not in expected]
    mismatches = [
        f"{k}: expected {expected[k]}, got {got[k]}"
        for k in expected
        if k in got and abs(got[k] - expected[k]) > 1e-9
    ]
    if missing or extra or mismatches:
        raise SystemExit(
            "FAIL\nmissing=%s\nextra=%s\nmismatches=%s" % (missing, extra, mismatches)
        )
    print("-" * 56)
    print("PASS")


if __name__ == "__main__":
    main()
