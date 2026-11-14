# -*- coding: utf-8 -*-
"""
Matching utility re-exports for backward compatibility.
Now delegates directly to services/partner_resolver and services/product_resolver.
"""
from ..services.partner_resolver import find_or_disambiguate_partner
from ..services.product_resolver import find_or_disambiguate_product

__all__ = [
    'find_or_disambiguate_partner',
    'find_or_disambiguate_product',
]
