# -*- coding: utf-8 -*-
"""
Intent Router & Dynamic Playbook Injector (Global Decisions 7 & 8).
Inspects prompt keywords to select domain: sales, purchase, inventory, mrp, crm, project, loyalty, quality, administration, multi.
Injects ONLY the relevant playbook into prompt cache to minimize token overhead.

Time Complexity: O(W) where W is number of words in query.
Space Complexity: O(P) where P is playbook size (~1-2KB).
"""
import os
import re
from typing import List, Optional, Tuple

_PLAYBOOK_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge")
_PLAYBOOK_CACHE = {}


def route_intent(prompt: str) -> str:
    """
    Categorizes user query into a domain:
    - sales
    - purchase
    - inventory
    - mrp
    - crm
    - project
    - loyalty
    - quality
    - administration
    - multi
    """
    p = prompt.lower()

    # Check for multi-module end-to-end indicators
    multi_keywords = (
        "end to end", "end-to-end", "use case", "usecase", "complete scenario",
        "full flow", "full workflow", "workflow", "sales + purchase", "purchase + sales"
    )
    if any(k in p for k in multi_keywords):
        return "multi"

    # Count domain keyword matches to detect multi-domain workflows
    domain_hits = 0
    if any(k in p for k in ("quotation", "quote", "discount", "customer", "sale order")):
        domain_hits += 1
    if any(k in p for k in ("supplier", "vendor", "rfq", "purchase order")):
        domain_hits += 1
    if any(k in p for k in ("bom", "bill of material", "manufactur", "produce", "production")):
        domain_hits += 1
    if any(k in p for k in ("replenish", "stock transfer", "picking", "warehouse")):
        domain_hits += 1
    if any(k in p for k in ("project", "task", "milestone")):
        domain_hits += 1
    if any(k in p for k in ("coupon", "loyalty", "promo")):
        domain_hits += 1

    if domain_hits >= 2:
        return "multi"

    if any(k in p for k in ("language", "lang", "arabic", "french", "spanish", "user", "create user", "role", "permission")):
        return "administration"
    elif any(k in p for k in ("quality", "inspection", "tolerance", "check type", "qc")):
        return "quality"
    elif any(k in p for k in ("project", "task", "deadline", "milestone", "overdue")):
        return "project"
    elif any(k in p for k in ("coupon", "loyalty", "promo", "pricelist", "reward", "card")):
        return "loyalty"
    elif any(k in p for k in ("bom", "bill of material", "manufactur", "produce", "production", "assembly", "mto", "work center")):
        return "mrp"
    elif any(k in p for k in ("supplier", "vendor", "rfq", "purchase", "buy", "cheapest", "lead time")):
        return "purchase"
    elif any(k in p for k in ("stock", "inventory", "on hand", "forecast", "replenish", "warehouse", "picking", "transfer", "location")):
        return "inventory"
    elif any(k in p for k in ("lead", "pipeline", "opportunity", "crm", "stage", "deals")):
        return "crm"
    else:
        return "sales"


def get_playbook_for_domain(domain: str) -> str:
    """Loads and caches the markdown playbook for a specific domain."""
    global _PLAYBOOK_CACHE
    if domain in _PLAYBOOK_CACHE:
        return _PLAYBOOK_CACHE[domain]

    path = os.path.join(_PLAYBOOK_DIR, f"{domain}.md")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                _PLAYBOOK_CACHE[domain] = content
                return content
        except Exception:
            pass

    return ""


def build_system_prompt_with_grounding(base_prompt: str, user_prompt: str) -> Tuple[str, str]:
    """
    Determines domain, loads targeted playbook, and returns combined system prompt.
    Returns: (final_system_prompt, domain)
    """
    domain = route_intent(user_prompt)
    playbook = get_playbook_for_domain(domain)

    tone_guidelines = (
        "\n\nTONE & INTERACTION RULES:\n"
        "- Be warm, professional, and concise. Never dump raw JSON or verbose explanations.\n"
        "- Respond in the same language as the user (English or Arabic).\n"
        "- If details are missing, ask at most ONE clarifying question and make sensible business assumptions.\n"
        "- Always state clearly which records were created or modified with their IDs/names."
    )

    if playbook:
        final_prompt = (
            f"{base_prompt}\n{tone_guidelines}\n\n"
            f"--- DOMAIN KNOWLEDGE PLAYBOOK ({domain.upper()}) ---\n"
            f"{playbook}\n"
            f"----------------------------------------------------"
        )
    else:
        final_prompt = f"{base_prompt}\n{tone_guidelines}"

    return final_prompt, domain
