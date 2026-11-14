# -*- coding: utf-8 -*-
"""
Shared Document Linker Service (Global Decision 8).
Attaches AI use case and subtask traceability metadata to newly created or updated Odoo records.

Complexity:
- Time: O(1) in-memory dictionary update or direct write.
- Space: O(1).
"""
from typing import Dict, Any, Optional


def link_ai_context_vals(vals: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Injects ai_use_case_id and ai_task_id into create values if present in the execution context.
    """
    if not context:
        return vals

    use_case_id = context.get('use_case_id')
    task_id = context.get('task_id')

    if use_case_id and 'ai_use_case_id' not in vals:
        vals['ai_use_case_id'] = use_case_id
    if task_id and 'ai_task_id' not in vals:
        vals['ai_task_id'] = task_id

    return vals


def link_record_to_ai_context(record, context: Optional[Dict[str, Any]]):
    """
    Writes ai_use_case_id and ai_task_id to an existing record if present in context.
    """
    if not context or not record:
        return

    vals = {}
    if context.get('use_case_id') and hasattr(record, 'ai_use_case_id') and not record.ai_use_case_id:
        vals['ai_use_case_id'] = context['use_case_id']
    if context.get('task_id') and hasattr(record, 'ai_task_id') and not record.ai_task_id:
        vals['ai_task_id'] = context['task_id']

    if vals:
        record.sudo().write(vals)
