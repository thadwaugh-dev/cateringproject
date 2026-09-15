# CateringOps Builder Status — hummus qty + ice on Food Sheet

**Phase:** Hummus for (people) + Ice on Food Sheet  
**Module:** `catering_ops` **18.0.1.5.3**  
**Package food rates:** unchanged (still 1 lb / 10 hummus-people; Buffet pita +0.125 / hummus-person)

## Changes
1. **Hummus for (people)** — shown when Hummus add-on is on; defaults to guest count. Hummus lb and hummus pita add-on scale from this qty, not order guest count. Example: 25 guests, hummus for 10 → hummus 1.0 lb, cut pita total 13.75 (half/half 6.875).
2. **Ice** — when Needs ice is on, Ice appears on the **Food Sheet** under DRINKS (not Driver).

## Upgrade
Restart `odoo-server-18.0` → Apps debug → catering_ops → **Upgrade** → Compute on a test order.
