"""
Optiqon CIM Cloud Platform - Configuration
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Load .env manually if exists
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = val

# Hardware Configuration
CIM_HARDWARE_URL = os.getenv("CIM_HARDWARE_URL", "http://192.168.1.230:5050/run_ising")
CIM_TIMEOUT_SECONDS = float(os.getenv("CIM_TIMEOUT_SECONDS", "8.0"))

# Database & Storage
DATABASE_URL = os.getenv("DATABASE_URL", None)
DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "cim_cloud.db"))

# Supabase Metadata
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Security & Authentication
JWT_SECRET = os.getenv("JWT_SECRET", "optiqon-cim-cloud-secret-key-2026-production-token")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7 # 7 days validity

# Billing & Default Quotas
DEFAULT_SIGNUP_CREDITS = 100
MAX_VARIABLES_PER_JOB = 1024

# Server Host & Port
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
