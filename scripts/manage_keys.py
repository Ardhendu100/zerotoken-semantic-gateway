import secrets
import hashlib
import sqlite3
import sys

DB_PATH = "zerotoken_metrics.db"

def init_key_table():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tenant_keys (
                key_hash TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def generate_tenant_key(tenant_id: str) -> str:
    # Generate 32 bytes of secure randomness (prefixed for clarity)
    raw_key = f"zt_live_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    
    init_key_table()
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO tenant_keys (key_hash, tenant_id) VALUES (?, ?)",
            (key_hash, tenant_id)
        )
        conn.commit()
        
    print(f"\n✅ API Key created for tenant: '{tenant_id}'")
    print(f"🔑 Secret Key (COPY NOW, SHOWS ONCE): {raw_key}\n")
    return raw_key

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/manage_keys.py <tenant_id>")
    else:
        generate_tenant_key(sys.argv[1])