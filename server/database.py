"""
Quantum Ising Optimizer Cloud Platform - Persistence Layer
Dual Adapter: Supports Supabase Hosted PostgreSQL & Local SQLite
"""

import os
import time
import sqlite3
import logging
import threading
from contextlib import contextmanager
from server.config import DATABASE_URL, DB_PATH

logger = logging.getLogger("cim_cloud.database")

# Check if PostgreSQL is available
USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))

_pg_pool = None
_pool_lock = threading.Lock()

if USE_POSTGRES:
    try:
        import psycopg2
        import psycopg2.extras
        import psycopg2.pool
        logger.info("Initializing Supabase PostgreSQL database adapter with connection pooling...")
    except ImportError:
        logger.warning("psycopg2 not found, falling back to SQLite.")
        USE_POSTGRES = False

def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        with _pool_lock:
            if _pg_pool is None:
                logger.info("Spawning ThreadedConnectionPool (minconn=2, maxconn=25) for Supabase PostgreSQL...")
                _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=25,
                    dsn=DATABASE_URL,
                    connect_timeout=10
                )
    return _pg_pool

class PGConnWrapper:
    """Wraps psycopg2 connection to mimic sqlite3 row-dict execution."""
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if params is not None:
            # Convert SQLite '?' placeholder to PostgreSQL '%s'
            pg_sql = sql.replace("?", "%s")
            cur.execute(pg_sql, params)
        else:
            cur.execute(sql)
        return cur

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        pass # Managed by connection pool

@contextmanager
def get_db():
    if USE_POSTGRES:
        pool = get_pg_pool()
        conn = pool.getconn()
        try:
            if conn.closed != 0:
                pool.putconn(conn, close=True)
                conn = pool.getconn()
            wrapper = PGConnWrapper(conn)
            yield wrapper
            wrapper.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            raise e
        finally:
            try:
                pool.putconn(conn)
            except Exception:
                pass
    else:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
        conn.execute("PRAGMA journal_mode=DELETE;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=15000;")
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

def init_db():
    with get_db() as conn:
        # 1. Users Table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            organization TEXT,
            tier TEXT DEFAULT 'community',
            credits INTEGER DEFAULT 100,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """)
        
        # 2. API Keys Table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            secret_hash TEXT NOT NULL,
            user_id TEXT NOT NULL,
            label TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            last_used_at TEXT,
            created_at TEXT NOT NULL
        );
        """)
        
        # 3. Jobs Table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            label TEXT,
            problem_type TEXT NOT NULL,
            problem_data TEXT NOT NULL,
            num_variables INTEGER NOT NULL,
            shots INTEGER DEFAULT 20,
            priority INTEGER DEFAULT 3,
            status TEXT NOT NULL,
            queue_position INTEGER DEFAULT 0,
            result_spins TEXT,
            result_energy REAL,
            execution_time_ms REAL,
            hardware_mode TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT
        );
        """)
        
        # 4. Hardware Metrics Table
        if USE_POSTGRES:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS hardware_metrics (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                ping_latency_ms REAL,
                jobs_executed INTEGER,
                last_error TEXT
            );
            """)
        else:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS hardware_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                ping_latency_ms REAL,
                jobs_executed INTEGER,
                last_error TEXT
            );
            """)

        # 5. Platform Stats Table (Visitor Counter)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS platform_stats (
            stat_key TEXT PRIMARY KEY,
            stat_value INTEGER DEFAULT 0
        );
        """)

        logger.info(f"Database initialized successfully (Engine: {'Supabase PostgreSQL' if USE_POSTGRES else 'SQLite'}).")

_visitor_count_cache = None
_visitor_lock = threading.Lock()
_last_visitor_flush = 0.0

def get_and_increment_visitor_count() -> int:
    """Atomically increments and returns the platform visitor count with high-concurrency RAM buffer."""
    global _visitor_count_cache, _last_visitor_flush
    now = time.time()
    with _visitor_lock:
        if _visitor_count_cache is None:
            try:
                with get_db() as conn:
                    row = conn.execute("SELECT stat_value FROM platform_stats WHERE stat_key = ?", ("visitor_count",)).fetchone()
                    if not row:
                        _visitor_count_cache = 1042
                        conn.execute("INSERT INTO platform_stats (stat_key, stat_value) VALUES (?, ?)", ("visitor_count", 1042))
                    else:
                        _visitor_count_cache = row["stat_value"] if isinstance(row, dict) else row[0]
            except Exception as e:
                logger.error(f"Error initializing visitor count: {e}")
                _visitor_count_cache = 1042
            _last_visitor_flush = now

        _visitor_count_cache += 1
        current_count = _visitor_count_cache

        # Flush to DB at most once every 5 seconds to prevent connection saturation
        if now - _last_visitor_flush > 5.0:
            _last_visitor_flush = now
            try:
                with get_db() as conn:
                    conn.execute("UPDATE platform_stats SET stat_value = ? WHERE stat_key = ?", (current_count, "visitor_count"))
            except Exception as e:
                logger.warning(f"Deferred visitor count flush: {e}")

        return current_count

if __name__ == "__main__":
    init_db()
    print("Database initialization complete.")
