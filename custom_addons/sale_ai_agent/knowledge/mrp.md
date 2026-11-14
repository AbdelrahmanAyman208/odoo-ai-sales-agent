# Odoo 20 Manufacturing (MRP) Playbook

## 1. Core Concepts & Document Flow
- **Bill of Materials (mrp.bom)**:
  - `normal`: Standard manufacturing process creating finished goods.
  - `phantom`: Kit BOM (sold as kit, components deducted upon delivery).
- **Manufacturing Order (mrp.production)**: Draft (`draft`) -> Confirmed (`confirmed`) -> In Progress (`progress`) -> Done (`done`).
- **Make-to-Order (MTO)**: Sales Order -> triggers MO -> missing components trigger Purchase RFQs.

## 2. Tool Execution Sequence
1. Check if BOM exists: `search_products(query)`. If missing -> `create_bill_of_materials(product_name_or_id, components)`.
2. Check component availability: `get_stock_availability(component_id)` for each component.
3. If components missing: `create_rfq(vendor, missing_items)`.
4. Create MO: `create_manufacturing_order(product_name_or_id, quantity)`.
5. *(T2 Operation)* Confirm MO & Reserve: `confirm_mrp_production(production_id)`. **Requires human approval!**

## 3. Common Errors & Troubleshooting
- **No BOM Error**: Trying to create an MO for a product without an active BOM fails. Always check or create BOM first.
- **Component Shortage**: MO confirmation sets state to `confirmed`, but moves stay in `waiting` until components arrive.

