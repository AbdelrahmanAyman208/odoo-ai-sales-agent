# -*- coding: utf-8 -*-
"""
Product Attribute & Variant Management Tools (Phase 9, Global Decision 8).
Features:
- Attribute & value creation / reuse.
- Product template attribute lines & price_extra.
- Variant matrix quotation support.
- Explosion guard: Prevents combinatorial explosion if potential variant count exceeds limit (default 100).

Complexity:
- Time: O(V) where V is generated variants.
- Space: O(V) variants created in batch.
"""
import itertools
import logging
from typing import Any, Dict, List, Optional
from odoo.exceptions import UserError
from ..tools.base import agent_tool
from ..services.product_resolver import find_or_disambiguate_product

_logger = logging.getLogger(__name__)


@agent_tool(
    name="configure_product_variants",
    domain="sales",
    label="Configure Product Attributes & Variants",
    description="Creates or configures product attributes (e.g. Color, Size, Trim), attribute values, price extras, and generates variants safely with explosion guards.",
    tier="T1",
    available_if=["sale_management"],
    examples=["Add Color (Red, Blue) and Size (S, M, L) to T-Shirt", "Configure variants for Desk"],
    parameters={
        "type": "object",
        "properties": {
            "product_name_or_id": {"type": "string", "description": "Product template name or ID"},
            "attributes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Attribute name (e.g. Color, Size)"},
                        "values": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "price_extra": {"type": "number", "default": 0.0},
                                },
                                "required": ["name"],
                            },
                        },
                    },
                    "required": ["name", "values"],
                },
                "description": "List of attributes with their values and optional price extra",
            },
            "max_variant_limit": {"type": "integer", "default": 100, "description": "Maximum allowed variants before explosion guard aborts"},
        },
        "required": ["product_name_or_id", "attributes"],
    },
)
def configure_product_variants(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    prod, disambig = find_or_disambiguate_product(env, str(args["product_name_or_id"]))
    if disambig:
        return {"success": False, "disambiguation_required": True, "candidates": disambig}
    if not prod:
        return {"success": False, "error": f"Product '{args['product_name_or_id']}' not found"}

    template = prod.product_tmpl_id
    attributes_data = args.get("attributes", [])

    # 1. Variant Explosion Guard (G2 & Phase 9)
    total_combinations = 1
    for attr in attributes_data:
        val_count = len(attr.get("values", []))
        if val_count > 0:
            total_combinations *= val_count

    max_limit = args.get("max_variant_limit", 100)
    if total_combinations > max_limit:
        return {
            "success": False,
            "error": f"Variant Explosion Guard: Requested configuration would create {total_combinations} variants, which exceeds the safety limit of {max_limit}. Consider dynamic creation or splitting attributes."
        }

    Attribute = env['product.attribute']
    AttributeVal = env['product.attribute.value']
    LineModel = env['product.template.attribute.line']

    added_attributes = []

    for attr_dict in attributes_data:
        attr_name = attr_dict["name"].strip()
        # Find or create attribute
        attribute = Attribute.search([('name', '=ilike', attr_name)], limit=1)
        if not attribute:
            attribute = Attribute.create({'name': attr_name, 'create_variant': 'always'})

        value_ids = []
        for val_dict in attr_dict.get("values", []):
            val_name = val_dict["name"].strip()
            val_rec = AttributeVal.search([('attribute_id', '=', attribute.id), ('name', '=ilike', val_name)], limit=1)
            if not val_rec:
                val_rec = AttributeVal.create({'attribute_id': attribute.id, 'name': val_name})
            value_ids.append(val_rec.id)

        # Check existing line on template
        existing_line = template.attribute_line_ids.filtered(lambda l: l.attribute_id.id == attribute.id)
        if existing_line:
            existing_line.write({'value_ids': [(6, 0, list(set(existing_line.value_ids.ids + value_ids)))]})
        else:
            LineModel.create({
                'product_tmpl_id': template.id,
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, value_ids)],
            })

        added_attributes.append(attribute.name)

    # Apply price extras
    for attr_dict in attributes_data:
        for val_dict in attr_dict.get("values", []):
            extra = val_dict.get("price_extra", 0.0)
            if extra > 0:
                ptav = template.attribute_line_ids.product_template_value_ids.filtered(
                    lambda v: v.name.lower() == val_dict["name"].strip().lower()
                )
                if ptav:
                    ptav.write({'price_extra': extra})

    # Flush variants
    template._create_variant_ids()

    variants_count = len(template.product_variant_ids)
    return {
        "success": True,
        "template_id": template.id,
        "template_name": template.name,
        "attributes_configured": added_attributes,
        "total_variants_count": variants_count,
        "message": f"Configured {len(added_attributes)} attribute(s) for '{template.name}'. Generated {variants_count} product variants.",
    }
