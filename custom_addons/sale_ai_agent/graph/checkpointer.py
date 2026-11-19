# -*- coding: utf-8 -*-
"""
Postgres Checkpointer Connection Provider for LangGraph (G12).
Uses a dedicated schema `saa_langgraph` and independent connection pool
completely isolated from Odoo's internal cursors.
"""
import logging
from typing import Optional
import psycopg
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

_logger = logging.getLogger(__name__)

_GLOBAL_POOL: Optional[ConnectionPool] = None
_CHECKPOINT_SCHEMA = "saa_langgraph"
_SCHEMA_INITIALIZED = False


def get_db_uri(env) -> str:
    """Builds connection URI from Odoo environment config."""
    db_name = env.cr.dbname
    import odoo.tools.config as config
    user = config.get('db_user') or 'odoo'
    password = config.get('db_password') or 'odoo'
    host = config.get('db_host') or 'localhost'
    port = config.get('db_port') or 5432
    
    if not host or host.startswith('/'):
        host = 'localhost'
    return f"dbname={db_name} user={user} password={password} host={host} port={port}"


def init_checkpointer_schema(env):
    """Idempotently initializes schema and tables with autocommit."""
    global _SCHEMA_INITIALIZED
    if _SCHEMA_INITIALIZED:
        return
    db_uri = get_db_uri(env)
    try:
        with psycopg.connect(db_uri, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {_CHECKPOINT_SCHEMA};")
                cur.execute(f"SET search_path TO {_CHECKPOINT_SCHEMA}, public;")
                # Fast existence check: If checkpoints table exists, DO NOT run saver.setup()
                # because saver.setup() uses CREATE INDEX CONCURRENTLY which deadlocks on any open transaction!
                cur.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = 'checkpoints';",
                    (_CHECKPOINT_SCHEMA,)
                )
                if cur.fetchone():
                    _SCHEMA_INITIALIZED = True
                    return
            saver = PostgresSaver(conn)
            saver.setup()
            _SCHEMA_INITIALIZED = True
        _logger.info("LangGraph postgres checkpointer schema '%s' initialized.", _CHECKPOINT_SCHEMA)
    except Exception as e:
        _logger.warning("Could not auto-initialize LangGraph postgres schema: %s", e)


def get_checkpoint_pool(env) -> ConnectionPool:
    """Returns singleton connection pool scoped to dedicated schema."""
    global _GLOBAL_POOL
    if _GLOBAL_POOL is None or _GLOBAL_POOL.closed:
        db_uri = get_db_uri(env)
        _GLOBAL_POOL = ConnectionPool(
            db_uri,
            min_size=1,
            max_size=5,
            kwargs={"options": f"-c search_path={_CHECKPOINT_SCHEMA}"}
        )
    return _GLOBAL_POOL
