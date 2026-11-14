# -*- coding: utf-8 -*-
"""
Project & Task Management Domain Tools (Phase 11, Global Decision 8).
Features:
- Project creation, configuration, stages.
- Task management: create, assign, deadline, subtasks, sale order linking.
- Project health & deadline monitor via _read_group.
- Onboarding / standard project templates.

Complexity:
- Time: O(1) project/task operations; O(T) health monitor where T is tasks count.
- Space: O(K) where K is number of returned task summaries.
"""
from datetime import datetime, date
import logging
from typing import Any, Dict, List, Optional
from ..tools.base import agent_tool
from ..services.partner_resolver import find_or_disambiguate_partner
from ..services.document_linker import link_ai_context_vals, link_record_to_ai_context

_logger = logging.getLogger(__name__)


@agent_tool(
    name="manage_projects",
    domain="project",
    label="Create or Update Project",
    description="Creates or modifies projects, assigns project managers, sets partners, and tracks project lifecycle.",
    tier="T1",
    available_if=["project"],
    examples=["Create project 'ERP Implementation' for ACME", "Update project 5 status"],
    parameters={
        "type": "object",
        "properties": {
            "project_id": {"type": "integer", "description": "Existing project ID if updating"},
            "name": {"type": "string", "description": "Project Name"},
            "partner_name_or_email": {"type": "string", "description": "Customer/Partner name"},
            "date_start": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
            "date": {"type": "string", "description": "End / Deadline date (YYYY-MM-DD)"},
        },
    },
)
def manage_projects(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    Project = env['project.project']
    project_id = args.get("project_id")

    vals = {}
    if args.get("name"):
        vals['name'] = args["name"].strip()
    if args.get("date_start"):
        vals['date_start'] = args["date_start"]
    if args.get("date"):
        vals['date'] = args["date"]

    partner_query = args.get("partner_name_or_email")
    if partner_query:
        partner, candidates = find_or_disambiguate_partner(env, partner_query)
        if candidates:
            return {"success": False, "disambiguation_required": True, "candidates": candidates}
        if partner:
            vals['partner_id'] = partner.id

    if project_id:
        proj = Project.browse(project_id)
        if not proj.exists():
            return {"success": False, "error": f"Project {project_id} not found"}
        proj.write(vals)
        action_type = "updated"
    else:
        if not vals.get('name'):
            vals['name'] = "New AI Project"
        proj = Project.create(vals)
        action_type = "created"

    return {
        "success": True,
        "project_id": proj.id,
        "name": proj.name,
        "partner_name": proj.partner_id.name if proj.partner_id else None,
        "action": action_type,
        "message": f"Project '{proj.name}' successfully {action_type} (ID: {proj.id}).",
    }


@agent_tool(
    name="manage_project_tasks",
    domain="project",
    label="Create or Update Project Task",
    description="Creates or updates tasks within projects, assigns team members, sets deadlines, and links to sale orders.",
    tier="T1",
    available_if=["project"],
    examples=["Create task 'Database Migration' in project 4", "Assign task 12 deadline to 2026-12-01"],
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "integer", "description": "Existing task ID if updating"},
            "project_id": {"type": "integer", "description": "Target Project ID"},
            "name": {"type": "string", "description": "Task Name"},
            "date_deadline": {"type": "string", "description": "Deadline (YYYY-MM-DD)"},
            "parent_id": {"type": "integer", "description": "Parent task ID for subtasks"},
            "sale_order_id": {"type": "integer", "description": "Optional linked Sale Order ID"},
        },
    },
)
def manage_project_tasks(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    Task = env['project.task']
    task_id = args.get("task_id")

    vals = {}
    for fld in ['name', 'project_id', 'date_deadline', 'parent_id', 'sale_order_id']:
        if fld in args and args[fld] is not None:
            vals[fld] = args[fld]

    if task_id:
        task = Task.browse(task_id)
        if not task.exists():
            return {"success": False, "error": f"Task {task_id} not found"}
        task.write(vals)
        action_type = "updated"
    else:
        if not vals.get('name'):
            vals['name'] = "New Task"
        if not vals.get('project_id'):
            return {"success": False, "error": "Creating a task requires 'project_id'."}
        task = Task.create(vals)
        action_type = "created"

    return {
        "success": True,
        "task_id": task.id,
        "name": task.name,
        "project_name": task.project_id.name,
        "deadline": str(task.date_deadline) if task.date_deadline else None,
        "action": action_type,
        "message": f"Task '{task.name}' successfully {action_type} in project '{task.project_id.name}'.",
    }


@agent_tool(
    name="check_project_health_and_deadlines",
    domain="project",
    label="Project Health & Overdue Deadlines Monitor",
    description="Scans project tasks for overdue deadlines, upcoming milestones, and overall health status.",
    tier="T0",
    available_if=["project"],
    examples=["Check project health", "List overdue tasks in project 3"],
    parameters={
        "type": "object",
        "properties": {
            "project_id": {"type": "integer", "description": "Optional specific project ID to inspect"},
        },
    },
)
def check_project_health_and_deadlines(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    Task = env['project.task']
    today = date.today().isoformat()

    domain = [('is_closed', '=', False)]
    if args.get("project_id"):
        domain.append(('project_id', '=', args["project_id"]))

    total_open_tasks = Task.search_count(domain)

    # Overdue tasks
    overdue_domain = domain + [('date_deadline', '<', today)]
    overdue_tasks = Task.search_read(
        overdue_domain,
        ['id', 'name', 'project_id', 'date_deadline'],
        limit=10,
        order='date_deadline asc'
    )

    return {
        "success": True,
        "open_tasks_count": total_open_tasks,
        "overdue_count": len(overdue_tasks),
        "overdue_tasks": [
            {
                "id": t['id'],
                "name": t['name'],
                "project": t['project_id'][1] if t['project_id'] else None,
                "deadline": str(t['date_deadline']),
            }
            for t in overdue_tasks
        ],
        "health_status": "Attention Needed" if overdue_tasks else "Healthy",
    }
