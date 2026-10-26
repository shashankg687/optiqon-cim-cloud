"""
Optiqon CIM Cloud Platform - Data Schemas & Validation Models
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Dict, List, Optional, Any, Union

# --- Authentication Models ---
class UserSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="User password (min 6 chars)")
    full_name: str = Field(..., min_length=2)
    organization: Optional[str] = "Independent Researcher"

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str
    tier: str
    credits: int

class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    organization: Optional[str]
    tier: str
    credits: int
    created_at: str

class ApiKeyCreateRequest(BaseModel):
    label: str = Field(default="Default API Key", min_length=1, max_length=50)

class ApiKeyResponse(BaseModel):
    key_id: str
    api_key: str
    label: str
    created_at: str

# --- Optimization & Job Models ---
class QuboJobSubmitRequest(BaseModel):
    label: Optional[str] = "CIM Optimization Job"
    problem_type: str = Field(default="QUBO", description="QUBO, ISING, MAX_CUT, or NUMBER_PARTITION")
    
    # Direct QUBO dictionary: {"0,0": -1.5, "0,1": 2.0} or {"(0, 0)": -1.5}
    qubo: Optional[Dict[str, float]] = None
    
    # Alternative Ising parameters
    linear: Optional[Dict[str, float]] = None
    quadratic: Optional[Dict[str, float]] = None
    
    # Alternative Graph adjacency for MAX_CUT: list of edges [[u, v, weight], ...]
    edges: Optional[List[List[Union[int, float]]]] = None
    
    # Alternative list of integers for NUMBER_PARTITION: [25, 35, 45, 20, 25]
    numbers: Optional[List[int]] = None
    
    shots: int = Field(default=20, ge=1, le=1000)

class JobStatusResponse(BaseModel):
    job_id: str
    user_id: str
    label: Optional[str]
    problem_type: str
    num_variables: int
    shots: int
    priority: int
    status: str
    queue_position: int
    result_spins: Optional[Dict[str, int]] = None
    result_energy: Optional[float] = None
    execution_time_ms: Optional[float] = None
    hardware_mode: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

class HardwareStatusResponse(BaseModel):
    status: str
    hardware_url: str
    hardware_online: bool
    ping_latency_ms: float
    active_queue_depth: int
    total_jobs_completed: int
    hardware_description: str = "Quanfluence Optiqon Coherent Ising Machine (OPO Pulsed Cavity)"
