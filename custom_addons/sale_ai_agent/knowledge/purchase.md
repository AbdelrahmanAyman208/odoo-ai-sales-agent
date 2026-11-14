# Odoo 20 Purchase Playbook

## 1. Core Concepts & Document Flow
- **Document Chain**: Request for Quotation (`draft`) -> RFQ Sent (`sent`) -> Purchase Order (`purchase`) -> Incoming Shipment / Receipt (`stock.picking`) -> Vendor Bill (`account.move`).
- **Supplierinfo**: Vendor pricing, minimum order quantities, and delivery lead times stored in `product.supplierinfo`.

## 2. Supplier Quotation & Broadcast
- **Broadcasting RFQs**: When sourcing a product, find all configured suppliers in `product.supplierinfo` and dispatch competitive RFQs.
- **Comparing Offers**: Compare supplier unit costs, delivery delays, and payment terms using `compare_vendor_offers`.

## 3. Tool Execution Sequence
1. Compare vendors: `compare_vendor_offers(product_name_or_id)`.
2. Create draft RFQ: `create_rfq(partner_name_or_id, items)`.
3. *(T2 Operation)* Confirm Purchase Order: `confirm_purchase_order(order_id)`. **Requires human approval!**

## 4. Common Errors & Troubleshooting
- **No Vendor Found**: If a product has no configured supplier, query contacts with `supplier_rank > 0`.
- **Unit of Measure (UoM) Mismatch**: Ensure purchase UoM matches inventory UoM or valid conversion factor exists.

