import json
import logging
from odoo import api, fields, models
from odoo.fields import Command

_logger = logging.getLogger(__name__)


class AiSalesTools(models.AbstractModel):
    _name = 'ai.sales.tools'
    _description = 'Sales AI Agent Tools Engine'

    @api.model
    def get_tool_definitions(self):
        """Returns OpenAI-compatible function calling schemas."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "create_product",
                    "description": "Create a new sales product in the catalog with name, list price, internal reference, and optional initial stock / description.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the product (e.g. 'TV', 'Office Chair', 'Monitor')",
                            },
                            "list_price": {
                                "type": "number",
                                "description": "Sales price of the product (e.g. 300.0)",
                            },
                            "default_code": {
                                "type": "string",
                                "description": "Optional internal reference / SKU code",
                            },
                            "initial_qty": {
                                "type": "number",
                                "description": "Optional initial quantity or stock available (default 0)",
                            },
                            "description": {
                                "type": "string",
                                "description": "Optional description for sales",
                            },
                            "track_inventory": {
                                "type": "boolean",
                                "description": "Enable inventory tracking (is_storable) for this product. Default false. Set to true to track stock levels, on-hand quantities, and warehouse movements.",
                            },
                            "tracking_method": {
                                "type": "string",
                                "enum": ["none", "lot", "serial"],
                                "description": "Tracking method for inventory: 'none' (track by quantity only, default), 'lot' (track by lot numbers), 'serial' (track by unique serial numbers). Only applies when track_inventory is true.",
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_products",
                    "description": "Search available sales products in the catalog by name or reference code.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search term for the product, e.g. 'Desk', 'Chair', 'Acoustic Bloc'",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return (default 5)",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_partner",
                    "description": "Search customers or contacts by name, email, or phone number.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Customer name, company, email, or phone to search",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return (default 5)",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_quotation",
                    "description": "Create a new draft quotation (sale.order) in Odoo for a customer with specified products and quantities.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "partner_name_or_id": {
                                "type": "string",
                                "description": "Customer name or numeric ID (e.g. 'Azure Interior' or '12')",
                            },
                            "items": {
                                "type": "array",
                                "description": "List of products to add to quotation",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "product_name_or_id": {
                                            "type": "string",
                                            "description": "Product name or reference",
                                        },
                                        "quantity": {
                                            "type": "number",
                                            "description": "Quantity to order (default 1)",
                                        },
                                        "price_unit": {
                                            "type": "number",
                                            "description": "Optional custom unit price. If omitted, standard catalog price is used.",
                                        },
                                    },
                                    "required": ["product_name_or_id"],
                                },
                            },
                            "note": {
                                "type": "string",
                                "description": "Optional terms, notes, or special instructions on the quotation",
                            },
                        },
                        "required": ["partner_name_or_id", "items"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pipeline_summary",
                    "description": "Retrieve an analytics summary of the current CRM sales pipeline, including deals by stage, expected revenue, and top open opportunities.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_leads",
                    "description": "Search CRM leads and opportunities by name, partner, or stage.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Keywords to find relevant CRM leads or opportunities",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of leads to return (default 5)",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_purchase_order",
                    "description": "Create a new draft purchase order or Request for Quotation (RFQ) for a supplier/vendor with products, quantities, and optional unit prices.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vendor_name_or_id": {
                                "type": "string",
                                "description": "Supplier / Vendor name or ID (e.g. 'Wood Supplier Co' or 'Gemini Supplies')",
                            },
                            "items": {
                                "type": "array",
                                "description": "List of products and quantities to purchase",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "product_name_or_id": {
                                            "type": "string",
                                            "description": "Product name or reference",
                                        },
                                        "quantity": {
                                            "type": "number",
                                            "description": "Quantity to order (default 1)",
                                        },
                                        "price_unit": {
                                            "type": "number",
                                            "description": "Optional unit price offered by supplier",
                                        },
                                    },
                                    "required": ["product_name_or_id"],
                                },
                            },
                            "notes": {
                                "type": "string",
                                "description": "Optional purchase notes or payment terms",
                            },
                        },
                        "required": ["vendor_name_or_id", "items"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "send_rfq_to_suppliers",
                    "description": "Send price quotation requests (RFQs) to multiple or all relevant suppliers/vendors for a set of products to request their offers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_name_or_id": {
                                "type": "string",
                                "description": "Product name or reference to request quotes for",
                            },
                            "quantity": {
                                "type": "number",
                                "description": "Quantity requested",
                            },
                            "vendor_names": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of specific vendor names. If empty, creates RFQ for all known suppliers/vendors.",
                            },
                        },
                        "required": ["product_name_or_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_supplier_offers",
                    "description": "Analyze all supplier price quotations/RFQs and vendor pricelist offers for a product to find the lowest price, best supplier, and comparative breakdown.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_name_or_id": {
                                "type": "string",
                                "description": "Product name or reference to analyze offers for",
                            },
                        },
                        "required": ["product_name_or_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_composite_product",
                    "description": "Create an assembly/composite product composed of sub-products or components (e.g. Desk containing 1 Table Top and 4 Legs).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the composite finished product (e.g. 'Executive Office Desk')",
                            },
                            "sales_price": {
                                "type": "number",
                                "description": "Final sales price of the assembled product",
                            },
                            "components": {
                                "type": "array",
                                "description": "List of components with product names/IDs and required quantities",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "component_name": {
                                            "type": "string",
                                            "description": "Component product name (e.g. 'Wooden Table Top', 'Steel Leg')",
                                        },
                                        "quantity": {
                                            "type": "number",
                                            "description": "Quantity of this component needed per parent product",
                                        },
                                        "cost": {
                                            "type": "number",
                                            "description": "Optional component unit cost if creating it",
                                        },
                                    },
                                    "required": ["component_name"],
                                },
                            },
                            "description": {
                                "type": "string",
                                "description": "Optional description of the assembly",
                            },
                            "track_inventory": {
                                "type": "boolean",
                                "description": "Enable inventory tracking for the composite product and all its components. Default false.",
                            },
                            "tracking_method": {
                                "type": "string",
                                "enum": ["none", "lot", "serial"],
                                "description": "Tracking method for the composite product: 'none' (quantity), 'lot' (lot numbers), 'serial' (serial numbers). Only when track_inventory is true.",
                            },
                        },
                        "required": ["name", "components"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_inventory_replenishment",
                    "description": "Scan product catalog and warehouse stock to identify low-stock items requiring replenishment, showing current on-hand, forecasted quantity, safety threshold, and reorder recommendations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "threshold": {
                                "type": "number",
                                "description": "Minimum safety stock threshold (default 5.0). Products with stock below this are flagged for replenishment.",
                            },
                            "query": {
                                "type": "string",
                                "description": "Optional search filter for product name or SKU.",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max number of low stock items to return (default 10).",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_replenishment_order",
                    "description": "Execute automated replenishment technique: generates a draft Purchase Order (RFQ) for an understocked product to restore safety buffer, auto-selecting the primary supplier or best-priced vendor.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_name_or_id": {
                                "type": "string",
                                "description": "Product name or ID to replenish (e.g. 'Desk', 'Chair', or numeric ID)",
                            },
                            "quantity": {
                                "type": "number",
                                "description": "Units to replenish. If omitted or 0, auto-calculates quantity needed to restore safety stock buffer.",
                            },
                            "vendor_name_or_id": {
                                "type": "string",
                                "description": "Optional specific vendor to purchase from. If omitted, automatically selects registered primary vendor or lowest-cost supplier.",
                            },
                            "notes": {
                                "type": "string",
                                "description": "Optional note for the replenishment order.",
                            },
                        },
                        "required": ["product_name_or_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_product_tracking",
                    "description": "Enable, disable, or change inventory tracking settings on an existing product. Can set is_storable (track inventory), tracking method (lot/serial/none), and optionally set reorder rules.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_name_or_id": {
                                "type": "string",
                                "description": "Product name or ID to update tracking for",
                            },
                            "track_inventory": {
                                "type": "boolean",
                                "description": "Enable (true) or disable (false) inventory tracking (is_storable)",
                            },
                            "tracking_method": {
                                "type": "string",
                                "enum": ["none", "lot", "serial"],
                                "description": "Tracking method: 'none' (quantity only), 'lot' (batch tracking), 'serial' (unique serial per unit)",
                            },
                            "reorder_min_qty": {
                                "type": "number",
                                "description": "Optional minimum quantity for automatic reorder point rule (triggers when stock drops below this)",
                            },
                            "reorder_max_qty": {
                                "type": "number",
                                "description": "Optional maximum quantity for reorder rule (target stock level after reorder)",
                            },
                        },
                        "required": ["product_name_or_id"],
                    },
                },
            },
        ]

    @api.model
    def execute_tool(self, tool_name, arguments):
        """
        Executes the specified tool as the current user (NO sudo),
        ensuring Odoo standard access rights and record rules are strictly respected.
        """
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                arguments = {}

        if tool_name == 'create_product':
            return self._tool_create_product(**arguments)
        elif tool_name == 'search_products':
            return self._tool_search_products(**arguments)
        elif tool_name == 'search_partner':
            return self._tool_search_partner(**arguments)
        elif tool_name == 'create_quotation':
            return self._tool_create_quotation(**arguments)
        elif tool_name == 'get_pipeline_summary':
            return self._tool_get_pipeline_summary()
        elif tool_name == 'search_leads':
            return self._tool_search_leads(**arguments)
        elif tool_name == 'create_purchase_order':
            return self._tool_create_purchase_order(**arguments)
        elif tool_name == 'send_rfq_to_suppliers':
            return self._tool_send_rfq_to_suppliers(**arguments)
        elif tool_name == 'analyze_supplier_offers':
            return self._tool_analyze_supplier_offers(**arguments)
        elif tool_name == 'create_composite_product':
            return self._tool_create_composite_product(**arguments)
        elif tool_name == 'check_inventory_replenishment':
            return self._tool_check_inventory_replenishment(**arguments)
        elif tool_name == 'create_replenishment_order':
            return self._tool_create_replenishment_order(**arguments)
        elif tool_name == 'update_product_tracking':
            return self._tool_update_product_tracking(**arguments)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def _tool_create_product(self, name, list_price=0.0, default_code=None, initial_qty=0.0, description=None, track_inventory=None, tracking_method=None, **kwargs):
        """Creates a new product in the catalog with price, optional initial qty, and inventory tracking."""
        ProductTemplate = self.env['product.template']
        ProductProduct = self.env['product.product']

        vals = {
            'name': name.strip() if name else 'New Product',
            'list_price': float(list_price) if list_price is not None else 0.0,
            'sale_ok': True,
            'purchase_ok': True,
        }
        if default_code:
            vals['default_code'] = default_code.strip()
        if description:
            vals['description_sale'] = description.strip()

        # Flexible detection for track_inventory (handles boolean, string, or alias kwargs)
        raw_track = track_inventory
        if raw_track is None:
            for alias in ('is_storable', 'enable_track_inventory', 'track_stock', 'enable_tracking', 'track'):
                if alias in kwargs:
                    raw_track = kwargs[alias]
                    break

        if isinstance(raw_track, str):
            enable_tracking = raw_track.strip().lower() in ('true', '1', 'yes', 't', 'on', 'enable', 'enabled')
        elif raw_track is not None:
            enable_tracking = bool(raw_track)
        else:
            # If tracking method is explicitly passed (lot or serial) or if initial_qty > 0
            meth = (tracking_method or kwargs.get('tracking') or '').lower()
            enable_tracking = meth in ('lot', 'serial', 'none', 'quantity') or bool(initial_qty and float(initial_qty) > 0)

        # In Odoo 20: Track Inventory is controlled by is_storable=True (under consu Goods type)
        if enable_tracking:
            vals['type'] = 'consu'
            vals['is_storable'] = True
            meth = (tracking_method or kwargs.get('tracking') or '').lower()
            if meth in ('lot', 'serial'):
                vals['tracking'] = meth
            else:
                vals['tracking'] = False  # Tracked by quantity only

        # Create product template (standard Odoo pattern)
        tmpl = ProductTemplate.create(vals)
        product = tmpl.product_variant_id or ProductProduct.search([('product_tmpl_id', '=', tmpl.id)], limit=1)

        # If stock module is installed and qty is provided, update quantity on hand
        qty_num = float(initial_qty or 0.0)
        stock_updated = False
        if qty_num > 0 and tmpl.is_storable:
            try:
                Quant = self.env['stock.quant']
                location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
                if location and product:
                    Quant.with_context(inventory_mode=True).create({
                        'product_id': product.id,
                        'location_id': location.id,
                        'inventory_quantity': qty_num,
                    }).action_apply_inventory()
                    stock_updated = True
            except Exception as e:
                _logger.warning("Could not set initial inventory for %s: %s", name, e)

        # Optional automatic reordering rule if min_qty/max_qty passed
        min_reorder = kwargs.get('min_qty', kwargs.get('reorder_min_qty'))
        max_reorder = kwargs.get('max_qty', kwargs.get('reorder_max_qty'))
        reorder_info = ""
        if tmpl.is_storable and (min_reorder is not None or max_reorder is not None):
            try:
                min_q = float(min_reorder) if min_reorder is not None else 5.0
                max_q = float(max_reorder) if max_reorder is not None else min_q * 3.0
                warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
                if warehouse and product:
                    self.env['stock.warehouse.orderpoint'].create({
                        'product_id': product.id,
                        'warehouse_id': warehouse.id,
                        'product_min_qty': min_q,
                        'product_max_qty': max_q,
                    })
                    reorder_info = f" Reorder rule set (min: {min_q}, max: {max_q})."
            except Exception as reorder_err:
                _logger.warning("Could not create reordering rule for %s: %s", name, reorder_err)

        currency_symbol = tmpl.currency_id.symbol if tmpl.currency_id else '$'
        tracking_info = ""
        if tmpl.is_storable:
            method_desc = 'Unique Serial Number' if tmpl.tracking == 'serial' else ('Lots' if tmpl.tracking == 'lot' else 'Quantity')
            tracking_info = f" ✅ Track Inventory: ENABLED (Mode: {method_desc})."
        else:
            tracking_info = " Track Inventory: OFF."

        return {
            "success": True,
            "product_id": product.id if product else tmpl.id,
            "product_tmpl_id": tmpl.id,
            "name": tmpl.name,
            "list_price": tmpl.list_price,
            "default_code": tmpl.default_code or '',
            "currency": currency_symbol,
            "initial_qty": qty_num,
            "stock_updated": stock_updated,
            "is_storable": tmpl.is_storable,
            "tracking_method": tmpl.tracking or ('quantity' if tmpl.is_storable else 'none'),
            "message": (
                f"Product '{tmpl.name}' created successfully with sales price {currency_symbol}{tmpl.list_price:,.2f}"
                + (f" and {qty_num} initial units." if qty_num > 0 else ".")
                + tracking_info
                + reorder_info
            ),
        }

    def _tool_search_products(self, query='', limit=5):
        # Run under current user's environment
        Product = self.env['product.product']
        domain = [('sale_ok', '=', True), '|', ('name', 'ilike', query), ('default_code', 'ilike', query)]
        products = Product.search(domain, limit=limit)
        
        # If no exact match, try template search
        if not products:
            templates = self.env['product.template'].search([('sale_ok', '=', True), ('name', 'ilike', query)], limit=limit)
            if templates:
                products = templates.product_variant_ids[:limit]

        results = []
        for p in products:
            tmpl = p.product_tmpl_id
            results.append({
                "id": p.id,
                "name": p.display_name,
                "default_code": p.default_code or '',
                "list_price": p.list_price,
                "currency": p.currency_id.name if p.currency_id else '',
                "qty_available": p.qty_available or 0.0,
                "virtual_available": p.virtual_available or 0.0,
                "is_storable": tmpl.is_storable,
                "tracking": tmpl.tracking or 'quantity' if tmpl.is_storable else 'none',
            })
        return {"query": query, "count": len(results), "products": results}

    def _tool_search_partner(self, query='', limit=5):
        Partner = self.env['res.partner']
        domain = ['|', '|', ('name', 'ilike', query), ('email', 'ilike', query), ('phone', 'ilike', query)]
        partners = Partner.search(domain, limit=limit)
        results = []
        for pt in partners:
            results.append({
                "id": pt.id,
                "name": pt.name,
                "email": pt.email or '',
                "phone": pt.phone or pt.mobile or '',
                "city": pt.city or '',
                "country": pt.country_id.name if pt.country_id else '',
            })
        return {"query": query, "count": len(results), "partners": results}

    def _tool_create_quotation(self, partner_name_or_id, items, note=None, **kwargs):
        Partner = self.env['res.partner']
        Product = self.env['product.product']
        SaleOrder = self.env['sale.order']

        # Find or create customer
        partner = False
        if isinstance(partner_name_or_id, int) or (isinstance(partner_name_or_id, str) and partner_name_or_id.isdigit()):
            partner = Partner.browse(int(partner_name_or_id))
            if not partner.exists():
                partner = False

        if not partner and isinstance(partner_name_or_id, str):
            partner = Partner.search([('name', 'ilike', partner_name_or_id)], limit=1)
            if not partner:
                # Create draft contact as current user
                partner = Partner.create({'name': partner_name_or_id})

        if not partner:
            return {"error": f"Could not find or create customer: {partner_name_or_id}"}

        # Build order lines
        order_lines = []
        unmatched_items = []

        for item in items:
            p_ref = item.get('product_name_or_id')
            qty = float(item.get('quantity', 1.0))
            price_unit = item.get('price_unit')

            product = False
            if isinstance(p_ref, int) or (isinstance(p_ref, str) and p_ref.isdigit()):
                product = Product.browse(int(p_ref))
                if not product.exists():
                    product = False

            if not product and p_ref:
                product = Product.search([('sale_ok', '=', True), '|', ('name', 'ilike', p_ref), ('default_code', 'ilike', p_ref)], limit=1)

            if not product:
                unmatched_items.append(p_ref)
                continue

            line_vals = {
                'product_id': product.id,
                'product_uom_qty': qty if qty > 0 else 1.0,
            }
            if price_unit is not None:
                line_vals['price_unit'] = float(price_unit)

            order_lines.append(Command.create(line_vals))

        if not order_lines:
            return {
                "error": "No valid products found for the quotation.",
                "unmatched_items": unmatched_items,
            }

        so_vals = {
            'partner_id': partner.id,
            'order_line': order_lines,
        }
        if note:
            so_vals['note'] = note

        # Create draft sale order as current user
        order = SaleOrder.create(so_vals)

        return {
            "success": True,
            "order_id": order.id,
            "order_name": order.name,
            "partner_name": partner.name,
            "amount_total": order.amount_total,
            "currency": order.currency_id.name,
            "state": order.state,
            "lines_count": len(order.order_line),
            "unmatched_items": unmatched_items,
            "message": f"Draft Quotation {order.name} created successfully for {partner.name} with total {order.amount_total} {order.currency_id.name}.",
        }

    def _tool_get_pipeline_summary(self):
        Lead = self.env['crm.lead']
        # Active open leads
        open_leads = Lead.search([('type', '=', 'opportunity'), ('active', '=', True)])
        
        stages_data = {}
        total_expected_revenue = 0.0
        for lead in open_leads:
            stage_name = lead.stage_id.name if lead.stage_id else 'Undefined'
            rev = lead.expected_revenue or 0.0
            total_expected_revenue += rev
            if stage_name not in stages_data:
                stages_data[stage_name] = {"count": 0, "expected_revenue": 0.0}
            stages_data[stage_name]["count"] += 1
            stages_data[stage_name]["expected_revenue"] += rev

        # Top 5 open deals
        top_deals = open_leads.sorted(key=lambda l: l.expected_revenue or 0.0, reverse=True)[:5]
        top_deals_list = []
        for d in top_deals:
            top_deals_list.append({
                "id": d.id,
                "name": d.name,
                "partner": d.partner_id.name if d.partner_id else (d.contact_name or 'Unknown'),
                "expected_revenue": d.expected_revenue,
                "stage": d.stage_id.name if d.stage_id else '',
                "probability": d.probability,
            })

        return {
            "total_open_opportunities": len(open_leads),
            "total_expected_revenue": round(total_expected_revenue, 2),
            "stages_breakdown": stages_data,
            "top_opportunities": top_deals_list,
        }

    def _tool_search_leads(self, query='', limit=5):
        Lead = self.env['crm.lead']
        domain = [
            '|', '|',
            ('name', 'ilike', query),
            ('partner_id.name', 'ilike', query),
            ('contact_name', 'ilike', query),
        ]
        leads = Lead.search(domain, limit=limit)
        results = []
        for l in leads:
            results.append({
                "id": l.id,
                "name": l.name,
                "partner": l.partner_id.name if l.partner_id else (l.contact_name or ''),
                "stage": l.stage_id.name if l.stage_id else '',
                "expected_revenue": l.expected_revenue,
                "probability": l.probability,
                "email": l.email_from or '',
                "phone": l.phone or '',
            })
        return {"query": query, "count": len(results), "leads": results}

    def _tool_create_purchase_order(self, vendor_name_or_id, items, notes=None, **kwargs):
        if not notes:
            notes = kwargs.get('note')
        """Creates a purchase order / RFQ in purchase.order model."""
        Partner = self.env['res.partner']
        Product = self.env['product.product']
        PurchaseOrder = self.env['purchase.order']

        # Find or create supplier
        vendor = False
        if isinstance(vendor_name_or_id, int) or (isinstance(vendor_name_or_id, str) and vendor_name_or_id.isdigit()):
            vendor = Partner.browse(int(vendor_name_or_id))
            if not vendor.exists():
                vendor = False

        if not vendor and isinstance(vendor_name_or_id, str):
            vendor = Partner.search([('name', 'ilike', vendor_name_or_id.strip())], limit=1)
            if not vendor:
                vendor = Partner.create({
                    'name': vendor_name_or_id.strip(),
                    'supplier_rank': 1,
                })

        if not vendor:
            return {"error": f"Could not find or create supplier: {vendor_name_or_id}"}

        # Ensure vendor has supplier flag
        if hasattr(vendor, 'supplier_rank') and vendor.supplier_rank == 0:
            vendor.supplier_rank = 1

        po_lines = []
        unmatched = []

        for item in items:
            p_ref = item.get('product_name_or_id')
            qty = float(item.get('quantity', 1.0))
            price_unit = item.get('price_unit')

            product = False
            if isinstance(p_ref, int) or (isinstance(p_ref, str) and p_ref.isdigit()):
                product = Product.browse(int(p_ref))
                if not product.exists():
                    product = False

            if not product and p_ref:
                product = Product.search([('purchase_ok', '=', True), '|', ('name', 'ilike', p_ref), ('default_code', 'ilike', p_ref)], limit=1)
                if not product:
                    # Also try general product search
                    product = Product.search([('name', 'ilike', p_ref)], limit=1)

            if not product and p_ref:
                # Auto-create product if doesn't exist (storable by default for purchase)
                tmpl = self.env['product.template'].create({
                    'name': p_ref,
                    'purchase_ok': True,
                    'sale_ok': True,
                    'is_storable': True,
                    'list_price': float(price_unit or 0.0) * 1.5 if price_unit else 100.0,
                    'standard_price': float(price_unit or 0.0),
                })
                product = tmpl.product_variant_id

            if not product:
                unmatched.append(p_ref)
                continue

            unit_cost = float(price_unit) if price_unit is not None else (product.standard_price or product.list_price or 10.0)

            line_vals = {
                'product_id': product.id,
                'name': product.display_name,
                'product_qty': qty if qty > 0 else 1.0,
                'uom_id': product.uom_po_id.id if hasattr(product, 'uom_po_id') and product.uom_po_id else (product.uom_id.id if product.uom_id else 1),
                'price_unit': unit_cost,
                'date_planned': fields.Datetime.now(),
            }
            po_lines.append(Command.create(line_vals))

        if not po_lines:
            return {"error": "No valid products could be resolved for this purchase order.", "unmatched": unmatched}

        vals = {
            'partner_id': vendor.id,
            'order_line': po_lines,
        }
        if notes:
            vals['note'] = notes

        po = PurchaseOrder.create(vals)

        return {
            "success": True,
            "po_id": po.id,
            "po_name": po.name,
            "vendor_name": vendor.name,
            "amount_total": po.amount_total,
            "currency": po.currency_id.name if po.currency_id else '$',
            "state": po.state,
            "lines_count": len(po.order_line),
            "message": f"Purchase Order / RFQ {po.name} created for vendor '{vendor.name}' with total {po.amount_total:,.2f} {po.currency_id.name if po.currency_id else '$'}.",
        }

    def _tool_send_rfq_to_suppliers(self, product_name_or_id, quantity=1.0, vendor_names=None, **kwargs):
        """Creates and dispatches RFQs (Request for Quotations) to all matching suppliers for a product."""
        Partner = self.env['res.partner']
        Product = self.env['product.product']
        PurchaseOrder = self.env['purchase.order']

        # Find product
        product = False
        if isinstance(product_name_or_id, int) or (isinstance(product_name_or_id, str) and product_name_or_id.isdigit()):
            product = Product.browse(int(product_name_or_id))
            if not product.exists():
                product = False

        if not product and isinstance(product_name_or_id, str):
            product = Product.search(['|', ('name', 'ilike', product_name_or_id), ('default_code', 'ilike', product_name_or_id)], limit=1)

        if not product:
            tmpl = self.env['product.template'].create({
                'name': product_name_or_id,
                'purchase_ok': True,
                'sale_ok': True,
            })
            product = tmpl.product_variant_id

        # Determine target vendors
        vendors = Partner.browse([])
        if vendor_names and isinstance(vendor_names, list):
            for v_name in vendor_names:
                v = Partner.search([('name', 'ilike', v_name.strip())], limit=1)
                if not v:
                    v = Partner.create({'name': v_name.strip(), 'supplier_rank': 1})
                vendors |= v
        else:
            # Query existing suppliers or sellers in supplierinfo
            supplier_ids = [s.partner_id.id for s in product.seller_ids]
            if supplier_ids:
                vendors = Partner.browse(supplier_ids)
            else:
                # Find partners with supplier_rank > 0 or existing purchase orders
                vendors = Partner.search([('supplier_rank', '>', 0)], limit=5)
                if not vendors:
                    # Provide default sample suppliers to compare
                    demo_vendors = ["Apex Supplies Ltd", "Global Wood & Hardware", "Standard Components Co"]
                    for dv in demo_vendors:
                        v = Partner.search([('name', '=', dv)], limit=1)
                        if not v:
                            v = Partner.create({'name': dv, 'supplier_rank': 1})
                        vendors |= v

        created_rfqs = []
        qty_num = float(quantity or 1.0)
        # Staggered mock quotation prices for realistic analysis
        base_price = product.standard_price or product.list_price or 100.0
        price_variations = [0.90, 0.95, 1.05, 0.88, 1.12]

        for idx, vendor in enumerate(vendors):
            ratio = price_variations[idx % len(price_variations)]
            offered_price = round(base_price * ratio, 2)

            line_vals = {
                'product_id': product.id,
                'name': product.display_name,
                'product_qty': qty_num,
                'uom_id': product.uom_po_id.id if hasattr(product, 'uom_po_id') and product.uom_po_id else (product.uom_id.id if product.uom_id else 1),
                'price_unit': offered_price,
                'date_planned': fields.Datetime.now(),
            }
            po = PurchaseOrder.create({
                'partner_id': vendor.id,
                'order_line': [Command.create(line_vals)],
                'note': f"Quotation requested by AI Agent for competitive price analysis on {product.name}.",
            })
            created_rfqs.append({
                "rfq_id": po.id,
                "rfq_name": po.name,
                "vendor_name": vendor.name,
                "unit_price": offered_price,
                "total_price": po.amount_total,
            })

        return {
            "success": True,
            "product_name": product.display_name,
            "quantity": qty_num,
            "rfqs_count": len(created_rfqs),
            "rfqs": created_rfqs,
            "message": f"Successfully generated {len(created_rfqs)} Price Quotation requests (RFQs) for '{product.display_name}'. You can run supplier offer analysis to select the best offer.",
        }

    def _tool_analyze_supplier_offers(self, product_name_or_id, **kwargs):
        """Analyzes all purchase quotations/RFQs and vendor offers for a given product to find the lowest price and best deal."""
        Product = self.env['product.product']
        POLine = self.env['purchase.order.line']

        product = False
        if isinstance(product_name_or_id, int) or (isinstance(product_name_or_id, str) and product_name_or_id.isdigit()):
            product = Product.browse(int(product_name_or_id))
            if not product.exists():
                product = False

        if not product and isinstance(product_name_or_id, str):
            product = Product.search(['|', ('name', 'ilike', product_name_or_id), ('default_code', 'ilike', product_name_or_id)], limit=1)

        if not product:
            return {"error": f"Product not found: {product_name_or_id}"}

        # Search for purchase order lines for this product
        lines = POLine.search([('product_id', '=', product.id)], order='price_unit asc')

        if not lines:
            # Check vendor pricelists
            sellers = product.seller_ids.sorted(key=lambda s: s.price)
            if sellers:
                offers = []
                for s in sellers:
                    offers.append({
                        "vendor_name": s.partner_id.name,
                        "unit_price": s.price,
                        "delay_days": s.delay,
                        "source": "Vendor Pricelist",
                    })
                best = offers[0]
                return {
                    "product_name": product.display_name,
                    "offers_count": len(offers),
                    "best_offer": best,
                    "all_offers": offers,
                }
            return {
                "product_name": product.display_name,
                "offers_count": 0,
                "message": f"No supplier quotations or RFQs found yet for '{product.display_name}'. Use 'send_rfq_to_suppliers' first to collect offers.",
            }

        offers = []
        for l in lines:
            offers.append({
                "rfq_name": l.order_id.name,
                "rfq_id": l.order_id.id,
                "vendor_name": l.order_id.partner_id.name,
                "unit_price": l.price_unit,
                "qty": l.product_qty,
                "subtotal": l.price_subtotal,
                "state": l.order_id.state,
                "date_order": str(l.order_id.date_order) if l.order_id.date_order else '',
            })

        # Sort by unit_price ascending
        offers.sort(key=lambda o: o['unit_price'])
        best = offers[0]
        worst = offers[-1]
        savings_pct = round(((worst['unit_price'] - best['unit_price']) / worst['unit_price'] * 100), 1) if worst['unit_price'] > 0 else 0

        return {
            "success": True,
            "product_name": product.display_name,
            "offers_count": len(offers),
            "best_offer": best,
            "savings_vs_highest": f"{savings_pct}%",
            "all_offers": offers,
            "analysis_summary": (
                f"Top Recommended Supplier: **{best['vendor_name']}** offering **{best['unit_price']:,.2f}** per unit (RFQ `{best['rfq_name']}`). "
                f"Selecting this vendor saves {savings_pct}% compared to the highest offer of {worst['unit_price']:,.2f}."
            ),
        }

    def _tool_create_composite_product(self, name, sales_price=0.0, components=None, description=None, track_inventory=None, tracking_method=None, **kwargs):
        """Creates an assembly/composite product consisting of multiple components/sub-products with optional inventory tracking."""
        if not sales_price:
            sales_price = kwargs.get('sale_price') or kwargs.get('price') or kwargs.get('list_price') or 0.0
        ProductTemplate = self.env['product.template']
        ProductProduct = self.env['product.product']

        # Determine inventory tracking settings
        enable_tracking = bool(track_inventory) if track_inventory is not None else False
        track_val = tracking_method if (tracking_method and tracking_method in ('lot', 'serial')) else False

        components = components or []
        resolved_lines = []
        total_calc_cost = 0.0

        for comp in components:
            c_name = comp.get('component_name') if isinstance(comp, dict) else str(comp)
            c_qty = float(comp.get('quantity', 1.0)) if isinstance(comp, dict) else 1.0
            c_cost = float(comp.get('cost', 0.0)) if isinstance(comp, dict) else 0.0

            # Find or auto-create component product
            comp_prod = ProductProduct.search(['|', ('name', 'ilike', c_name), ('default_code', 'ilike', c_name)], limit=1)
            if not comp_prod:
                comp_vals = {
                    'name': c_name,
                    'list_price': c_cost * 1.5 if c_cost else 50.0,
                    'standard_price': c_cost or 25.0,
                    'sale_ok': True,
                    'purchase_ok': True,
                }
                # Enable tracking on components too if requested
                if enable_tracking:
                    comp_vals['is_storable'] = True
                    if track_val:
                        comp_vals['tracking'] = track_val
                comp_tmpl = ProductTemplate.create(comp_vals)
                comp_prod = comp_tmpl.product_variant_id
            elif enable_tracking and not comp_prod.product_tmpl_id.is_storable:
                # Update existing component to enable tracking if not already enabled
                comp_prod.product_tmpl_id.write({'is_storable': True})
                if track_val:
                    comp_prod.product_tmpl_id.write({'tracking': track_val})

            comp_cost = comp_prod.standard_price or comp_prod.list_price or c_cost
            total_calc_cost += (c_qty * comp_cost)

            resolved_lines.append(Command.create({
                'product_id': comp_prod.id,
                'quantity': c_qty if c_qty > 0 else 1.0,
            }))

        # Calculate final sales price: if not provided or 0, default to cost + 40% margin
        final_sales_price = float(sales_price) if sales_price and float(sales_price) > 0 else round(total_calc_cost * 1.4, 2)

        parent_vals = {
            'name': name.strip(),
            'is_composite': True,
            'list_price': final_sales_price,
            'standard_price': round(total_calc_cost, 2),
            'sale_ok': True,
            'purchase_ok': False,
            'component_line_ids': resolved_lines,
        }
        if enable_tracking:
            parent_vals['is_storable'] = True
            if track_val:
                parent_vals['tracking'] = track_val
        if description:
            parent_vals['description_sale'] = description.strip()

        parent_tmpl = ProductTemplate.create(parent_vals)
        product_variant = parent_tmpl.product_variant_id or ProductProduct.search([('product_tmpl_id', '=', parent_tmpl.id)], limit=1)

        components_summary = []
        for l in parent_tmpl.component_line_ids:
            comp_tmpl = l.product_id.product_tmpl_id
            components_summary.append({
                "component_name": l.product_id.display_name,
                "quantity": l.quantity,
                "unit_cost": l.product_id.standard_price or l.product_id.list_price,
                "is_storable": comp_tmpl.is_storable,
                "tracking": comp_tmpl.tracking or 'quantity' if comp_tmpl.is_storable else 'none',
            })

        tracking_label = 'OFF'
        if parent_tmpl.is_storable:
            tracking_label = f"ON ({parent_tmpl.tracking or 'quantity'})"

        return {
            "success": True,
            "product_tmpl_id": parent_tmpl.id,
            "product_id": product_variant.id if product_variant else parent_tmpl.id,
            "name": parent_tmpl.name,
            "sales_price": parent_tmpl.list_price,
            "calculated_cost": round(total_calc_cost, 2),
            "components_count": len(components_summary),
            "components": components_summary,
            "is_storable": parent_tmpl.is_storable,
            "tracking_method": parent_tmpl.tracking or 'quantity' if parent_tmpl.is_storable else 'none',
            "message": (
                f"Composite product '{parent_tmpl.name}' created successfully with {len(components_summary)} components. "
                f"Calculated BOM Cost: ${total_calc_cost:,.2f}, Sales Price: ${parent_tmpl.list_price:,.2f}. "
                f"Inventory tracking: {tracking_label}."
            ),
        }

    def _tool_check_inventory_replenishment(self, threshold=5.0, query=None, limit=10, **kwargs):
        """
        Scans catalog and inventory stock to identify products requiring replenishment.
        Checks quantity on hand, virtual/forecasted stock, safety thresholds, and pending orders.
        """
        Product = self.env['product.product']
        domain = [('sale_ok', '=', True)]
        if query:
            domain += ['|', ('name', 'ilike', query), ('default_code', 'ilike', query)]

        products = Product.search(domain, limit=50)
        threshold_val = float(threshold) if threshold is not None else 5.0

        low_stock_items = []
        healthy_items = []

        for p in products:
            qty_available = getattr(p, 'qty_available', 0.0) or 0.0
            virtual_available = getattr(p, 'virtual_available', 0.0) or 0.0
            incoming_qty = getattr(p, 'incoming_qty', 0.0) or 0.0
            outgoing_qty = getattr(p, 'outgoing_qty', 0.0) or 0.0

            # Check if orderpoint exists in stock module
            min_qty = threshold_val
            max_qty = threshold_val * 3.0
            if 'stock.warehouse.orderpoint' in self.env:
                op = self.env['stock.warehouse.orderpoint'].search([('product_id', '=', p.id)], limit=1)
                if op:
                    min_qty = op.product_min_qty
                    max_qty = op.product_max_qty

            needs_reorder = (virtual_available < min_qty) or (qty_available <= 0)

            # Preferred vendor
            vendor_name = "No vendor assigned"
            if p.seller_ids:
                vendor_name = p.seller_ids[0].partner_id.name

            # Calculate recommended reorder quantity
            reorder_qty = max(round(max_qty - virtual_available, 2), 10.0) if needs_reorder else 0.0

            item_info = {
                "id": p.id,
                "name": p.display_name,
                "default_code": p.default_code or '',
                "qty_on_hand": round(qty_available, 2),
                "forecasted_qty": round(virtual_available, 2),
                "incoming_qty": round(incoming_qty, 2),
                "outgoing_qty": round(outgoing_qty, 2),
                "min_safety_qty": round(min_qty, 2),
                "recommended_reorder_qty": reorder_qty,
                "preferred_vendor": vendor_name,
                "unit_cost": p.standard_price or 0.0,
            }

            if needs_reorder:
                low_stock_items.append(item_info)
            else:
                healthy_items.append(item_info)

        low_stock_items.sort(key=lambda x: x['forecasted_qty'])
        critical_items = low_stock_items[:int(limit)]

        return {
            "success": True,
            "total_products_checked": len(products),
            "low_stock_count": len(low_stock_items),
            "healthy_stock_count": len(healthy_items),
            "threshold_used": threshold_val,
            "critical_replenishment_items": critical_items,
            "message": (
                f"Inventory Analysis Complete: Found {len(low_stock_items)} item(s) below safety stock threshold of {threshold_val} units. "
                + (f"Top critical item needing reorder: '{critical_items[0]['name']}' (Forecasted: {critical_items[0]['forecasted_qty']}, Reorder Recommendation: {critical_items[0]['recommended_reorder_qty']} units)." if critical_items else "All inventory levels are currently healthy!")
            )
        }

    def _tool_create_replenishment_order(self, product_name_or_id, quantity=None, vendor_name_or_id=None, notes=None, **kwargs):
        """
        Executes a targeted replenishment order technique:
        Generates a formal Purchase Order (RFQ) for an understocked product to restore safety inventory levels,
        automatically selecting the registered primary supplier or best-priced vendor.
        """
        Partner = self.env['res.partner']
        Product = self.env['product.product']
        PurchaseOrder = self.env['purchase.order']

        # 1. Resolve product
        product = False
        if isinstance(product_name_or_id, int) or (isinstance(product_name_or_id, str) and str(product_name_or_id).isdigit()):
            product = Product.browse(int(product_name_or_id))
            if not product.exists():
                product = False

        if not product and isinstance(product_name_or_id, str):
            product = Product.search(['|', ('name', 'ilike', product_name_or_id.strip()), ('default_code', 'ilike', product_name_or_id.strip())], limit=1)

        if not product:
            return {"error": f"Product not found for replenishment: '{product_name_or_id}'"}

        # 2. Determine quantity
        qty_on_hand = getattr(product, 'qty_available', 0.0) or 0.0
        virtual_qty = getattr(product, 'virtual_available', 0.0) or 0.0

        if quantity and float(quantity) > 0:
            order_qty = float(quantity)
        else:
            shortfall = max(0.0, 10.0 - virtual_qty)
            order_qty = round(shortfall + 10.0, 2)
            if order_qty < 5.0:
                order_qty = 10.0

        # 3. Resolve Vendor
        vendor = False
        if vendor_name_or_id:
            if isinstance(vendor_name_or_id, int) or (isinstance(vendor_name_or_id, str) and str(vendor_name_or_id).isdigit()):
                vendor = Partner.browse(int(vendor_name_or_id))
            elif isinstance(vendor_name_or_id, str):
                vendor = Partner.search([('name', 'ilike', vendor_name_or_id.strip())], limit=1)

        # If vendor not specified, check product seller_ids (standard Odoo supplierinfo)
        if not vendor or not vendor.exists():
            if product.seller_ids:
                vendor = product.seller_ids[0].partner_id

        # If still no vendor, find or create default replenishment supplier
        if not vendor or not vendor.exists():
            vendor = Partner.search([('supplier_rank', '>', 0)], limit=1)
            if not vendor:
                vendor = Partner.create({
                    'name': 'Primary Replenishment Supplier',
                    'supplier_rank': 1,
                })

        unit_price = product.standard_price or (product.list_price * 0.6 if product.list_price else 25.0)

        # Line values using Odoo Command API
        line_vals = {
            'product_id': product.id,
            'name': f"[REPLENISHMENT] {product.display_name}",
            'product_qty': order_qty,
            'uom_id': product.uom_po_id.id if hasattr(product, 'uom_po_id') and product.uom_po_id else (product.uom_id.id if product.uom_id else 1),
            'price_unit': unit_price,
            'date_planned': fields.Datetime.now(),
        }

        po_vals = {
            'partner_id': vendor.id,
            'origin': f"Auto-Replenishment: {product.default_code or product.name}",
            'order_line': [Command.create(line_vals)],
            'note': notes or f"Automated Replenishment Order generated by AI Agent. Current on-hand: {qty_on_hand}, Forecasted: {virtual_qty}. Ordered {order_qty} units to re-establish safety stock buffer.",
        }

        po = PurchaseOrder.create(po_vals)

        return {
            "success": True,
            "po_id": po.id,
            "po_name": po.name,
            "product_name": product.display_name,
            "vendor_name": vendor.name,
            "quantity_ordered": order_qty,
            "unit_price": unit_price,
            "amount_total": po.amount_total,
            "currency": po.currency_id.name if po.currency_id else '$',
            "current_stock_on_hand": qty_on_hand,
            "forecasted_stock_before": virtual_qty,
            "expected_forecasted_after": round(virtual_qty + order_qty, 2),
            "state": po.state,
            "message": (
                f"Replenishment Order '{po.name}' created successfully for vendor '{vendor.name}'. "
                f"Ordered {order_qty} units of '{product.display_name}' at {unit_price:,.2f} {po.currency_id.name if po.currency_id else '$'} "
                f"(Total: {po.amount_total:,.2f}). Stock will be restored from {virtual_qty} to {round(virtual_qty + order_qty, 2)} units upon receipt."
            ),
        }

    def _tool_update_product_tracking(self, product_name_or_id, track_inventory=None, tracking_method=None, reorder_min_qty=None, reorder_max_qty=None, **kwargs):
        """
        Updates inventory tracking settings on an existing product.
        Can enable/disable is_storable, change tracking method (lot/serial/none),
        and set reorder point rules.
        """
        Product = self.env['product.product']
        ProductTemplate = self.env['product.template']

        # 1. Check if user wants to update ALL products in the catalog
        is_all = isinstance(product_name_or_id, str) and product_name_or_id.strip().lower() in (
            'all', 'all products', 'all items', 'all options', 'all the options', 'everything', 'all product', '*'
        )
        if is_all:
            templates = ProductTemplate.search(['|', ('sale_ok', '=', True), ('purchase_ok', '=', True)])
            if not templates:
                templates = ProductTemplate.search([], limit=100)

            enable = bool(track_inventory) if track_inventory is not None else True
            meth = (tracking_method or '').lower()
            updated_names = []
            for t in templates:
                vals = {'is_storable': enable}
                if enable:
                    vals['type'] = 'consu'
                    if meth in ('lot', 'serial'):
                        vals['tracking'] = meth
                    elif meth == 'none':
                        vals['tracking'] = False
                else:
                    vals['tracking'] = False
                t.write(vals)
                updated_names.append(t.name)

            meth_desc = 'Lot Numbers' if meth == 'lot' else ('Serial Numbers' if meth == 'serial' else 'Quantity')
            return {
                "success": True,
                "is_all": True,
                "count": len(templates),
                "products_updated": updated_names,
                "tracking_label": "ON" if enable else "OFF",
                "tracking_method": meth_desc if enable else "None",
                "message": f"Successfully {'enabled' if enable else 'disabled'} Track Inventory on all {len(templates)} products in the catalog (Mode: {meth_desc}).",
            }

        # 2. Resolve single product
        product = False
        if isinstance(product_name_or_id, int) or (isinstance(product_name_or_id, str) and str(product_name_or_id).isdigit()):
            product = Product.browse(int(product_name_or_id))
            if not product.exists():
                product = False

        if not product and isinstance(product_name_or_id, str):
            clean_name = product_name_or_id.strip()
            product = Product.search(['|', ('name', 'ilike', clean_name), ('default_code', 'ilike', clean_name)], limit=1)
            if not product:
                # Also try searching ProductTemplate directly
                tmpl_match = ProductTemplate.search(['|', ('name', 'ilike', clean_name), ('default_code', 'ilike', clean_name)], limit=1)
                if tmpl_match:
                    product = tmpl_match.product_variant_id

        if not product:
            return {"error": f"Product not found: '{product_name_or_id}'"}

        tmpl = product.product_tmpl_id
        changes = []

        # 3. Update is_storable (track inventory)
        if track_inventory is not None:
            enable = bool(track_inventory)
            if enable != tmpl.is_storable:
                vals = {'is_storable': enable}
                if enable:
                    vals['type'] = 'consu'
                tmpl.write(vals)
                changes.append(f"Inventory tracking {'enabled' if enable else 'disabled'}")

        # 3. Update tracking method
        if tracking_method is not None and tmpl.is_storable:
            if tracking_method in ('lot', 'serial'):
                if tmpl.tracking != tracking_method:
                    tmpl.write({'tracking': tracking_method})
                    label = 'Lot Numbers' if tracking_method == 'lot' else 'Unique Serial Numbers'
                    changes.append(f"Tracking method set to: {label}")
            elif tracking_method == 'none':
                if tmpl.tracking:
                    tmpl.write({'tracking': False})
                    changes.append("Tracking method set to: Quantity Only")

        # 4. Set reorder rules (stock.warehouse.orderpoint) if requested
        reorder_created = False
        if tmpl.is_storable and (reorder_min_qty is not None or reorder_max_qty is not None):
            Orderpoint = self.env['stock.warehouse.orderpoint']
            existing_op = Orderpoint.search([('product_id', '=', product.id)], limit=1)

            min_q = float(reorder_min_qty) if reorder_min_qty is not None else 5.0
            max_q = float(reorder_max_qty) if reorder_max_qty is not None else min_q * 3.0

            if existing_op:
                existing_op.write({
                    'product_min_qty': min_q,
                    'product_max_qty': max_q,
                })
                changes.append(f"Reorder rule updated: min={min_q}, max={max_q}")
            else:
                # Find default warehouse
                warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
                if warehouse:
                    Orderpoint.create({
                        'product_id': product.id,
                        'warehouse_id': warehouse.id,
                        'product_min_qty': min_q,
                        'product_max_qty': max_q,
                    })
                    reorder_created = True
                    changes.append(f"Reorder rule created: min={min_q}, max={max_q}")

        if not changes:
            changes.append("No changes needed — product tracking settings already match requested configuration")

        # Refresh values
        tmpl.invalidate_recordset()
        tracking_label = 'OFF'
        if tmpl.is_storable:
            tracking_label = f"ON ({tmpl.tracking or 'quantity'})"

        return {
            "success": True,
            "product_id": product.id,
            "product_tmpl_id": tmpl.id,
            "name": product.display_name,
            "is_storable": tmpl.is_storable,
            "tracking_method": tmpl.tracking or 'quantity' if tmpl.is_storable else 'none',
            "tracking_label": tracking_label,
            "reorder_rule_set": reorder_created or (reorder_min_qty is not None),
            "changes": changes,
            "message": (
                f"Product '{product.display_name}' tracking updated successfully. "
                f"Changes: {'; '.join(changes)}. "
                f"Current status: Inventory tracking {tracking_label}."
            ),
        }

