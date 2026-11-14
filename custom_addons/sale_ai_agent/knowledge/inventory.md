# Odoo 20 Inventory & Warehouse Playbook

## 1. Core Concepts & Architecture
- **Stock Quants**: Live inventory levels stored in `stock.quant` per location. Aggregated using `_read_group` across `location_id.usage = 'internal'`.
- **Pickings & Transfers**: Transfers (`stock.picking`) contain moves (`stock.move`) and move lines (`stock.move.line`).
- **Warehouse Routes**:
  - `Buy`: Triggers purchase order replenishment.
  - `Manufacture`: Triggers manufacturing order.
  - `Make-to-Order (MTO)`: Binds customer demand directly to procurement.

## 2. Low-Stock & Replenishment Execution
1. Scan stock thresholds: `check_inventory_replenishment(threshold)`.
2. Evaluate route per low-stock product:
   - If route is `Buy` -> `create_replenishment_order(product_name_or_id, quantity)`.
   - If route is `Manufacture` -> `create_manufacturing_order(product_name_or_id, quantity)`.
3. Check stock levels: `get_stock_availability(product_name_or_id)`.
4. *(T2 Operation)* Validate receipts/deliveries: `validate_picking(picking_id)`. **Requires human approval!**

## 3. Common Errors & Troubleshooting
- **Reserved Quantity Block**: If available stock is 0 but on-hand > 0, check existing reserved pickings.
- **Missing Stock Route**: Storable products require at least one active replenishment route (`buy` or `mrp`).

