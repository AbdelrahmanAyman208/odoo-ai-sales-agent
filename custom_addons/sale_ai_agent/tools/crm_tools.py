# -*- coding: utf-8 -*-
"""
Full CRM Implementer Domain Tools (Phase 9, Global Decision 8).
Features:
- Pipeline setup: sales teams, stages, lost reasons.
- Lead / Opportunity management: create, update, qualify, assign.
- Hash-based O(N) duplicate detection and merging.
- Lead scoring (rule-based transparent explanation).
- Batch lead extraction from structured text / CSV.
- Reporting via _read_group (pipeline by stage, win rate, stale opps).
- Quotation creation from opportunity with document linking.

Complexity:
- Time: O(N) for lead batch/merges; O(1) for stage/lead updates.
- Space: O(N) for hash dedup sets.
"""
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from ..tools.base import agent_tool
from ..services.partner_resolver import find_or_disambiguate_partner
from ..services.document_linker import link_ai_context_vals, link_record_to_ai_context

_logger = logging.getLogger(__name__)


@agent_tool(
    name="setup_crm_pipeline",
    domain="crm",
    label="Setup Sales Teams & Stages",
    description="Configures sales pipeline stages (sequence, won flag, fold) and sales teams.",
    tier="T1",
    available_if=["crm"],
    examples=["Create pipeline stage 'Negotiation' sequence 3", "Setup B2B Sales Team"],
    parameters={
        "type": "object",
        "properties": {
            "team_name": {"type": "string", "description": "Optional sales team name to create or configure"},
            "stages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "sequence": {"type": "integer"},
                        "is_won": {"type": "boolean"},
                        "fold": {"type": "boolean"},
                    },
                    "required": ["name"],
                },
                "description": "List of stages to create or update",
            },
        },
    },
)
def setup_crm_pipeline(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    CrmTeam = env['crm.team']
    CrmStage = env['crm.stage']

    team = None
    if args.get("team_name"):
        team_name = args["team_name"].strip()
        team = CrmTeam.search([('name', '=ilike', team_name)], limit=1)
        if not team:
            team = CrmTeam.create({'name': team_name})

    created_stages = []
    for s_data in args.get("stages", []):
        s_name = s_data["name"].strip()
        domain = [('name', '=ilike', s_name)]
        if team:
            domain.append(('team_ids', 'in', [team.id]))
        existing = CrmStage.search(domain, limit=1)

        vals = {
            'sequence': s_data.get('sequence', 10),
            'is_won': s_data.get('is_won', False),
            'fold': s_data.get('fold', False),
        }
        if team:
            vals['team_ids'] = [(4, team.id)]

        if existing:
            existing.write(vals)
            stage_rec = existing
        else:
            vals['name'] = s_name
            stage_rec = CrmStage.create(vals)
        created_stages.append({"id": stage_rec.id, "name": stage_rec.name, "is_won": stage_rec.is_won})

    return {
        "success": True,
        "team_id": team.id if team else None,
        "team_name": team.name if team else None,
        "stages": created_stages,
        "message": f"Pipeline configured with {len(created_stages)} stage(s).",
    }


@agent_tool(
    name="manage_leads",
    domain="crm",
    label="Create or Update CRM Lead / Opportunity",
    description="Creates or updates a lead/opportunity with contact info, expected revenue, stage, and priority.",
    tier="T1",
    available_if=["crm"],
    examples=["Create opportunity 'Office Refurbishment' for TechCorp, expected 25000", "Update lead 12 stage to Qualified"],
    parameters={
        "type": "object",
        "properties": {
            "lead_id": {"type": "integer", "description": "Existing lead ID if updating"},
            "name": {"type": "string", "description": "Lead/Opportunity title"},
            "partner_name_or_email": {"type": "string", "description": "Customer name or email"},
            "contact_name": {"type": "string", "description": "Contact person name"},
            "email_from": {"type": "string", "description": "Contact email"},
            "phone": {"type": "string", "description": "Contact phone"},
            "expected_revenue": {"type": "number", "description": "Expected revenue amount"},
            "probability": {"type": "number", "description": "Success probability (0-100)"},
            "type": {"type": "string", "enum": ["lead", "opportunity"], "default": "opportunity"},
            "stage_id": {"type": "integer", "description": "Pipeline stage ID"},
            "priority": {"type": "string", "enum": ["0", "1", "2", "3"], "description": "0=Low, 1=Medium, 2=High, 3=Very High"},
        },
    },
)
def manage_leads(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    CrmLead = env['crm.lead']
    lead_id = args.get("lead_id")

    vals = {}
    for fld in ['name', 'contact_name', 'email_from', 'phone', 'expected_revenue', 'probability', 'type', 'stage_id', 'priority']:
        if fld in args and args[fld] is not None:
            vals[fld] = args[fld]

    # Partner resolution
    partner_query = args.get("partner_name_or_email")
    if partner_query:
        partner, candidates = find_or_disambiguate_partner(env, partner_query)
        if candidates:
            return {"success": False, "disambiguation_required": True, "candidates": candidates}
        if partner:
            vals['partner_id'] = partner.id
            if not vals.get('email_from') and partner.email:
                vals['email_from'] = partner.email
            if not vals.get('phone') and partner.phone:
                vals['phone'] = partner.phone

    if lead_id:
        lead = CrmLead.browse(lead_id)
        if not lead.exists():
            return {"success": False, "error": f"Lead {lead_id} not found"}
        lead.write(vals)
        link_record_to_ai_context(lead, context)
        action_type = "updated"
    else:
        if not vals.get('name'):
            vals['name'] = f"Opportunity - {args.get('contact_name') or partner_query or 'New'}"
        vals = link_ai_context_vals(vals, context)
        lead = CrmLead.create(vals)
        action_type = "created"

    return {
        "success": True,
        "lead_id": lead.id,
        "name": lead.name,
        "type": lead.type,
        "expected_revenue": lead.expected_revenue,
        "stage": lead.stage_id.name if lead.stage_id else "New",
        "action": action_type,
        "message": f"Lead/Opportunity '{lead.name}' successfully {action_type} (ID: {lead.id}).",
    }


@agent_tool(
    name="merge_duplicate_leads",
    domain="crm",
    label="Merge Duplicate Leads (O(N) Hash Match)",
    description="Finds and merges duplicate leads based on normalized email, phone, or name matching in linear time.",
    tier="T1",
    available_if=["crm"],
    examples=["Find and merge duplicate leads", "Clean CRM duplicate leads"],
    parameters={
        "type": "object",
        "properties": {
            "auto_merge": {"type": "boolean", "default": False, "description": "If True, merges duplicates automatically keeping the oldest record"},
        },
    },
)
def merge_duplicate_leads(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    CrmLead = env['crm.lead']
    leads = CrmLead.search_read(
        [('active', '=', True)],
        ['id', 'name', 'email_from', 'phone', 'partner_id', 'create_date'],
        order='id asc'
    )

    seen_hashes = {}
    duplicates_groups = []

    for l in leads:
        email = (l.get('email_from') or '').strip().lower()
        phone = ''.join(c for c in (l.get('phone') or '') if c.isdigit())
        name = (l.get('name') or '').strip().lower()

        # Build composite identity key
        lead_key = None
        if email and len(email) > 5:
            lead_key = f"email:{email}"
        elif phone and len(phone) >= 7:
            lead_key = f"phone:{phone}"
        elif name:
            lead_key = f"name:{name}"

        if not lead_key:
            continue

        if lead_key in seen_hashes:
            primary_lead_id = seen_hashes[lead_key]
            # Find group
            found = False
            for grp in duplicates_groups:
                if grp['primary_id'] == primary_lead_id:
                    grp['duplicate_ids'].append(l['id'])
                    found = True
                    break
            if not found:
                duplicates_groups.append({
                    'key': lead_key,
                    'primary_id': primary_lead_id,
                    'duplicate_ids': [l['id']]
                })
        else:
            seen_hashes[lead_key] = l['id']

    total_dupes = sum(len(g['duplicate_ids']) for g in duplicates_groups)
    merged_count = 0

    if args.get("auto_merge") and duplicates_groups:
        for grp in duplicates_groups:
            all_ids = [grp['primary_id']] + grp['duplicate_ids']
            lead_records = CrmLead.browse(all_ids)
            try:
                # Odoo native merge
                master = lead_records._merge_opportunity(user_id=False, team_id=False)
                merged_count += len(grp['duplicate_ids'])
            except Exception as e:
                _logger.warning("Failed merging leads %s: %s", all_ids, e)

    return {
        "success": True,
        "duplicate_groups_count": len(duplicates_groups),
        "total_duplicates_found": total_dupes,
        "merged_count": merged_count,
        "groups": duplicates_groups[:10],
        "message": f"Identified {len(duplicates_groups)} duplicate group(s) ({total_dupes} duplicates). {merged_count} merged.",
    }


@agent_tool(
    name="batch_create_leads_from_text",
    domain="crm",
    label="Batch Generate Leads From Text / CSV",
    description="Extracts structured leads from pasted text or CSV rows and batch creates them with deduplication.",
    tier="T1",
    available_if=["crm"],
    examples=["Batch create leads from customer list CSV", "Import prospects text"],
    parameters={
        "type": "object",
        "properties": {
            "leads_data": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "contact_name": {"type": "string"},
                        "email": {"type": "string"},
                        "phone": {"type": "string"},
                        "company_name": {"type": "string"},
                        "expected_revenue": {"type": "number"},
                    },
                    "required": ["name"],
                },
                "description": "List of extracted lead dictionaries",
            },
        },
        "required": ["leads_data"],
    },
)
def batch_create_leads_from_text(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    CrmLead = env['crm.lead']
    leads_in = args.get("leads_data", [])
    if not leads_in:
        return {"success": False, "error": "No leads provided to import."}

    # Gather existing emails for O(1) in-memory dedup
    existing_emails = {
        l['email_from'].lower()
        for l in CrmLead.search_read([('email_from', '!=', False)], ['email_from'])
    }

    create_vals_list = []
    skipped = 0

    for item in leads_in:
        email = (item.get('email') or '').strip()
        if email and email.lower() in existing_emails:
            skipped += 1
            continue

        vals = {
            'name': item['name'],
            'contact_name': item.get('contact_name'),
            'email_from': email or False,
            'phone': item.get('phone'),
            'partner_name': item.get('company_name'),
            'expected_revenue': item.get('expected_revenue', 0.0),
            'type': 'lead',
        }
        vals = link_ai_context_vals(vals, context)
        create_vals_list.append(vals)
        if email:
            existing_emails.add(email.lower())

    created_records = []
    if create_vals_list:
        created = CrmLead.create(create_vals_list)
        created_records = [{"id": r.id, "name": r.name} for r in created]

    return {
        "success": True,
        "created_count": len(created_records),
        "skipped_duplicates": skipped,
        "created_leads": created_records[:10],
        "message": f"Successfully batch-created {len(created_records)} leads ({skipped} duplicates skipped).",
    }


@agent_tool(
    name="score_lead",
    domain="crm",
    label="Score Lead Quality (Transparent Rules)",
    description="Evaluates lead quality score (0-100) with clear explanatory factors based on data completeness and revenue.",
    tier="T0",
    available_if=["crm"],
    examples=["Score lead 42", "Evaluate quality of opportunity 15"],
    parameters={
        "type": "object",
        "properties": {
            "lead_id": {"type": "integer", "description": "Lead ID to evaluate"},
        },
        "required": ["lead_id"],
    },
)
def score_lead(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    lead = env['crm.lead'].browse(args["lead_id"])
    if not lead.exists():
        return {"success": False, "error": f"Lead {args['lead_id']} not found"}

    score = 0
    factors = []

    # Factor 1: Email present (+25)
    if lead.email_from:
        score += 25
        factors.append("+25: Valid email provided")
    else:
        factors.append("0: Missing email")

    # Factor 2: Phone present (+20)
    if lead.phone:
        score += 20
        factors.append("+20: Phone number provided")
    else:
        factors.append("0: Missing phone")

    # Factor 3: Partner linked (+20)
    if lead.partner_id:
        score += 20
        factors.append(f"+20: Linked to existing partner '{lead.partner_id.name}'")

    # Factor 4: Expected revenue (+20)
    if lead.expected_revenue > 0:
        score += 20
        factors.append(f"+20: Quantified deal value (${lead.expected_revenue:,.2f})")

    # Factor 5: Priority level (+15 max)
    priority_bonus = int(lead.priority or 0) * 5
    if priority_bonus > 0:
        score += priority_bonus
        factors.append(f"+{priority_bonus}: High priority rating ({lead.priority})")

    return {
        "success": True,
        "lead_id": lead.id,
        "lead_name": lead.name,
        "score": min(score, 100),
        "rating": "Hot" if score >= 70 else ("Warm" if score >= 40 else "Cold"),
        "factors": factors,
    }


@agent_tool(
    name="get_crm_reporting",
    domain="crm",
    label="CRM Pipeline Analytics & Health",
    description="Analyzes pipeline performance, expected revenue per stage, win rate, and overdue activities via _read_group.",
    tier="T0",
    available_if=["crm"],
    examples=["Show CRM pipeline report", "What is our current win rate?"],
    parameters={"type": "object", "properties": {}},
)
def get_crm_reporting(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    CrmLead = env['crm.lead']

    # 1. Pipeline by stage
    stage_data = CrmLead._read_group(
        [('active', '=', True)],
        ['stage_id'],
        ['__count', 'expected_revenue:sum'],
    )
    pipeline_by_stage = [
        {
            "stage_id": s.id if s else None,
            "stage_name": s.name if s else "Unassigned",
            "count": count,
            "expected_revenue": rev or 0.0,
        }
        for s, count, rev in stage_data
    ]

    # 2. Win rate calculation
    won_count = CrmLead.search_count([('active', '=', True), ('stage_id.is_won', '=', True)])
    total_active = CrmLead.search_count([('active', '=', True)])
    win_rate = (won_count / total_active * 100.0) if total_active > 0 else 0.0

    return {
        "success": True,
        "total_active_opportunities": total_active,
        "won_count": won_count,
        "win_rate_percent": round(win_rate, 1),
        "stages_breakdown": pipeline_by_stage,
    }


@agent_tool(
    name="create_quotation_from_opportunity",
    domain="crm",
    label="Create Quotation From Opportunity",
    description="Cross-module flow: Generates a draft Sale Order from a CRM opportunity and establishes two-way linking.",
    tier="T1",
    available_if=["crm", "sale_management"],
    examples=["Create quotation for opportunity 14", "Turn opportunity into sale order"],
    parameters={
        "type": "object",
        "properties": {
            "opportunity_id": {"type": "integer", "description": "CRM Opportunity ID"},
            "order_lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_name_or_id": {"type": "string"},
                        "quantity": {"type": "number"},
                        "price_unit": {"type": "number"},
                    },
                    "required": ["product_name_or_id", "quantity"],
                },
                "description": "Optional initial line items to include",
            },
        },
        "required": ["opportunity_id"],
    },
)
def create_quotation_from_opportunity(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from ..services.product_resolver import find_or_disambiguate_product

    opp = env['crm.lead'].browse(args["opportunity_id"])
    if not opp.exists():
        return {"success": False, "error": f"Opportunity {args['opportunity_id']} not found"}

    partner = opp.partner_id
    if not partner:
        # Create partner from lead if missing
        partner = env['res.partner'].create({
            'name': opp.contact_name or opp.partner_name or opp.name,
            'email': opp.email_from,
            'phone': opp.phone,
        })
        opp.partner_id = partner

    order_vals = {
        'partner_id': partner.id,
        'opportunity_id': opp.id,
        'company_id': env.company.id,
        'currency_id': env.company.currency_id.id,
    }
    order_vals = link_ai_context_vals(order_vals, context)

    # Prepare order lines
    lines_vals = []
    for l in args.get("order_lines", []):
        prod, disambig = find_or_disambiguate_product(env, str(l["product_name_or_id"]))
        if prod:
            lines_vals.append((0, 0, {
                'product_id': prod.id,
                'product_uom_qty': l.get('quantity', 1.0),
                'price_unit': l.get('price_unit', prod.list_price),
            }))

    if lines_vals:
        order_vals['order_line'] = lines_vals

    sale_order = env['sale.order'].create(order_vals)
    return {
        "success": True,
        "sale_order_id": sale_order.id,
        "sale_order_name": sale_order.name,
        "partner_name": partner.name,
        "opportunity_id": opp.id,
        "amount_total": sale_order.amount_total,
        "message": f"Draft Quotation {sale_order.name} created and linked to Opportunity '{opp.name}'.",
    }
