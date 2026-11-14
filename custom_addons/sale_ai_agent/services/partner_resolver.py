# -*- coding: utf-8 -*-
"""
Shared Partner Disambiguation Service.
Resolves contacts safely across all business domains.

Complexity:
- Time: O(1) indexed search (name / email / phone).
- Space: O(K) where K is number of matched candidates (<= 5).
"""
import logging
from typing import Tuple, Optional, List, Dict, Any

_logger = logging.getLogger(__name__)


def find_or_disambiguate_partner(env, name_or_email: str, is_vendor: bool = False) -> Tuple[Optional[Any], Optional[List[Dict[str, Any]]]]:
    """
    Finds a res.partner record with progressive matching:
    1. Exact match on email
    2. Exact match on name
    3. Case-insensitive substring match (ilike)
    If multiple found, returns (None, candidates_list).
    If exactly one found, returns (partner, None).
    If none found, returns (None, None).
    """
    clean_val = (name_or_email or '').strip()
    if not clean_val:
        return None, None

    Partner = env['res.partner']
    domain_filter = []
    if is_vendor:
        domain_filter.append(('supplier_rank', '>', 0))

    # 1. Exact email match
    if '@' in clean_val:
        partners = Partner.search([('email', '=ilike', clean_val)] + domain_filter)
        if len(partners) == 1:
            return partners[0], None
        elif len(partners) > 1:
            return None, [{'id': p.id, 'name': p.display_name, 'email': p.email} for p in partners[:5]]

    # 2. Exact name match
    partners = Partner.search([('name', '=ilike', clean_val)] + domain_filter)
    if len(partners) == 1:
        return partners[0], None
    elif len(partners) > 1:
        return None, [{'id': p.id, 'name': p.display_name, 'email': p.email} for p in partners[:5]]

    # 3. Substring match
    partners = Partner.search([('name', 'ilike', clean_val)] + domain_filter, limit=5)
    if len(partners) == 1:
        return partners[0], None
    elif len(partners) > 1:
        return None, [{'id': p.id, 'name': p.display_name, 'email': p.email} for p in partners]

    return None, None
