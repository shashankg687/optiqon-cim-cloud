"""
Optiqon CIM Cloud Platform - Configuration
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Hardware Configuration
CIM_HARDWARE_URL = os.getenv("CIM_HARDWARE_URL", "http://192.168.1.230:5050/run_ising")
CIM_TIMEOUT_SECONDS = float(os.getenv("CIM_TIMEOUT_SECONDS", "8.0"))

# Database & Storage
DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "cim_cloud.db"))

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
