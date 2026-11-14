# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Post-migration script for sale_ai_agent 20.0.1.1.0.
    Ensures indexes and clean setup for AI use case and task references.
    """
    _logger.info("Executing post-migration for sale_ai_agent to %s", version)
    # Check if tables exist and create index on ai_use_case_id if missing
    for table in ['sale_order', 'purchase_order', 'stock_picking', 'mrp_production', 'crm_lead']:
        cr.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name = 'ai_use_case_id'
        """, (table,))
        if cr.fetchone():
            cr.execute(f"""
                CREATE INDEX IF NOT EXISTS {table}_ai_use_case_id_idx 
                ON {table} (ai_use_case_id);
            """)
