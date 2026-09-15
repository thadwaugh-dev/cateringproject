# CateringOps Builder Status — Compute / platter error visibility

**Module:** 18.0.1.5.5 commit (this push)

## What was wrong
After 18.0.1.5.4, Compute Prep Sheet aborted in ~2 DB queries whenever platter totals did not equal Guest count (or Package/guests missing). The UserError often did not feel visible, so sheets never wrote — including after a partial fix if totals still mismatched.

## Fixes
- Visible **Platter total** + **Platter check** status on Catering tab (shows MISMATCH vs OK)
- Clear UserError modal text listing each platter count and the required Guest count
- Also errors if Package or Guest count missing
- Success toast + chatter note with line counts
- Removed silent auto-compute on every field write (button-only compute)

## Upgrade
Restart odoo-server-18.0 → Apps debug → catering_ops → Upgrade.
Then open quotation → Catering → confirm Platter check says OK → Compute Prep Sheet.
