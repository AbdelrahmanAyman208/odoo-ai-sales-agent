{
    'name': "AI Agent",
    'summary': "Intelligent AI Operations Agent for Sales, CRM, Purchase & Inventory Replenishment (Quotes, RFQs, Offer Analysis & Assemblies)",
    'description': """
AI Agent for Odoo 20:
====================
* Interactive AI Agent chat assistant for Sales, Purchase, CRM, and Inventory.
* Sales Quotes & Follow-up emails for Leads and Opportunities.
* Automated Inventory Replenishment Order technique for low-stock items.
* Purchase Orders & RFQ broadcasting to all suppliers.
* Supplier Offer Analysis form to identify lowest prices and highest savings.
* Composite/Assembly Product creation with Bill of Materials and automatic costing.
* Audit logging and action history tracking user and execution time.
    """,
    'author': "AI Agent Team",
    'category': 'Sales/Purchase/CRM',
    'version': '1.2',
    'depends': [
        'sale_management',
        'purchase',
        'stock',
        'crm',
        'mail',
    ],
    'data': [
        'security/ir.access.csv',
        'views/res_config_settings_views.xml',
        'wizard/ai_sale_followup_wizard_views.xml',
        'wizard/ai_agent_chat_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/crm_lead_views.xml',
        'views/product_template_views.xml',
        'views/ai_agent_log_views.xml',
        'views/menu_views.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
