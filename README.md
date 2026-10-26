# Optiqon CIM Cloud Platform (Q-CIM Cloud)

> **High-Throughput Public Cloud Gateway & Job Scheduler for the Optiqon Coherent Ising Machine**  
> **Physical Hardware Interface:** `http://192.168.1.230:5050/run_ising`  
> **Lead Architect:** Dr. Shashank Gupta, Ph.D.  

---

## 1. Overview

The **Optiqon CIM Cloud Platform** provides authenticated, multi-tenant remote access to the physical **Quanfluence Optiqon Coherent Ising Machine (CIM)**. Researchers, developers, and enterprise security auditors can register, receive free compute credits, obtain persistent API keys, and dispatch combinatorial optimization (QUBO, Ising, Max-Cut, and Number Partitioning) workloads from any machine, Google Colab, or automated script globally.

### Key Capabilities
* **Full Multi-Tenancy:** User registration (`/api/v1/auth/signup`), JWT authentication, and secure `cim_live_...` API keys.
* **Intelligent Job Scheduler:** Asynchronous, prioritized queue with physical hardware Mutex locking to prevent optical cavity race conditions.
* **Dual Execution Modes:**
  * **`OPTICAL_HARDWARE`:** Live physical OPO laser cavity execution at `192.168.1.230:5050/run_ising` (~65–80 ms solve time).
  * **`CALIBRATED_FALLBACK`:** Seamless Simulated Annealing digital twin if the physical laser bench undergoes maintenance.
* **Stunning Web Dashboard:** Live optical telemetry, interactive QUBO builder, real-time queue tracker, and spin configuration viewer.
* **Python SDK (`cim_cloud`):** Clean, Pythonic client library for programmatic execution in Jupyter Notebooks and Google Colab.

---

## 2. Directory Structure

```
d:\My Drive\Benti_sys\cim_cloud_platform\
├── CIM_CLOUD_PDA.md               # Product Design & Architecture (PDA) Specification
├── README.md                      # Platform Documentation & Guide
├── run_server.py                  # Standalone Gateway Server Launcher
├── server/
│   ├── main.py                    # FastAPI Application & REST Endpoints
│   ├── config.py                  # Hardware URL, JWT Secret, and Quotas
│   ├── database.py                # SQLite Persistence Layer (WAL Mode)
│   ├── auth.py                    # PBKDF2 Password Hashing & API Key Engine
│   ├── models.py                  # Pydantic Schemas for QUBO/Ising & Responses
│   ├── scheduler.py               # Job Scheduler & Hardware Mutex Worker
│   └── portal/                    # Responsive Dark-Mode Glassmorphic Dashboard
│       ├── index.html
│       ├── style.css
│       └── app.js
└── sdk/
    ├── cim_client.py              # Official Python Client SDK
    └── example_client_usage.py    # Automated End-to-End Verification Test
```

---

## 3. Quickstart: Running the Cloud Server

### Step 1: Start the Gateway Server
```powershell
cd "d:\My Drive\Benti_sys\cim_cloud_platform"
python run_server.py
```
* **Interactive Web Portal:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* **OpenAPI Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Step 2: Expose Publicly (For Global Access)
To make your local CIM accessible from Google Colab or anywhere on the internet:
```bash
# Using free Cloudflare Tunnel (no port forwarding required)
cloudflared tunnel --url http://127.0.0.1:8000

# Or using ngrok:
ngrok http 8000
```

---

## 4. Python SDK Usage

```python
from sdk.cim_client import CIMClient

# 1. Initialize client with your API key
client = CIMClient(api_key="cim_live_...", base_url="http://127.0.0.1:8000")

# 2. Check physical optical hardware status
hw = client.get_hardware_status()
print("Optiqon CIM Status:", hw["status"], f"({hw['ping_latency_ms']} ms)")

# 3. Formulate optimization problem
Q = {
    (0, 0): -2.5, (1, 1): 2.5, (2, 2): -1.8,
    (0, 1): 0.45, (1, 2): -0.35
}

# 4. Dispatch job to cloud scheduler
job = client.submit_qubo(Q, label="Sample Max-Cut Run", shots=20)
print(f"Submitted Job: {job.id} | Initial State: {job.status}")

# 5. Wait for optical solution
result = job.wait_for_completion()
print(f"Solve Latency: {result.execution_time_ms} ms")
print(f"Ground State Energy: {result.energy}")
print(f"Optimal Spin Configuration: {result.spins}")
```

---

## 5. End-to-End Automated Verification Test

Run the included verification script:
```powershell
python sdk/example_client_usage.py
```
This script signs up a user, generates an API key, checks physical hardware health, dispatches a 5-variable QUBO problem to the scheduler, executes on `192.168.1.230:5050/run_ising`, and reports the ground state energy.
