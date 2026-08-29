import sqlite3
import time
import asyncio
from typing import Optional, Dict, Any, List

DB_PATH = "zerotoken_metrics.db"

def init_db():
    """Initialize the SQLite database schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            tenant_id TEXT NOT NULL,
            cache_status TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            similarity_score REAL DEFAULT 0.0,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            cost_saved_usd REAL DEFAULT 0.0
        )
    """)
    conn.commit()
    conn.close()


def log_request_sync(
    tenant_id: str,
    cache_status: str,
    latency_ms: float,
    similarity_score: float = 0.0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_saved_usd: float = 0.0
):
    """Synchronous worker for database inserts."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO request_logs 
            (tenant_id, cache_status, latency_ms, similarity_score, prompt_tokens, completion_tokens, cost_saved_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tenant_id, cache_status, latency_ms, similarity_score, prompt_tokens, completion_tokens, cost_saved_usd))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Metrics DB Logging Error: {e}")


async def log_metrics_async(
    tenant_id: str,
    cache_status: str,
    latency_ms: float,
    similarity_score: float = 0.0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_saved_usd: float = 0.0
):
    """Asynchronous wrapper to log metrics in a background thread."""
    await asyncio.to_thread(
        log_request_sync,
        tenant_id,
        cache_status,
        latency_ms,
        similarity_score,
        prompt_tokens,
        completion_tokens,
        cost_saved_usd
    )