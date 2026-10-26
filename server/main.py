"""
Quantum Ising Optimizer Cloud Platform - FastAPI Application Gateway
"""

import os
import json
import secrets
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.config import SERVER_HOST, SERVER_PORT, DEFAULT_SIGNUP_CREDITS
from server.database import init_db, get_db
from server.auth import (
    hash_password, verify_password, create_jwt_token, 
    generate_api_key, get_current_user
)
from server.models import (
    UserSignupRequest, UserLoginRequest, TokenResponse, UserProfileResponse,
    ApiKeyCreateRequest, ApiKeyResponse, QuboJobSubmitRequest,
    JobStatusResponse, HardwareStatusResponse
)
from server.scheduler import scheduler

# Initialize FastAPI App
app = FastAPI(
    title="Quantum Ising Optimizer API",
    description="High-Throughput Remote Gateway & Job Scheduler for the Coherent Ising Machine (CIM)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable Full CORS for Public / Cross-Origin Remote Access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup & Shutdown Lifecycles
@app.on_event("startup")
def on_startup():
    init_db()
    scheduler.start()

@app.on_event("shutdown")
def on_shutdown():
    scheduler.stop()

# --------------------------------------------------------------------------
# Public Hardware Health & Status
# --------------------------------------------------------------------------
@app.get("/api/v1/hardware/status", response_model=HardwareStatusResponse, tags=["Hardware"])
def get_hardware_status():
    return scheduler.get_hardware_status()

# --------------------------------------------------------------------------
# Authentication Endpoints
# --------------------------------------------------------------------------
@app.post("/api/v1/auth/signup", tags=["Authentication"])
def signup(req: UserSignupRequest):
    email = req.email.lower().strip()
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="An account with this email already exists.")
        
        user_id = f"usr_{secrets.token_hex(8)}"
        hashed_pwd = hash_password(req.password)
        now = datetime.utcnow().isoformat()
        
        conn.execute("""
            INSERT INTO users (id, email, hashed_password, full_name, organization, tier, credits, created_at)
            VALUES (?, ?, ?, ?, ?, 'community', ?, ?)
        """, (user_id, email, hashed_pwd, req.full_name, req.organization, DEFAULT_SIGNUP_CREDITS, now))
        
    # Auto-generate a default API key and JWT token for instant access
    api_key_data = generate_api_key(user_id, label="Primary API Key (Auto-Generated)")
    token = create_jwt_token(user_id, email, "community")
    
    return {
        "message": "User registered successfully.",
        "user_id": user_id,
        "email": email,
        "full_name": req.full_name,
        "tier": "community",
        "credits": DEFAULT_SIGNUP_CREDITS,
        "access_token": token,
        "token_type": "bearer",
        "primary_api_key": api_key_data["api_key"]
    }

@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["Authentication"])
def login(req: UserLoginRequest):
    email = req.email.lower().strip()
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)).fetchone()
        if not user or not verify_password(user["hashed_password"], req.password):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        
        token = create_jwt_token(user["id"], user["email"], user["tier"])
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "tier": user["tier"],
            "credits": user["credits"]
        }

@app.get("/api/v1/auth/me", tags=["Authentication"])
def get_profile(current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        keys = conn.execute("""
            SELECT key_id, label, is_active, last_used_at, created_at
            FROM api_keys
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (current_user["id"],)).fetchall()
        
    return {
        "user": current_user,
        "api_keys": [dict(k) for k in keys]
    }

@app.post("/api/v1/auth/api-keys", response_model=ApiKeyResponse, tags=["Authentication"])
def create_api_key(req: ApiKeyCreateRequest, current_user: dict = Depends(get_current_user)):
    return generate_api_key(current_user["id"], req.label)

# --------------------------------------------------------------------------
# Job Submission & Management Endpoints
# --------------------------------------------------------------------------
@app.post("/api/v1/jobs/submit", response_model=JobStatusResponse, tags=["Jobs"])
def submit_job(req: QuboJobSubmitRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    
    # 1. Check user credit balance
    if current_user.get("credits", 0) <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient execution credits. Please contact admin to refill credits."
        )

    # 2. Package problem data
    problem_data = {}
    if req.qubo is not None:
        problem_data["qubo"] = req.qubo
    if req.linear is not None:
        problem_data["linear"] = req.linear
    if req.quadratic is not None:
        problem_data["quadratic"] = req.quadratic
    if req.edges is not None:
        problem_data["edges"] = req.edges
    if req.numbers is not None:
        problem_data["numbers"] = req.numbers

    if not problem_data:
        raise HTTPException(status_code=400, detail="Must provide optimization data (qubo, ising, edges, or numbers).")

    problem_data_json = json.dumps(problem_data)

    # 3. Pre-flight validate matrix with dimod
    try:
        _, num_vars = scheduler.compile_to_bqm(req.problem_type, problem_data_json)
    except Exception as parse_err:
        raise HTTPException(status_code=400, detail=f"Matrix validation failed: {str(parse_err)}")

    # 4. Determine priority by tier
    tier = current_user.get("tier", "community")
    priority_map = {"enterprise": 1, "research": 2, "community": 3}
    priority = priority_map.get(tier, 3)

    job_id = f"job_{secrets.token_hex(8)}"
    now = datetime.utcnow().isoformat()

    # 5. Insert Job and Debit 1 credit
    with get_db() as conn:
        conn.execute("UPDATE users SET credits = credits - 1 WHERE id = ?", (user_id,))
        conn.execute("""
            INSERT INTO jobs (
                job_id, user_id, label, problem_type, problem_data,
                num_variables, shots, priority, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'QUEUED', ?)
        """, (job_id, user_id, req.label, req.problem_type, problem_data_json,
              num_vars, req.shots, priority, now))

        # Calculate queue position
        q_row = conn.execute("""
            SELECT COUNT(*) as pos FROM jobs 
            WHERE status = 'QUEUED' AND (priority < ? OR (priority = ? AND created_at <= ?))
        """, (priority, priority, now)).fetchone()
        queue_pos = q_row["pos"] if q_row else 1

    return {
        "job_id": job_id,
        "user_id": user_id,
        "label": req.label,
        "problem_type": req.problem_type,
        "num_variables": num_vars,
        "shots": req.shots,
        "priority": priority,
        "status": "QUEUED",
        "queue_position": queue_pos,
        "created_at": now
    }

@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse, tags=["Jobs"])
def get_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found.")
        
        # User isolation
        if row["user_id"] != current_user["id"] and current_user.get("tier") != "admin":
            raise HTTPException(status_code=403, detail="Unauthorized access to this job.")

        job_dict = dict(row)
        
        # Calculate queue position if queued
        queue_pos = 0
        if job_dict["status"] == "QUEUED":
            q_row = conn.execute("""
                SELECT COUNT(*) as pos FROM jobs 
                WHERE status = 'QUEUED' AND (priority < ? OR (priority = ? AND created_at <= ?))
            """, (job_dict["priority"], job_dict["priority"], job_dict["created_at"])).fetchone()
            queue_pos = q_row["pos"] if q_row else 1

        spins = json.loads(job_dict["result_spins"]) if job_dict.get("result_spins") else None

        return {
            "job_id": job_dict["job_id"],
            "user_id": job_dict["user_id"],
            "label": job_dict["label"],
            "problem_type": job_dict["problem_type"],
            "num_variables": job_dict["num_variables"],
            "shots": job_dict["shots"],
            "priority": job_dict["priority"],
            "status": job_dict["status"],
            "queue_position": queue_pos,
            "result_spins": spins,
            "result_energy": job_dict["result_energy"],
            "execution_time_ms": job_dict["execution_time_ms"],
            "hardware_mode": job_dict["hardware_mode"],
            "error_message": job_dict["error_message"],
            "created_at": job_dict["created_at"],
            "started_at": job_dict["started_at"],
            "completed_at": job_dict["completed_at"]
        }

@app.get("/api/v1/jobs", tags=["Jobs"])
def list_jobs(limit: int = 50, current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT job_id, label, problem_type, num_variables, shots, status, 
                   result_energy, execution_time_ms, hardware_mode, created_at, completed_at
            FROM jobs
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (current_user["id"], limit)).fetchall()
        
    return {"jobs": [dict(r) for r in rows]}

@app.post("/api/v1/jobs/{job_id}/cancel", tags=["Jobs"])
def cancel_job(job_id: str, current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        row = conn.execute("SELECT user_id, status FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found.")
        if row["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Unauthorized.")
        if row["status"] != "QUEUED":
            raise HTTPException(status_code=400, detail=f"Cannot cancel job with status '{row['status']}'.")
            
        now = datetime.utcnow().isoformat()
        conn.execute("UPDATE jobs SET status = 'CANCELLED', completed_at = ? WHERE job_id = ?", (now, job_id))
        conn.execute("UPDATE users SET credits = credits + 1 WHERE id = ?", (current_user["id"],))
        
    return {"message": "Job cancelled successfully and credit refunded."}

# --------------------------------------------------------------------------
# Sample Benchmark Presets
# --------------------------------------------------------------------------
@app.get("/api/v1/presets", tags=["Benchmarks"])
def get_presets():
    return {
        "max_cut_petersen": {
            "name": "Petersen Graph (10 Nodes) Max-Cut",
            "problem_type": "MAX_CUT",
            "edges": [
                [0, 1], [1, 2], [2, 3], [3, 4], [4, 0],
                [0, 5], [1, 6], [2, 7], [3, 8], [4, 9],
                [5, 7], [7, 9], [9, 6], [6, 8], [8, 5]
            ]
        },
        "number_partition": {
            "name": "Subset Sum / Number Partitioning",
            "problem_type": "NUMBER_PARTITION",
            "numbers": [19, 17, 13, 9, 6]
        },
        "benti_neuromechanical_16": {
            "name": "Benti ARCAF 16-Channel Sensor Covariance Inversion",
            "problem_type": "QUBO",
            "qubo": {
                "0,0": -2.5, "1,1": 2.5, "2,2": -2.5, "3,3": 2.5,
                "0,1": 0.35, "1,2": -0.28, "2,3": 0.42, "0,3": -0.19,
                "4,4": -3.0, "5,5": 3.0, "4,5": 0.55
            }
        }
    }

PORTAL_DIR = os.path.join(os.path.dirname(__file__), "portal")
if os.path.exists(PORTAL_DIR):
    app.mount("/portal", StaticFiles(directory=PORTAL_DIR, html=True), name="portal")

@app.get("/style.css")
def serve_css():
    css_path = os.path.join(PORTAL_DIR, "style.css")
    if os.path.exists(css_path):
        return FileResponse(css_path, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS not found")

@app.get("/app.js")
def serve_js():
    js_path = os.path.join(PORTAL_DIR, "app.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JS not found")

@app.get("/")
def serve_portal_root():
    index_file = os.path.join(PORTAL_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"status": "Quantum Ising Optimizer Gateway is Online", "docs": "/docs", "portal": "/portal"}
