"""
Optiqon CIM Cloud Platform - SQLite Persistence Layer (WAL Mode)
"""

import sqlite3
import json
import logging
from datetime import datetime
from contextlib import contextmanager
from server.config import DB_PATH

logger = logging.getLogger("cim_cloud.database")

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
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
        cursor = conn.cursor()
        
        # 1. Users Table
        cursor.execute("""
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            secret_hash TEXT NOT NULL,
            user_id TEXT NOT NULL,
            label TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            last_used_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        
        # 3. Jobs Table
        cursor.execute("""
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
            completed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        
        # 4. Hardware Metrics Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS hardware_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            ping_latency_ms REAL,
            jobs_executed INTEGER,
            last_error TEXT
        );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON jobs (status, priority, created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys (secret_hash);")
        
        logger.info("Optiqon CIM Cloud database schema initialized successfully.")

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
