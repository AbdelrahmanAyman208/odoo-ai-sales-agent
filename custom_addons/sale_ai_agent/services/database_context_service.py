# -*- coding: utf-8 -*-
"""
Database & Task Context Memory Service.
Builds real-time compact snapshots of recent user tasks, active records,
and core operational metrics to inject into the LLM system prompt.

Complexity:
- Time: O(1) indexed reads with limit <= 5.
- Space: O(1) compact text summary (< 500 tokens).
"""
import logging
from typing import Dict, Any, Optional

_logger = logging.getLogger(__name__)


def build_live_database_context(env, active_model: Optional[str] = None, active_id: Optional[int] = None) -> str:
    """
    Constructs a compact context block describing:
    1. Active record being viewed by the user (if any).
    2. Recent AI tasks and use cases executed in the database.
    3. Core operational snapshot (open quotations, MOs, locations).
    """
    lines = ["=== LIVE DATABASE & ACTIVITY CONTEXT ==="]

    # 1. Active screen / viewed record context
    if active_model and active_id:
        try:
            if active_model in env:
                rec = env[active_model].browse(active_id)
                if rec.exists():
                    disp = rec.display_name or f"ID #{rec.id}"
                    lines.append(f"CURRENTLY VIEWING SCREEN: {active_model} #{active_id} ('{disp}')")
                    if active_model == 'sale.order':
                        lines.append(f"  Customer: {rec.partner_id.name}, State: {rec.state}, Total: {rec.amount_total}")
                    elif active_model == 'mrp.production':
                        lines.append(f"  Product: {rec.product_id.display_name}, Qty: {rec.product_qty}, State: {rec.state}")
                    elif active_model == 'project.project':
                        lines.append(f"  Project: {rec.name}, Tasks Count: {rec.task_count}")
                    elif active_model == 'project.task':
                        lines.append(f"  Task: {rec.name}, Project: {rec.project_id.name}, Stage: {rec.stage_id.name}")
        except Exception as e:
            _logger.debug("Failed reading active record context: %s", e)

    # 2. Recent AI Agent tasks & executions
    try:
        Task = env['ai.agent.task']
        recent_tasks = Task.search([], order='id desc', limit=6)
        if recent_tasks:
            lines.append("RECENTLY EXECUTED AGENT TASKS:")
            for t in recent_tasks:
                summary = (t.result_summary or t.state or "")[:80]
                lines.append(f"  - [{t.tool_name}] {t.title} -> {t.state} ({summary})")
    except Exception as e:
        _logger.debug("Failed reading recent tasks context: %s", e)

    # 3. Core Database Entities Snapshot
    try:
        # Warehouse locations
        locations = env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('location_id', '!=', False)
        ], limit=8)
        if locations:
            loc_str = ", ".join([l.complete_name for l in locations])
            lines.append(f"AVAILABLE INTERNAL LOCATIONS: {loc_str}")

        # Core metric counts
        so_count = env['sale.order'].search_count([('state', 'in', ['draft', 'sent'])])
        mo_count = env['mrp.production'].search_count([('state', 'in', ['draft', 'confirmed', 'progress'])])
        prod_count = env['product.product'].search_count([('active', '=', True)])
        lines.append(f"DATABASE METRICS: {prod_count} Products, {so_count} Draft Quotations, {mo_count} Active MOs")
    except Exception as e:
        _logger.debug("Failed building DB metrics snapshot: %s", e)

    lines.append("=========================================")
    return "\n".join(lines)
