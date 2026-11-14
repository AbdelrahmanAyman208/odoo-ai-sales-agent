# -*- coding: utf-8 -*-
"""
Administration & System Tools for AI Operations Agent.
Implements:
1. install_or_activate_language: install/activate languages (e.g. Arabic, French, German, Spanish).
2. create_odoo_user: create new users with specific role permissions (Sales, Purchase, Inventory, Admin).
3. list_available_languages: check currently installed/available languages.

Time Complexity: O(1) dictionary lookups and ORM calls.
Space Complexity: O(1).
"""
import logging
from typing import Dict, Any, List
from odoo.exceptions import UserError, AccessError
from .base import agent_tool

_logger = logging.getLogger(__name__)

# Map common language names/aliases to Odoo language codes
LANG_CODE_MAP = {
    'arabic': 'ar_001',
    'arabic (eg)': 'ar_001',
    'ar': 'ar_001',
    'french': 'fr_FR',
    'fr': 'fr_FR',
    'spanish': 'es_ES',
    'es': 'es_ES',
    'german': 'de_DE',
    'de': 'de_DE',
    'italian': 'it_IT',
    'it': 'it_IT',
    'chinese': 'zh_CN',
    'zh': 'zh_CN',
    'russian': 'ru_RU',
    'ru': 'ru_RU',
    'portuguese': 'pt_PT',
    'pt': 'pt_PT',
    'turkish': 'tr_TR',
    'tr': 'tr_TR',
    'japanese': 'ja_JP',
    'ja': 'ja_JP',
    'english': 'en_US',
    'en': 'en_US',
}


@agent_tool(
    name="install_or_activate_language",
    domain="administration",
    label="Install or Activate Language",
    description="Installs or activates an Odoo system language (e.g. Arabic 'ar_001', French 'fr_FR', Spanish 'es_ES', German 'de_DE') and loads its translations.",
    tier="T1",
    examples=[
        "Add Arabic language to the system",
        "Install French language",
        "Enable Spanish for users"
    ],
    parameters={
        "type": "object",
        "properties": {
            "lang_name_or_code": {
                "type": "string",
                "description": "Language name (e.g. 'Arabic', 'French', 'Spanish', 'German') or ISO code (e.g. 'ar_001', 'fr_FR', 'es_ES')."
            },
            "overwrite": {
                "type": "boolean",
                "description": "Whether to overwrite existing terms with latest translations. Default True.",
                "default": True
            }
        },
        "required": ["lang_name_or_code"]
    }
)
def install_or_activate_language(env, lang_name_or_code: str, overwrite: bool = True) -> Dict[str, Any]:
    """
    Installs or activates a system language.
    Time: O(M) where M is installed modules updating terms.
    Space: O(1).
    """
    clean_input = (lang_name_or_code or '').strip().lower()
    code = LANG_CODE_MAP.get(clean_input, lang_name_or_code.strip())

    Lang = env['res.lang'].with_context(active_test=False)
    lang_record = Lang.search([('code', '=', code)], limit=1)
    if not lang_record:
        # Search by name match
        lang_record = Lang.search([('name', 'ilike', clean_input)], limit=1)

    if not lang_record:
        return {
            "success": False,
            "error": f"Language '{lang_name_or_code}' not found in Odoo system languages catalog."
        }

    if lang_record.active:
        return {
            "success": True,
            "already_active": True,
            "lang_code": lang_record.code,
            "lang_name": lang_record.name,
            "message": f"Language '{lang_record.name}' ({lang_record.code}) is already active in the system."
        }

    # Activate and load translations using base.language.install wizard
    try:
        wizard = env['base.language.install'].sudo().create({
            'lang_ids': [(6, 0, lang_record.ids)],
            'overwrite': overwrite,
        })
        wizard.lang_install()
        return {
            "success": True,
            "activated": True,
            "lang_code": lang_record.code,
            "lang_name": lang_record.name,
            "message": f"Successfully installed and activated language '{lang_record.name}' ({lang_record.code}). Users can now select it in their preferences."
        }
    except Exception as e:
        _logger.exception("Failed installing language %s: %s", lang_name_or_code, e)
        return {
            "success": False,
            "error": f"Failed activating language '{lang_record.name}': {str(e)}"
        }


@agent_tool(
    name="list_system_languages",
    domain="administration",
    label="List System Languages",
    description="Lists all currently active languages and available installed language packs.",
    tier="T0",
    examples=[
        "What languages are currently installed?",
        "Check active languages"
    ],
    parameters={
        "type": "object",
        "properties": {}
    }
)
def list_system_languages(env) -> Dict[str, Any]:
    """Lists active and inactive languages."""
    active_langs = env['res.lang'].search([])
    return {
        "success": True,
        "active_languages": [{"code": l.code, "name": l.name, "direction": l.direction} for l in active_langs],
        "count": len(active_langs)
    }


@agent_tool(
    name="create_odoo_user",
    domain="administration",
    label="Create Odoo User with Permissions",
    description="Creates a new user in Odoo with specified login, email, password, and access roles (e.g. 'sales_user', 'sales_manager', 'purchase_user', 'purchase_manager', 'inventory_user', 'inventory_manager', 'admin').",
    tier="T1",
    examples=[
        "Create user Sarah as Sales Representative with email sarah@company.com",
        "Add a purchase manager user John",
        "Create user Ahmed with inventory user rights"
    ],
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Full name of the user (e.g. 'Sarah Connor')."
            },
            "login": {
                "type": "string",
                "description": "User login identifier or email address (e.g. 'sarah@example.com')."
            },
            "email": {
                "type": "string",
                "description": "Email address of the user."
            },
            "password": {
                "type": "string",
                "description": "Initial password for the user. Defaults to login if omitted."
            },
            "lang": {
                "type": "string",
                "description": "Language code for the user preferences (e.g. 'en_US', 'ar_001', 'fr_FR'). Optional."
            },
            "roles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of role names: 'sales_user', 'sales_manager', 'purchase_user', 'purchase_manager', 'inventory_user', 'inventory_manager', 'admin'."
            }
        },
        "required": ["name", "login"]
    }
)
def create_odoo_user(
    env,
    name: str,
    login: str,
    email: str = None,
    password: str = None,
    lang: str = None,
    roles: List[str] = None
) -> Dict[str, Any]:
    """
    Creates an Odoo internal user and assigns appropriate groups.
    Time: O(1)
    Space: O(1)
    """
    clean_login = (login or '').strip().lower()
    clean_email = (email or clean_login).strip()
    clean_name = (name or '').strip()

    # Check for duplicate login
    existing = env['res.users'].sudo().search([('login', '=', clean_login)], limit=1)
    if existing:
        return {
            "success": False,
            "error": f"A user with login '{clean_login}' already exists (ID: {existing.id}, Name: {existing.name})."
        }

    # Build group IDs
    # Internal User is always required
    group_records = [env.ref('base.group_user')]

    role_mapping = {
        'sales_user': 'sales_team.group_sale_salesman',
        'sales_rep': 'sales_team.group_sale_salesman',
        'sales_all': 'sales_team.group_sale_salesman_all_leads',
        'sales_manager': 'sales_team.group_sale_manager',
        'purchase_user': 'purchase.group_purchase_user',
        'purchase_manager': 'purchase.group_purchase_manager',
        'inventory_user': 'stock.group_stock_user',
        'stock_user': 'stock.group_stock_user',
        'inventory_manager': 'stock.group_stock_manager',
        'stock_manager': 'stock.group_stock_manager',
        'admin': 'base.group_system',
        'administrator': 'base.group_system',
    }

    assigned_role_names = []
    if roles:
        for r in roles:
            r_clean = r.strip().lower()
            xml_id = role_mapping.get(r_clean)
            if xml_id:
                grp = env.ref(xml_id, raise_if_not_found=False)
                if grp:
                    group_records.append(grp)
                    assigned_role_names.append(grp.name)

    vals = {
        'name': clean_name,
        'login': clean_login,
        'email': clean_email,
        'password': password or clean_login,
        'group_ids': [(6, 0, [g.id for g in group_records])],
    }

    if lang:
        target_lang = LANG_CODE_MAP.get(lang.lower().strip(), lang.strip())
        installed_lang = env['res.lang'].search([('code', '=', target_lang)], limit=1)
        if installed_lang:
            vals['lang'] = target_lang

    try:
        new_user = env['res.users'].sudo().create(vals)
        return {
            "success": True,
            "user_id": new_user.id,
            "name": new_user.name,
            "login": new_user.login,
            "email": new_user.email,
            "roles": assigned_role_names,
            "message": f"Successfully created user '{new_user.name}' ({new_user.login}) with roles: {', '.join(assigned_role_names) if assigned_role_names else 'Internal User'}."
        }
    except Exception as e:
        _logger.exception("Failed creating user %s: %s", clean_login, e)
        return {
            "success": False,
            "error": f"Failed creating user '{clean_name}': {str(e)}"
        }

