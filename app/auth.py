import hashlib
import sqlite3
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()
DB_PATH = "zerotoken_metrics.db"

def get_tenant_id_from_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    raw_key = credentials.credentials
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tenant_id FROM tenant_keys WHERE key_hash = ?", (key_hash,))
        result = cursor.fetchone()
        
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Tenant API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return result[0]  # Returns tenant_id (e.g. 'tenant_acme')