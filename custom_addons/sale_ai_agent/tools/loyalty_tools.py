# -*- coding: utf-8 -*-
"""
Promotions, Coupons, and Loyalty Programs Domain Tools (Phase 10, Global Decision 8).
Features:
- Program management: promotions, discount codes, coupons, loyalty cards.
- Bulk coupon generation with create([vals_list]) and T2 gating above limit.
- Apply & preview promotions on sale orders.
- Customer pricelists and rules.
- Usage and performance reporting.

Complexity:
- Time: O(N) batch coupon generation; O(1) single-order promotion preview.
- Space: O(N) where N is generated coupons list.
"""
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from ..tools.base import agent_tool
from ..services.partner_resolver import find_or_disambiguate_partner
from ..services.product_resolver import find_or_disambiguate_product
from ..services.document_linker import link_ai_context_vals

_logger = logging.getLogger(__name__)


@agent_tool(
    name="manage_loyalty_program",
    domain="loyalty",
    label="Create or Update Promotion / Loyalty Program",
    description="Creates or updates promotional programs, coupon rules, discounts, and reward configurations.",
    tier="T1",
    available_if=["loyalty"],
    examples=["Create 10% summer promotion", "Setup loyalty card program"],
    parameters={
        "type": "object",
        "properties": {
            "program_id": {"type": "integer", "description": "Existing program ID if updating"},
            "name": {"type": "string", "description": "Program Name"},
            "program_type": {
                "type": "string",
                "enum": ["promotion", "coupons", "promo_code", "loyalty", "buy_x_get_y", "gift_card"],
                "default": "promotion",
            },
            "discount_percentage": {"type": "number", "description": "Discount percent (e.g. 10 for 10%)"},
            "minimum_amount": {"type": "number", "description": "Minimum purchase amount to qualify"},
            "minimum_qty": {"type": "integer", "description": "Minimum item quantity required"},
            "code": {"type": "string", "description": "Optional promo code string"},
            "active": {"type": "boolean", "default": True},
        },
    },
)
def manage_loyalty_program(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    LoyaltyProgram = env['loyalty.program']
    LoyaltyRule = env['loyalty.rule']
    LoyaltyReward = env['loyalty.reward']

    prog_id = args.get("program_id")
    name = args.get("name") or "Promotional Campaign"
    prog_type = args.get("program_type", "promotion")

    vals = {
        'name': name,
        'program_type': prog_type,
        'applies_on': 'current' if prog_type != 'next_order_coupons' else 'future',
        'active': args.get('active', True),
    }

    if prog_id:
        program = LoyaltyProgram.browse(prog_id)
        if not program.exists():
            return {"success": False, "error": f"Loyalty program {prog_id} not found"}
        program.write(vals)
        action_type = "updated"
    else:
        # Prevent duplicates via idempotency hash
        existing = LoyaltyProgram.search([('name', '=ilike', name), ('program_type', '=', prog_type)], limit=1)
        if existing:
            return {
                "success": True,
                "program_id": existing.id,
                "name": existing.name,
                "message": f"Identified existing program '{existing.name}' (ID: {existing.id}). No duplicate created.",
            }
        program = LoyaltyProgram.create(vals)
        action_type = "created"

    # Configure Rule if minimum criteria specified
    min_amount = args.get("minimum_amount", 0.0)
    min_qty = args.get("minimum_qty", 0)
    code = args.get("code")

    if min_amount or min_qty or code:
        rule_vals = {
            'program_id': program.id,
            'minimum_amount': min_amount,
            'minimum_qty': min_qty or 1,
        }
        if code:
            rule_vals['code'] = code.strip()

        if program.rule_ids:
            program.rule_ids[0].write(rule_vals)
        else:
            LoyaltyRule.create(rule_vals)

    # Configure Discount Reward
    disc_pct = args.get("discount_percentage")
    if disc_pct is not None and disc_pct > 0:
        reward_vals = {
            'program_id': program.id,
            'reward_type': 'discount',
            'discount': disc_pct,
            'discount_mode': 'percent',
        }
        if program.reward_ids:
            program.reward_ids[0].write(reward_vals)
        else:
            LoyaltyReward.create(reward_vals)

    return {
        "success": True,
        "program_id": program.id,
        "name": program.name,
        "program_type": program.program_type,
        "action": action_type,
        "message": f"Loyalty / Promotion Program '{program.name}' successfully {action_type} (ID: {program.id}).",
    }


@agent_tool(
    name="generate_coupons",
    domain="loyalty",
    label="Generate Bulk Coupons for Program",
    description="Bulk generates unique coupon cards for a coupon program using batch creation create([vals_list]). Requests > 100 coupons require T2 approval.",
    tier="T1",
    available_if=["loyalty"],
    examples=["Generate 20 coupons for Summer Promo", "Issue 50 coupon codes"],
    parameters={
        "type": "object",
        "properties": {
            "program_id": {"type": "integer", "description": "Coupon program ID"},
            "count": {"type": "integer", "default": 10, "description": "Number of coupons to generate (Max 100 per T1 execution)"},
            "partner_id": {"type": "integer", "description": "Optional partner ID to assign cards to"},
        },
        "required": ["program_id"],
    },
)
def generate_coupons(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    LoyaltyProgram = env['loyalty.program']
    LoyaltyCard = env['loyalty.card']

    program = LoyaltyProgram.browse(args["program_id"])
    if not program.exists():
        return {"success": False, "error": f"Program {args['program_id']} not found"}

    count = int(args.get("count", 10))
    if count > 100:
        # Escalate to T2 approval requirement
        return {
            "success": False,
            "tier_escalation": "T2",
            "error": f"Generating {count} coupons exceeds single-batch safety limit (100). Escalate with human approval.",
        }

    partner_id = args.get("partner_id")
    vals_list = []
    for _ in range(count):
        code = program._generate_report_id() if hasattr(program, '_generate_report_id') else LoyaltyCard._generate_code()
        vals_list.append({
            'program_id': program.id,
            'code': code,
            'partner_id': partner_id or False,
            'points': program.points_name and 1 or 0,
        })

    cards = LoyaltyCard.create(vals_list)
    return {
        "success": True,
        "program_id": program.id,
        "program_name": program.name,
        "generated_count": len(cards),
        "sample_codes": [c.code for c in cards[:5]],
        "message": f"Successfully generated {len(cards)} unique coupon code(s) for '{program.name}'.",
    }


@agent_tool(
    name="apply_promotions_to_order",
    domain="loyalty",
    label="Apply & Preview Promotions on Sale Order",
    description="Evaluates applicable loyalty/promotion programs against a sale order and previews resulting discounts.",
    tier="T1",
    available_if=["sale_loyalty", "sale_management"],
    examples=["Apply promotions to quotation SO004", "Calculate available discounts on order 5"],
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "integer", "description": "Sale Order ID"},
            "coupon_code": {"type": "string", "description": "Optional coupon or discount code to apply"},
        },
        "required": ["order_id"],
    },
)
def apply_promotions_to_order(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    order = env['sale.order'].browse(args["order_id"])
    if not order.exists():
        return {"success": False, "error": f"Sale Order {args['order_id']} not found"}

    code = (args.get("coupon_code") or '').strip()
    status_msg = ""

    if code and hasattr(order, '_try_apply_code'):
        res = order._try_apply_code(code)
        if 'error' in res:
            return {"success": False, "error": res['error']}
        status_msg = f"Applied code '{code}'."

    if hasattr(order, '_update_programs_and_rewards'):
        order._update_programs_and_rewards()

    # Calculate discount impact
    discount_lines = order.order_line.filtered(lambda l: l.is_reward_line if hasattr(l, 'is_reward_line') else (l.price_unit < 0))
    total_discount = sum(abs(l.price_subtotal) for l in discount_lines)

    return {
        "success": True,
        "order_id": order.id,
        "order_name": order.name,
        "amount_untaxed": order.amount_untaxed,
        "amount_total": order.amount_total,
        "total_discount_applied": total_discount,
        "discount_lines_count": len(discount_lines),
        "message": f"Order {order.name}: Total {order.currency_id.symbol}{order.amount_total:,.2f} with {order.currency_id.symbol}{total_discount:,.2f} discount applied. {status_msg}",
    }


@agent_tool(
    name="get_loyalty_report",
    domain="loyalty",
    label="Loyalty & Coupon Performance Report",
    description="Summarizes total active loyalty programs, coupons issued, and redeemed cards via _read_group.",
    tier="T0",
    available_if=["loyalty"],
    examples=["Show loyalty report", "How many coupons have been used?"],
    parameters={"type": "object", "properties": {}},
)
def get_loyalty_report(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    LoyaltyProgram = env['loyalty.program']
    LoyaltyCard = env['loyalty.card']

    programs = LoyaltyProgram.search_read([], ['id', 'name', 'program_type', 'active'])
    card_counts = LoyaltyCard._read_group(
        [],
        ['program_id'],
        ['__count'],
    )
    counts_map = {p.id: count for p, count in card_counts if p}

    report = []
    for prog in programs:
        p_id = prog['id']
        report.append({
            "id": p_id,
            "name": prog['name'],
            "type": prog['program_type'],
            "active": prog['active'],
            "total_cards_or_coupons": counts_map.get(p_id, 0),
        })

    return {
        "success": True,
        "total_programs": len(programs),
        "programs_overview": report,
    }
