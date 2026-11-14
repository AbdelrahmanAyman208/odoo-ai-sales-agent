# Odoo 20 Sales Playbook

## 1. Core Concepts & Document Flow
- **Document Chain**: Quotation (`draft`) -> Quotation Sent (`sent`) -> Sales Order (`sale`) -> Delivery Order (`stock.picking`) -> Invoice (`account.move`).
- **Partner Matching**: Look up existing customer by exact name, email, or phone before creating a new record.

## 2. Key Settings & Configurations
- **Pricelists**: Configured per partner or sale order (`pricelist_id`). Dictates item unit prices and volume discounts.
- **Taxes**: Automatically populated from `product.taxes_id` and customer fiscal position.
- **Invoicing Policy**:
  - `ordered`: Invoices are generated based on quantities ordered in the SO.
  - `delivered`: Invoices can only be created after the warehouse validates delivery (`stock.picking`).

## 3. Tool Execution Sequence
1. Check customer: `search_partner(query)`.
2. Check product catalog: `search_products(query)`.
3. Check stock availability: `get_stock_availability(product_name_or_id)`.
4. Create draft quotation: `create_quotation(partner_name_or_id, items)`.
5. *(T2 Operation)* Order confirmation: `confirm_sales_order(order_id)`. **Requires human approval!**

## 4. Common Errors & Troubleshooting
- **Missing Partner**: If customer doesn't exist, ask for confirmation or pass `allow_create_partner=True`.
- **Unavailable Stock**: Inform customer of lead time or trigger replenishment before confirming SO.

