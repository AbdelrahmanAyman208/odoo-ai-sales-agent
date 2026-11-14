# -*- coding: utf-8 -*-
"""
Shared Product Disambiguation Service.
Resolves products/variants across inventory, sales, mrp, and purchase domains.

Complexity:
- Time: O(1) indexed barcode/default_code/name search.
- Space: O(K) where K is number of matched candidates (<= 5).
"""
import logging
from typing import Tuple, Optional, List, Dict, Any

_logger = logging.getLogger(__name__)


def find_or_disambiguate_product(env, query: str) -> Tuple[Optional[Any], Optional[List[Dict[str, Any]]]]:
    """
    Finds a product.product record with progressive matching:
    1. Exact barcode match
    2. Exact internal reference (default_code) match
    3. Exact name match
    4. Substring (ilike) on name or reference
    If multiple found, returns (None, candidates_list).
    If exactly one found, returns (product, None).
    If none found, returns (None, None).
    """
    clean_val = (query or '').strip()
    if not clean_val:
        return None, None

    Product = env['product.product']

    # 1. Barcode match
    products = Product.search([('barcode', '=', clean_val)])
    if len(products) == 1:
        return products[0], None
    elif len(products) > 1:
        return None, [{'id': p.id, 'name': p.display_name, 'default_code': p.default_code} for p in products[:5]]

    # 2. Internal reference (default_code) match
    products = Product.search([('default_code', '=ilike', clean_val)])
    if len(products) == 1:
        return products[0], None
    elif len(products) > 1:
        return None, [{'id': p.id, 'name': p.display_name, 'default_code': p.default_code} for p in products[:5]]

    # 3. Exact name match
    products = Product.search([('name', '=ilike', clean_val)])
    if len(products) == 1:
        return products[0], None
    elif len(products) > 1:
        return None, [{'id': p.id, 'name': p.display_name, 'default_code': p.default_code} for p in products[:5]]

    # 4. Substring match
    products = Product.search(['|', ('name', 'ilike', clean_val), ('default_code', 'ilike', clean_val)], limit=5)
    if len(products) == 1:
        return products[0], None
    elif len(products) > 1:
        return None, [{'id': p.id, 'name': p.display_name, 'default_code': p.default_code} for p in products]

    return None, None
