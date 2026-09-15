# CateringOps Builder Status — pita people split + sheet polish

**Module:** `catering_ops` **18.0.1.5.6**

## Changes
1. **Split grilled/fried people** — enter people counts (e.g. 15 grilled + 5 fried). System splits total cut pita by that ratio. Leave both 0 for half/half. Hummus add-on still folds into total cut pita first.
2. **Section headers** (MEAT, PITABREAD, …) — Qty column blank (no 0.0).
3. **Ice** — Food Sheet shows `YES` when Needs ice is on (no calculated amount). Off = omitted.

Example: 20 guests, hummus on, 15/5 split → cut pita 12.5 → grilled 9.375, fried 3.125.

## Upgrade
Restart odoo-server-18.0 → Apps debug → catering_ops → Upgrade → Compute.
