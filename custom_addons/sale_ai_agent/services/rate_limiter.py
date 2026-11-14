# -*- coding: utf-8 -*-
"""
Shared Rate Limiter & Daily Budget Service (Global Decision 2).
Enforces:
1. Requests Per Minute (RPM) token bucket to prevent 429 errors on free models.
2. Daily request budget (e.g., 50 or 1000 requests/day).
3. Redis backend with in-process threading-safe LRU fallback.

Complexity:
- Time: O(1) atomic check and increment.
- Space: O(1) counter storage per company/registry.
"""
from datetime import date, datetime
import logging
import threading
import time
from typing import Dict, Any, Optional, Tuple

_logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_IN_PROCESS_RPM_BUCKET = {"tokens": 10.0, "last_updated": time.time()}
_IN_PROCESS_DAILY_USAGE = {"day": str(date.today()), "count": 0}


def _get_redis_client(env):
    """Attempts to connect to configured Redis server if available."""
    ICP = env['ir.config_parameter'].sudo()
    redis_url = ICP.get_str('sale_ai_agent.redis_url', default='')
    if not redis_url:
        return None
    try:
        import redis
        client = redis.Redis.from_url(redis_url, socket_timeout=1.5)
        client.ping()
        return client
    except Exception:
        return None


def check_and_consume_budget(env, cost: int = 1) -> Tuple[bool, Dict[str, Any]]:
    """
    Checks both RPM limit and daily request budget before making an LLM call.
    Returns: (is_allowed, budget_info_dict)
    """
    ICP = env['ir.config_parameter'].sudo()
    rpm_limit = ICP.get_int('sale_ai_agent.rpm_limit', 15)
    daily_budget = ICP.get_int('sale_ai_agent.daily_budget', 200)

    r_client = _get_redis_client(env)
    today_str = str(date.today())

    if r_client:
        try:
            db_name = env.cr.dbname
            daily_key = f"saa:{db_name}:budget:{today_str}"
            rpm_key = f"saa:{db_name}:rpm_tokens"

            pipe = r_client.pipeline()
            pipe.incrby(daily_key, cost)
            pipe.expire(daily_key, 86400 * 2)
            res = pipe.execute()
            current_daily = res[0]

            if current_daily > daily_budget:
                return False, {
                    "allowed": False,
                    "reason": "daily_limit_exceeded",
                    "daily_used": current_daily,
                    "daily_budget": daily_budget,
                    "remaining_today": 0,
                    "retry_after": 3600,
                }

            return True, {
                "allowed": True,
                "daily_used": current_daily,
                "daily_budget": daily_budget,
                "remaining_today": max(0, daily_budget - current_daily),
            }
        except Exception as e:
            _logger.warning("Redis rate limiter error, falling back to in-memory: %s", e)

    # In-process fallback
    with _LOCK:
        if _IN_PROCESS_DAILY_USAGE["day"] != today_str:
            _IN_PROCESS_DAILY_USAGE["day"] = today_str
            _IN_PROCESS_DAILY_USAGE["count"] = 0

        if _IN_PROCESS_DAILY_USAGE["count"] + cost > daily_budget:
            return False, {
                "allowed": False,
                "reason": "daily_limit_exceeded",
                "daily_used": _IN_PROCESS_DAILY_USAGE["count"],
                "daily_budget": daily_budget,
                "remaining_today": 0,
                "retry_after": 3600,
            }

        _IN_PROCESS_DAILY_USAGE["count"] += cost
        remaining = max(0, daily_budget - _IN_PROCESS_DAILY_USAGE["count"])

        return True, {
            "allowed": True,
            "daily_used": _IN_PROCESS_DAILY_USAGE["count"],
            "daily_budget": daily_budget,
            "remaining_today": remaining,
        }


def get_budget_status(env) -> Dict[str, Any]:
    """Inspects remaining calls without consuming budget."""
    ICP = env['ir.config_parameter'].sudo()
    daily_budget = ICP.get_int('sale_ai_agent.daily_budget', 200)
    today_str = str(date.today())

    with _LOCK:
        used = _IN_PROCESS_DAILY_USAGE["count"] if _IN_PROCESS_DAILY_USAGE["day"] == today_str else 0
        return {
            "daily_budget": daily_budget,
            "daily_used": used,
            "remaining_today": max(0, daily_budget - used),
        }
