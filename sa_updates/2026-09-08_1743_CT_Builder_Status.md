# CateringOps Builder Status — dessert/tea opt-in

**Phase:** Cookies & sweet tea no longer default on every order  
**Module:** `catering_ops` **18.0.1.5.1**  
**Food math:** unchanged (Buffet / BYOP / Greek Salad frozen)

## What changed
- Catering tab: **Dessert** (None default / Chocolate chip cookie), cookie qty (defaults to guest count when cookie on), **Sweet tea** checkbox (default OFF), sweet tea gal (defaults to `0.08 * guests` when on). Ice toggle unchanged.
- FOOD DESSERTS / DRINKS omit when qty 0; DRIVER dessert plates only if dessert selected.
- Old always-on package rules for cookie / sweet_tea / dessert_plate deactivated on Upgrade (`extras_opt_in_deactivate.xml`).
- Shared extras seeds keep ice + utensils only.

## Proofs (engine)
- Buffet 25, dessert=none, tea=off: no cookie / sweet_tea / dessert_plate; pita/salad/ice unchanged.
- Buffet 25, cookie on qty 25 + tea on 2.00 gal: cookie 25, sweet_tea 2.00, dessert_plate 25.

## Upgrade (after Restart)
1. Restart Windows service `odoo-server-18.0`
2. http://localhost:8069/odoo/apps?debug=1 → search catering_ops → Module Info → **Upgrade**
3. Open 25-guest Buffet quotation → Catering → confirm Dessert=None, Sweet tea off → **Compute Prep Sheet** → Food Sheet has no DESSERTS/tea; Driver has no dessert plates
4. Flip dessert to cookie + sweet tea on → Compute again → cookie 25, tea 2.00 gal, dessert plates 25

## Out of scope
Package food math; hosted multi-user Odoo (SA).
