# CateringOps Builder Status — multi dessert + tea

**Phase:** Baklava, Assorted Dessert Triangles, Unsweet tea; multi on one ticket  
**Module:** `catering_ops` **18.0.1.5.2**  
**Food math:** unchanged

## UX
Qty fields (0 = off). Multiple desserts and both teas can sit on one order:
- Chocolate chip cookie / Baklava / Assorted Dessert Triangles
- Sweet tea (gal) / Unsweet tea (gal)
Exclusive dropdowns cannot put two desserts on one ticket, so each option has its own qty.

Dessert plates = guest_count when any dessert qty > 0.

## Proofs
- All qtys 0: no dessert/tea/dessert_plate lines
- Cookie 25 + baklava 10 + triangles 5 + sweet 2 + unsweet 1: all food lines + dessert_plate 25
- Buffet/BYOP/Greek Salad food math still PASS

## Upgrade
1. Restart `odoo-server-18.0`
2. Apps debug → catering_ops → Upgrade
3. Catering tab: set dessert/tea qtys → Compute
