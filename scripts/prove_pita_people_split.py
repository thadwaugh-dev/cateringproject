"""Pita split by people; ice YES; section headers blank qty."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qty_engine", ROOT / "catering_ops" / "qty_engine.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

# 20 guests, hummus on → cut = 0.5*20 + 0.125*20 = 12.5
# 15 grilled people / 5 fried → 9.375 / 3.125
lines = engine.compute_prep_lines(
    engine.BUFFET_RULES,
    20,
    {"chicken": 12, "gyro": 8, "falafel": 0},
    hummus=True,
    hummus_count=20,
    pita_style="split",
    pita_grilled=15,
    pita_fried=5,
)
got = {l["item_code"]: l["quantity"] for l in lines}
assert abs(got["pita_grilled"] - 9.375) < 1e-9, got["pita_grilled"]
assert abs(got["pita_fried"] - 3.125) < 1e-9, got["pita_fried"]

# default half/half still works
lines2 = engine.compute_prep_lines(
    engine.BUFFET_RULES, 25, {"chicken": 15, "gyro": 10}, hummus=True, hummus_count=25, pita_style="split"
)
g2 = {l["item_code"]: l["quantity"] for l in lines2}
assert abs(g2["pita_grilled"] - 7.8125) < 1e-9

raw = engine.compute_prep_lines(
    engine.BUFFET_RULES + engine.SHARED_EXTRAS_RULES,
    25,
    {"chicken": 15, "gyro": 10, "falafel": 0, "steak": 0, "salmon": 0, "lamb": 0},
    hummus=True,
    hummus_count=25,
    pita_style="split",
)
en = engine.enrich_lines(raw, needs_ice=True)
food = engine.lines_for_sheet(en, "food")
ice = [l for l in food if l.get("item_code") == "ice"][0]
assert ice["qty_display"] == "YES", ice
sections = [l for l in food if l.get("is_section")]
assert sections and all(l.get("qty_display", "") == "" for l in sections), sections[0]
print("PASS pita people split + ice YES + blank section qty")
