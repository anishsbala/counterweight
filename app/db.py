import time
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

from app.config import (
    DATABASE_URL,
    DB_CONNECT_DELAY_SECONDS,
    DB_CONNECT_RETRIES,
    DB_POOL_MAX_SIZE,
    DB_POOL_MIN_SIZE,
    TESTING,
)

try:
    from psycopg2.extras import RealDictCursor
    from psycopg2.pool import ThreadedConnectionPool
except ModuleNotFoundError:  # pragma: no cover - only for test environments without postgres deps
    RealDictCursor = None
    ThreadedConnectionPool = None

_connection_pool = None
_pool_lock = Lock()


def get_connection_pool():
    global _connection_pool
    if ThreadedConnectionPool is None:
        raise RuntimeError("psycopg2 is not installed. Install requirements.txt before using the database.")
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = ThreadedConnectionPool(
                    DB_POOL_MIN_SIZE,
                    DB_POOL_MAX_SIZE,
                    dsn=DATABASE_URL,
                    cursor_factory=RealDictCursor,
                )
    return _connection_pool


@contextmanager
def get_db_connection():
    pool = get_connection_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn, close=bool(conn.closed))


@contextmanager
def get_cursor():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            yield cur


def wait_for_database() -> None:
    if TESTING:
        return
    last_error = None
    for _ in range(DB_CONNECT_RETRIES):
        try:
            with get_db_connection():
                return
        except Exception as exc:  # pragma: no cover - only used during container startup
            last_error = exc
            time.sleep(DB_CONNECT_DELAY_SECONDS)
    raise RuntimeError(f"Database never became ready: {last_error}")


def run_sql_file(path: Path) -> None:
    statement_text = path.read_text(encoding="utf-8")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(statement_text)


def fetch_all(query: str, params=None):
    with get_cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchall()


def fetch_one(query: str, params=None):
    with get_cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchone()


def execute(query: str, params=None) -> None:
    with get_cursor() as cur:
        cur.execute(query, params or ())
