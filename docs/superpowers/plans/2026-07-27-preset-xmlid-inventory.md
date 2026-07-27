# Phase A preset xmlid inventory

Generated for Task 1 (2026-07-27). Each name is the `id` on a `<record>` in `dashboard_engine/data/` that will move to the listed target module. Duplicate `<record id="…">` updates (e.g. graph fields on `blueprint_crm_customers`) count once. Salesperson ids (`*_sp_*`, `seed_crm_salesperson.xml`) are **not** in `CRM_CUSTOMER_XMLID_NAMES`.

**Sources scanned:** `seed_blueprints.xml`, `seed_blueprint_headers.xml`, `seed_conditions.xml`, `seed_crm_parity.xml`, `seed_sales_parity.xml`, `seed_crm_salesperson.xml` (not `seed_share_links.xml` — same blueprint names only; share-link slice is Task 5).

## CRM customer (`crm_customer_dashboard`)

```python
CRM_CUSTOMER_XMLID_NAMES = (
    # seed_blueprints.xml
    "blueprint_crm_customers",
    "scope_crm_mine",
    "scope_crm_pipeline",
    "scope_crm_leads",
    "scope_crm_mine_label_sale",
    "scope_crm_mine_label_website",
    "slot_crm_open_opportunities",
    "slot_crm_overdue_opportunities",
    "slot_crm_menu_opportunities",
    "slot_crm_bottom_opportunities",
    # seed_blueprint_headers.xml
    "header_crm_job",
    "header_crm_location",
    "header_crm_email",
    "header_crm_tags",
    # seed_conditions.xml (CRM-only)
    "condition_crm_overdue_opportunity",
    "rule_crm_overdue_type",
    "rule_crm_overdue_open",
    "rule_crm_overdue_deadline",
    "condition_crm_default_type",
    "rule_crm_default_type",
    "group_value_crm_use_lead",
    # seed_crm_parity.xml
    "condition_crm_unassigned",
    "rule_crm_unassigned_user",
    "slot_crm_unassigned",
    "slot_crm_menu_view_leads",
    "slot_crm_menu_new_lead",
    "slot_crm_menu_new_opportunity",
    "slot_crm_menu_report_leads",
    "slot_crm_menu_report_opportunities",
    "variant_crm_report_opportunities_enterprise",
    "slot_crm_menu_report_activities",
    "slot_crm_bottom_meetings",
    "variant_crm_primary_enterprise",
)
```

**Count:** 33

## Sales customer (`sales_customer_dashboard`)

```python
SALES_CUSTOMER_XMLID_NAMES = (
    # seed_blueprints.xml
    "blueprint_sales_customers",
    "scope_sale_orders",
    "scope_sale_quotations",
    "scope_sale_mine",
    "slot_sale_quotations",
    "slot_sale_bottom_orders",
    # seed_blueprint_headers.xml
    "header_sales_job",
    "header_sales_location",
    "header_sales_email",
    "header_sales_tags",
    # seed_sales_parity.xml
    "slot_sale_to_deliver",
    "slot_sale_to_invoice",
    "slot_sale_to_upsell",
    "slot_sale_bottom_deliveries",
    "slot_sale_box_total_due",
    "slot_sale_box_total_overdue",
    "slot_sale_bottom_invoiced",
    "slot_sale_menu_quotations",
    "slot_sale_menu_orders",
    "slot_sale_menu_transfers",
    "slot_sale_menu_invoices",
    "slot_sale_menu_new_quotation",
    "slot_sale_menu_report_sales",
    "slot_sale_menu_report_quotation",
    "slot_sale_menu_report_transfers",
    "slot_sale_menu_report_invoices",
)
```

**Count:** 26

## CRM salesperson (`crm_salesperson_dashboard`)

```python
CRM_SALESPERSON_XMLID_NAMES = (
    # seed_crm_salesperson.xml
    "blueprint_crm_salespersons",
    "scope_crm_sp_pipeline",
    "scope_crm_sp_leads",
    "slot_crm_sp_open",
    "slot_crm_sp_bottom",
    "slot_crm_sp_menu_opportunities",
)
```

**Count:** 6

## Excluded (stay in `dashboard_engine` for Phase A)

- POS / Website: `blueprint_pos_*`, `scope_pos_*`, `slot_pos_*`, `header_pos_*`, `seed_pos_parity.xml`, `seed_website_parity.xml`, warehouse seeds
- `dashboard_graph_periods_data.xml` period records
- Share-link-only updates in `seed_share_links.xml` (Task 5)
