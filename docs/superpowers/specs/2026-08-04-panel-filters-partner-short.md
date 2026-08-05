# Partner note — Panel filters & linked My (short)

**Audience:** Implementers linking CRM ↔ Sales 360 boards  
**Date:** 2026-08-04

## What end users do

1. **Search bar** — which cards (customers / salespeople).
2. **Configuration gear** — My Data, chart shape, months/years, custom filter.
3. **Link dashboards** (share) — Sales buttons appear on the CRM card.

They never open Studio to map fields for the happy path.

## What builders do

| Need | Where |
|------|--------|
| CRM↔Sales My + period | Seeded / auto on share link (`scope.target`) |
| Odd button (Meetings, Deliveries) | Slot flags **Follow My** / **Follow Filters**, or a target map with an explicit date field |
| Chart model choice | Graph Model variants (model + primary button label/action together) |

## Safety rules

- Missing field on target → skip (no crash).
- No map → do not filter that surface.
- Never invent delivery dates (`scheduled_date` vs `planned_date`) — seed or Studio pick.
- Target queries always use the target model's record rules (no `sudo()` shortcut).

## Label honesty

“My Pipeline and Sales Orders” only when Sale is installed **and** dashboards are linked **and** a Sales map exists.
