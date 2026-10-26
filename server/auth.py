"""
Quantum Ising Optimizer Cloud Platform - Authentication & Authorization Engine
"""

import os
import secrets
import hashlib
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from server.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS, DEFAULT_SIGNUP_CREDITS
from server.database import get_db

security_bearer = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-CIM-API-Key", auto_error=False)

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
    return f"{salt.hex()}:{key.hex()}"

def verify_password(stored_password: str, provided_password: str) -> bool:
    try:
        salt_hex, key_hex = stored_password.split(":")
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100_000)
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False

def create_jwt_token(user_id: str, email: str, tier: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "tier": tier,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

def generate_api_key(user_id: str, label: str) -> Dict[str, str]:
    raw_key = f"cim_live_{secrets.token_hex(24)}"
    secret_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
    key_id = f"key_{secrets.token_hex(8)}"
    now = datetime.utcnow().isoformat()
    
    with get_db() as conn:
        conn.execute("""
            INSERT INTO api_keys (key_id, secret_hash, user_id, label, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (key_id, secret_hash, user_id, label, now))
        
    return {
        "key_id": key_id,
        "api_key": raw_key,
        "label": label,
        "created_at": now
    }

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    api_key: Optional[str] = Security(api_key_header)
) -> Dict[str, Any]:
    # 1. Try API Key
    if api_key:
        secret_hash = hashlib.sha256(api_key.strip().encode('utf-8')).hexdigest()
        with get_db() as conn:
            row = conn.execute("""
                SELECT u.id, u.email, u.full_name, u.organization, u.tier, u.credits, u.is_active, k.key_id
                FROM api_keys k
                JOIN users u ON k.user_id = u.id
                WHERE k.secret_hash = ? AND k.is_active = 1 AND u.is_active = 1
            """, (secret_hash,)).fetchone()
            
            if row:
                conn.execute("UPDATE api_keys SET last_used_at = ? WHERE key_id = ?", 
                             (datetime.utcnow().isoformat(), row["key_id"]))
                return dict(row)
                
    # 2. Try Bearer JWT Token
    if credentials:
        payload = decode_jwt_token(credentials.credentials)
        if payload:
            user_id = payload.get("sub")
            with get_db() as conn:
                row = conn.execute("""
                    SELECT id, email, full_name, organization, tier, credits, is_active
                    FROM users
                    WHERE id = ? AND is_active = 1
                """, (user_id,)).fetchone()
                if row:
                    return dict(row)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials (Provide 'Authorization: Bearer <token>' or 'X-CIM-API-Key').",
        headers={"WWW-Authenticate": "Bearer"}
    )
