"""Checkpoint storage for LangGraph runs.

With DATABASE_URL set, runs are stored in Postgres (Neon) so a pause for clarification or
technician review survives restarts and redeploys. Without it, an in-memory store is used
(local development and tests)."""
from langgraph.checkpoint.memory import MemorySaver

from . import config


def make_checkpointer():
    """Returns (checkpointer, pool). `pool` is None for the in-memory store."""
    if not config.DATABASE_URL:
        return MemorySaver(), None
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        conninfo=config.DATABASE_URL, min_size=1, max_size=5, timeout=30, open=True,
        check=ConnectionPool.check_connection,  # drop connections Neon closed while scaled to zero
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    saver = PostgresSaver(pool)
    saver.setup()  # creates the checkpoint tables on first run; safe to repeat
    return saver, pool
