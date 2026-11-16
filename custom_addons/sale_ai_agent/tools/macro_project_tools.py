# -*- coding: utf-8 -*-
"""
Project Macro Tools (Addendum 4 & Phase 8).
Spec-First Macro Tool: `project_build_from_spec`
- Batched two-phase creation O(n)
- Critical path and scheduling via topological sort
- O(1) query health and portfolio reporting
"""
import logging
from datetime import date
from typing import Dict, Any, List, Tuple
from odoo import Command
from .base import agent_tool
from ..services.pipeline_engine import execute_pipeline
from ..services.scheduler_engine import schedule_project_tasks

_logger = logging.getLogger(__name__)


def _understand_project_spec(env, spec: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    assumptions = []
    resolved = dict(spec)

    if not resolved.get("name"):
        resolved["name"] = "New Business Project"
        assumptions.append("Project name defaulted to 'New Business Project'")

    # Resolve manager / assignees in bulk
    User = env['res.users']
    all_assignee_names = set()
    for t in resolved.get("tasks", []):
        if t.get("assignee"):
            all_assignee_names.add(t["assignee"])

    user_map = {}
    if all_assignee_names:
        users = User.search([('name', 'in', list(all_assignee_names))])
        user_map = {u.name: u.id for u in users}

    resolved["_user_map"] = user_map
    resolved["_estimated_record_count"] = len(resolved.get("tasks", [])) + len(resolved.get("stages", [])) + 1
    return resolved, assumptions


def _preflight_project(env, spec: Dict[str, Any]) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    errors = []
    fix_tasks = []
    if 'project.project' not in env:
        errors.append("Project module is not installed.")
        fix_tasks.append({"title": "Install 'project' module", "action": "install_module", "module": "project"})
    return len(errors) == 0, errors, fix_tasks


def _validate_project(env, spec: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []
    tasks = spec.get("tasks", [])
    if not tasks:
        errors.append("Project specification must contain at least one task.")

    # Schedule check & cycle detection
    schedule_res = schedule_project_tasks(tasks)
    if schedule_res.get("has_cycle"):
        errors.append(schedule_res.get("error"))

    spec["_schedule_res"] = schedule_res
    return len(errors) == 0, errors


def _execute_project_build(env, spec: Dict[str, Any]) -> Dict[str, Any]:
    Project = env['project.project']
    Task = env['project.task']
    Stage = env['project.task.type']

    # 1. Create project
    proj_vals = {
        'name': spec["name"],
        'company_id': env.company.id,
    }
    project = Project.create(proj_vals)

    # 2. Create / Link Stages
    stage_map = {}
    stage_names = spec.get("stages") or ["New", "In Progress", "Done"]
    for idx, s_name in enumerate(stage_names):
        stage = Stage.search([('name', '=', s_name)], limit=1)
        if not stage:
            stage = Stage.create({'name': s_name, 'sequence': (idx + 1) * 10})
        stage.write({'project_ids': [Command.link(project.id)]})
        stage_map[s_name] = stage.id

    # 3. Two-phase Task Creation
    # Phase A: Create all tasks in batch with temp keys
    tasks_spec = spec.get("tasks", [])
    schedule_map = spec.get("_schedule_res", {}).get("schedule", {})
    user_map = spec.get("_user_map", {})
    default_stage_id = stage_map.get(stage_names[0]) if stage_names else False

    task_vals_list = []
    key_to_index = {}

    for idx, t in enumerate(tasks_spec):
        key = t.get("key") or f"task_{idx+1}"
        sched = schedule_map.get(key, {})
        u_id = user_map.get(t.get("assignee"))

        vals = {
            'name': t.get("title") or t.get("name") or f"Task {idx+1}",
            'project_id': project.id,
            'allocated_hours': float(t.get("allocated_hours", 8.0)),
            'stage_id': stage_map.get(t.get("stage"), default_stage_id),
            'user_ids': [Command.link(u_id)] if u_id else False,
        }
        if sched.get("date_deadline"):
            vals['date_deadline'] = sched["date_deadline"]

        task_vals_list.append(vals)
        key_to_index[key] = idx

    created_tasks = Task.create(task_vals_list)
    key_to_task_id = {key: created_tasks[idx].id for key, idx in key_to_index.items()}

    # Phase B: Relational Linkage (Parent-Child and Task Dependencies) in one batched pass
    for key, idx in key_to_index.items():
        t_spec = tasks_spec[idx]
        task_rec = created_tasks[idx]
        parent_key = t_spec.get("parent_key")
        deps_keys = t_spec.get("depends_on_keys") or []

        write_vals = {}
        if parent_key and parent_key in key_to_task_id:
            write_vals['parent_id'] = key_to_task_id[parent_key]

        dep_ids = [key_to_task_id[dk] for dk in deps_keys if dk in key_to_task_id]
        if dep_ids and hasattr(task_rec, 'depend_on_ids'):
            write_vals['depend_on_ids'] = [Command.link(d_id) for d_id in dep_ids]

        if write_vals:
            task_rec.write(write_vals)

    return {
        "project_id": project.id,
        "project_name": project.name,
        "tasks_count": len(created_tasks),
        "stages_count": len(stage_names),
        "critical_path": spec.get("_schedule_res", {}).get("critical_path_keys", []),
        "finish_date": spec.get("_schedule_res", {}).get("project_finish_date"),
    }


def _verify_project(env, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    warnings = []
    Task = env['project.task']
    tasks = Task.search([('project_id', '=', data["project_id"])])
    if len(tasks) != data["tasks_count"]:
        warnings.append(f"Expected {data['tasks_count']} tasks, but found {len(tasks)} in database.")
    return len(warnings) == 0, warnings


@agent_tool(
    name="project_build_from_spec",
    domain="project",
    label="Build Complete Project from Macro Spec",
    description="Constructs projects, stages, milestones, and scheduled task WBS with critical path in one batched pipeline.",
    tier="T1",
    examples=["Build software delivery project with 6 phases and 45 tasks"],
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Project title"},
            "stages": {"type": "array", "items": {"type": "string"}, "description": "Ordered stage names"},
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Unique key (e.g. T1, T2)"},
                        "title": {"type": "string", "description": "Task description"},
                        "stage": {"type": "string", "description": "Assigned stage name"},
                        "allocated_hours": {"type": "number", "default": 8.0},
                        "assignee": {"type": "string", "description": "User name"},
                        "parent_key": {"type": "string", "description": "Parent task key if subtask"},
                        "depends_on_keys": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["key", "title"],
                },
            },
            "confirm_run": {"type": "boolean", "default": True},
        },
        "required": ["name", "tasks"],
    },
)
def project_build_from_spec(env, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    return execute_pipeline(
        env=env,
        tool_name="project_build_from_spec",
        spec=args,
        understand_fn=_understand_project_spec,
        preflight_fn=_preflight_project,
        validate_fn=_validate_project,
        execute_fn=_execute_project_build,
        verify_fn=_verify_project,
    )
