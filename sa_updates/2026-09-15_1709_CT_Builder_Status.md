# CateringOps Builder Status — mini baklava + platter check

**Module:** `catering_ops` **18.0.1.5.4**

## Changes
1. **Mini baklava** dessert qty (with cookie / baklava / triangles).
2. **Needs ice** moved under Gallon tea section.
3. **Hummus for (people)** defaults to Guest count when Hummus is turned on; stays editable.
4. **Platter vs guests:** chicken+gyro+falafel+steak+salmon+lamb must equal Guest count. Warning while editing; **UserError** blocks Compute Prep Sheet if mismatch.

## Upgrade
Restart odoo-server-18.0 → Apps debug → catering_ops → Upgrade.
