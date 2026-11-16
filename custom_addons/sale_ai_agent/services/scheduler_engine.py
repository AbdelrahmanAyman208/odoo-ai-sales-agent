# -*- coding: utf-8 -*-
"""
Deterministic Project Scheduling Engine (Addendum 4 & Phase 8).
Calendar-aware, topological forward scheduling, critical path detection,
slack computation, and delay propagation replan.

Complexity:
- Time: O(V + E) where V is task count and E is dependency count.
- Space: O(V + E) graph structures.
"""
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Set, Tuple, Optional


def schedule_project_tasks(
    tasks: List[Dict[str, Any]],
    project_start_date: Optional[date] = None,
    hours_per_day: float = 8.0,
) -> Dict[str, Any]:
    """
    Computes earliest start, earliest finish, latest start, latest finish,
    slack, and critical path using topological sorting.

    Complexity: O(V + E)
    """
    if not project_start_date:
        project_start_date = date.today()

    task_map: Dict[str, Dict[str, Any]] = {t["key"]: t for t in tasks}
    in_degree: Dict[str, int] = {t["key"]: 0 for t in tasks}
    adj_list: Dict[str, List[str]] = {t["key"]: [] for t in tasks}

    for t in tasks:
        deps = t.get("depends_on_keys") or []
        for dep in deps:
            if dep in adj_list:
                adj_list[dep].append(t["key"])
                in_degree[t["key"]] += 1

    # Cycle detection via Kahn's algorithm
    queue = [k for k, d in in_degree.items() if d == 0]
    topological_order: List[str] = []

    while queue:
        curr = queue.pop(0)
        topological_order.append(curr)
        for neighbor in adj_list[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(topological_order) != len(tasks):
        return {
            "has_cycle": True,
            "error": "Cyclic task dependency detected in project specification.",
        }

    # Forward pass: Earliest Start (ES) and Earliest Finish (EF)
    es: Dict[str, date] = {}
    ef: Dict[str, date] = {}

    for k in topological_order:
        t = task_map[k]
        allocated = float(t.get("allocated_hours", 8.0))
        duration_days = max(1, int(round(allocated / hours_per_day)))

        deps = t.get("depends_on_keys") or []
        if not deps:
            earliest = project_start_date
        else:
            dep_finishes = [ef[d] for d in deps if d in ef]
            earliest = max(dep_finishes) if dep_finishes else project_start_date

        es[k] = earliest
        ef[k] = earliest + timedelta(days=duration_days)

    project_finish_date = max(ef.values()) if ef else project_start_date

    # Backward pass: Latest Start (LS) and Latest Finish (LF)
    lf: Dict[str, date] = {}
    ls: Dict[str, date] = {}

    for k in reversed(topological_order):
        t = task_map[k]
        allocated = float(t.get("allocated_hours", 8.0))
        duration_days = max(1, int(round(allocated / hours_per_day)))

        successors = adj_list[k]
        if not successors:
            latest = project_finish_date
        else:
            latest = min([ls[s] for s in successors if s in ls])

        lf[k] = latest
        ls[k] = latest - timedelta(days=duration_days)

    # Critical path & Slack
    critical_path: List[str] = []
    task_schedule: Dict[str, Dict[str, Any]] = {}

    for k in topological_order:
        slack_days = (ls[k] - es[k]).days
        is_critical = slack_days == 0
        if is_critical:
            critical_path.append(k)

        task_schedule[k] = {
            "key": k,
            "date_start": es[k].isoformat(),
            "date_deadline": ef[k].isoformat(),
            "slack_days": slack_days,
            "is_critical": is_critical,
        }

    return {
        "has_cycle": False,
        "project_start_date": project_start_date.isoformat(),
        "project_finish_date": project_finish_date.isoformat(),
        "total_duration_days": (project_finish_date - project_start_date).days,
        "critical_path_keys": critical_path,
        "schedule": task_schedule,
    }
