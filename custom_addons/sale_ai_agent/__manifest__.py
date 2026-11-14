{
    'name': "AI Operations Agent",
    'summary': "Autonomous Junior Odoo Implementer for Sales, Purchase, Inventory & Manufacturing",
    'description': """
Odoo 20 AI Operations Agent (sale_ai_agent):
=============================================
* Powered exclusively by Anthropic Claude via Messages API.
* Dynamic planning, task decomposition, and execution across Sales, Purchase, Inventory, and MRP.
* Global Decision 6 compliant: Human approval required for irreversible / financial (T2) operations.
* Zero plain-chat persistence; audit-logged tool execution.
* Real-time streaming and modern OWL interface with collapsible Capabilities panel.
    """,
    'author': "AI Agent Team",
    'category': 'Sales/Operations',
    'version': '20.0.1.1.0',
    'depends': [
        'sale_management',
        'purchase',
        'stock',
        'mrp',
        'crm',
        'mail',
        'bus',
        'web',
    ],
    'data': [
        'security/ir.access.csv',
        'views/res_config_settings_views.xml',
        'views/ai_agent_approval_views.xml',
        'views/ai_agent_log_views.xml',
        'views/sale_order_views.xml',
        'views/crm_lead_views.xml',
        'views/product_template_views.xml',
        'wizard/ai_sale_followup_wizard_views.xml',
        'wizard/ai_agent_chat_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sale_ai_agent/static/src/scss/ai_chat_minimize.scss',
            'sale_ai_agent/static/src/js/ai_chat_minimize.js',
            'sale_ai_agent/static/src/components/ai_chat_panel/ai_chat_panel.xml',
            'sale_ai_agent/static/src/components/ai_chat_panel/ai_chat_panel.js',
        ],
    },
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
