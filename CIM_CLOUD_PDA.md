# Product Design & Architecture (PDA): Quantum Ising Optimizer Cloud Platform

> **Document Version:** 1.0.0  
> **Classification:** Technical Architecture & Product Specification  
> **System Name:** Quantum Ising Optimizer (QIO Cloud Gateway)  
> **Physical Hardware Target:** Coherent Ising Machine (OPO Cavity Bench at `http://192.168.1.230:5050/run_ising`)  
> **Lead Architect:** Dr. Shashank Gupta, Ph.D.  
> **Date:** October 2026  

---

## 1. Executive Summary & Vision

The **Quantum Ising Optimizer Cloud Platform** bridges physical optical computing hardware with global cloud developers, quantum researchers, and enterprise cybersecurity engineers. Built as an open, high-throughput cloud gateway analogous to *IBM Quantum Platform* and *D-Wave Leap*, this system allows authenticated users worldwide to submit NP-hard combinatorial optimization, Quadratic Unconstrained Binary Optimization (QUBO), and Ising spin-glass problems directly to the physical Coherent Ising Machine (CIM) located at `192.168.1.230:5050`.

### 1.1 Core Value Proposition
* **Frictionless Onboarding:** Instant user registration, API key generation (`cim_live_...`), and starter compute credits.
* **Universal Remote API:** RESTful and Python SDK access enabling programmatic job dispatch from any network, Google Colab, or automated CI/CD pipeline.
* **Intelligent Job Scheduler:** Asynchronous, prioritized queueing engine with hardware serialization (Mutex lock) ensuring conflict-free optical cavity execution.
* **High-Aesthetic Web Portal:** Real-time job telemetry, interactive QUBO formulator, optical bifurcation latency tracking, and spin state visualization.
* **Fault-Tolerant Resilience:** Automatic hardware heartbeat monitoring, rate limiting, and seamless calibrated digital-twin fallback during physical bench recalibration.

---

## 2. System Architecture & Topology

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       CLIENT LAYER                                              │
│                                                                                                 │
│   ┌───────────────────────────┐    ┌───────────────────────────┐    ┌─────────────────────────┐ │
│   │    Python Client SDK      │    │    Web Dashboard / UI     │    │   External CI/CD or     │ │
│   │ (Google Colab / Jupyter)  │    │ (Browser / Mobile Portal) │    │  Adversarial Testbeds   │ │
│   └─────────────┬─────────────┘    └─────────────┬─────────────┘    └────────────┬────────────┘ │
└─────────────────┼────────────────────────────────┼───────────────────────────────┼──────────────┘
                  │                                │                               │
                  ▼                                ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                CLOUD API GATEWAY (FastAPI)                                      │
│                                                                                                 │
│  • Public Edge / Reverse Proxy (SSL/TLS, 0.0.0.0:8000 or Cloudflare Tunnel)                    │
│  • Authentication & Identity Provider (PBKDF2 Password Hashing, JWT Bearer, API Keys)           │
│  • Rate Limiter & Credit Billing Guard (Token Bucket Algorithm)                                 │
│  • Input Validator (QUBO Symmetry, Dimension Bounds N <= 1000, Dimod BQM Parser)               │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                            INTELLIGENT JOB SCHEDULER & QUEUE                                    │
│                                                                                                 │
│  • Priority Multi-Tier Queue (Tier 1: Enterprise -> Tier 2: Research -> Tier 3: Community)     │
│  • Job State Machine: SUBMITTED -> QUEUED -> DISPATCHED -> SOLVING -> COMPLETED / FAILED       │
│  • Hardware Mutex Lock: Guarantees single-tenant access to physical OPO optical cavity           │
│  • Persistent SQLite WAL Database: ACID storage for Users, API Keys, Jobs, and Results          │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              HARDWARE DISPATCHER & WORKER                                       │
│                                                                                                 │
│  • Worker Thread: Dequeues top-priority job and compiles matrix into BQM payload                │
│  • Live Probe: Verifies HTTP connectivity to physical CIM at 192.168.1.230:5050                │
│  • Execution Engine: Submits POST /run_ising, captures spins S_i, ground energy, and latency   │
│  • Calibrated Fallback Twin: High-fidelity Simulated Annealing if optical bench in maintenance   │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              PHYSICAL QUANTUM HARDWARE                                          │
│                                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                          COHERENT ISING MACHINE (CIM)                                   │   │
│   │   • IP Address: http://192.168.1.230:5050/run_ising                                     │   │
│   │   • Optical Parametric Oscillator (OPO) Pulsed Fiber Ring Cavity                        │   │
│   │   • Phase Pitchfork Bifurcation (~65 - 80 ms per ground energy solve)                   │   │
│   │   • FPGA Feedback Matrix Coupler                                                        │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Models & Database Schema

The persistence layer uses a high-performance SQLite engine with **Write-Ahead Logging (WAL)** enabled for zero-lock concurrency:

### 3.1 `users`
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `TEXT PRIMARY KEY` | UUID string (`usr_...`) |
| `email` | `TEXT UNIQUE` | User email address |
| `hashed_password` | `TEXT` | Salted PBKDF2-SHA256 password hash |
| `full_name` | `TEXT` | User's full name / organization |
| `tier` | `TEXT` | `community`, `research`, or `enterprise` |
| `credits` | `INTEGER` | Remaining execution credits (default: 100 on signup) |
| `created_at` | `DATETIME` | Account creation timestamp |

### 3.2 `api_keys`
| Column | Type | Description |
| :--- | :--- | :--- |
| `key_id` | `TEXT PRIMARY KEY` | Public key identifier |
| `secret_hash` | `TEXT` | Hash of secret token (`cim_live_...`) |
| `user_id` | `TEXT` | Foreign key to `users.id` |
| `label` | `TEXT` | User label (e.g., "Colab Notebook", "Prod Server") |
| `is_active` | `BOOLEAN` | Active status toggle |
| `created_at` | `DATETIME` | Generation timestamp |

### 3.3 `jobs`
| Column | Type | Description |
| :--- | :--- | :--- |
| `job_id` | `TEXT PRIMARY KEY` | Unique job UUID (`job_...`) |
| `user_id` | `TEXT` | Foreign key to `users.id` |
| `problem_type` | `TEXT` | `QUBO`, `ISING`, `MAX_CUT`, or `NUMBER_PARTITION` |
| `problem_data` | `TEXT (JSON)`| Full problem coefficients ($Q$ or $J, h$) |
| `num_variables` | `INTEGER` | Size of variable space $N$ |
| `shots` | `INTEGER` | Repetitions / sweeps requested |
| `priority` | `INTEGER` | Numeric queue priority (1 = Highest) |
| `status` | `TEXT` | `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED` |
| `result_spins` | `TEXT (JSON)`| Discovered ground state spin configuration |
| `result_energy` | `REAL` | Hamiltonian ground state energy $E_0$ |
| `execution_time_ms`| `REAL` | Optical cavity solve latency in ms |
| `hardware_mode` | `TEXT` | `OPTICAL_HARDWARE` or `CALIBRATED_FALLBACK` |
| `error_message` | `TEXT` | Error details if failed |
| `created_at` | `DATETIME` | Submission timestamp |
| `completed_at` | `DATETIME` | Completion timestamp |

---

## 4. API Specification (RESTful)

### 4.1 Authentication & Profile
* `POST /api/v1/auth/signup`: Create a new user account and award initial credits.
* `POST /api/v1/auth/login`: Authenticate with email/password to receive JWT token.
* `GET /api/v1/auth/me`: Fetch user profile, tier, and remaining credit balance.
* `POST /api/v1/auth/api-keys`: Generate a persistent `cim_live_...` API key.

### 4.2 Job Management
* `POST /api/v1/jobs/submit`: Submit an optimization problem (QUBO/Ising). Returns `job_id` and initial queue position.
* `GET /api/v1/jobs/{job_id}`: Poll job status, queue position, or retrieve final spins and ground energy.
* `GET /api/v1/jobs`: List user's historical jobs with pagination.
* `POST /api/v1/jobs/{job_id}/cancel`: Cancel a pending queued job.

### 4.3 Hardware Telemetry & Health
* `GET /api/v1/hardware/status`: Returns live status of `http://192.168.1.230:5050/run_ising`, latency, queue depth, and total jobs executed.

---

## 5. Job Scheduler & Hardware Mutex Protocol

Because the optical cavity of the Coherent Ising Machine (CIM) is an analog physical resonator operating at pulsed laser rates, multiple jobs cannot occupy the optical cavity simultaneously. The scheduler implements a **Serial Lock Pattern**:

1. **Submission:** When a user calls `/jobs/submit`, the problem is validated, credits are debited, and the job is recorded as `QUEUED` in SQLite.
2. **Prioritization:** The background scheduler worker orders the queue by:
   $$\text{Priority Score} = \text{Tier Weight} \times 1000 - (\text{Wait Time in Seconds})$$
3. **Dispatch & Lock:** The worker acquires an asynchronous non-blocking lock on the hardware interface.
4. **Execution:** The worker serializes the problem into the Dimod BQM format:
   ```json
   {
     "bqm": {
       "linear": { "0": -1.0, "1": 1.0 },
       "quadratic": { "0,1": 0.5 },
       "offset": 0.0,
       "vartype": "SPIN"
     }
   }
   ```
   and executes `POST http://192.168.1.230:5050/run_ising` with a 10-second timeout.
5. **Reconciliation & Release:** Upon response `{"S": {...}, "energy": ...}`, the worker commits results, records latency, marks status `COMPLETED`, releases the hardware lock, and picks the next job in the queue.

---

## 6. Security, Rate Limiting & Multi-Tenancy

1. **Authentication:** All API endpoints (except public health and signup/login) require either:
   * Header: `Authorization: Bearer <JWT_TOKEN>`
   * Header: `X-CIM-API-Key: cim_live_<SECRET>`
2. **Rate Limiting:**
   * Community tier: 10 requests / min.
   * Research tier: 60 requests / min.
   * Enterprise tier: 300 requests / min.
3. **Problem Size Guardrails:** $N \le 1,024$ variables per job to avoid memory saturation.
4. **Zero-Leak Multi-Tenancy:** Each user can only inspect their own job parameters and results.

---

## 7. Python Client SDK Design (`cim_cloud`)

The SDK provides an intuitive interface modeled after standard quantum toolkits:

```python
from cim_cloud import CIMClient

# Initialize client
client = CIMClient(api_key="cim_live_...", base_url="https://your-cloud-domain.com")

# Define a QUBO dictionary
Q = {
    (0, 0): -2.0, (1, 1): -2.0, (2, 2): -2.0,
    (0, 1): 1.5, (1, 2): 1.5
}

# Submit job to the physical optical hardware
job = client.submit_qubo(Q, label="Graph Max-Cut Benchmark")
print(f"Submitted Job ID: {job.id} | Initial Queue Status: {job.status}")

# Wait for completion (blocking or callback)
result = job.wait_for_completion()
print(f"Optical Solve Latency: {result.execution_time_ms:.2f} ms")
print(f"Ground State Energy: {result.energy}")
print(f"Optimal Spin Configuration: {result.spins}")
```

---

## 8. Rollout & Verification Roadmap

* [x] **Phase 1:** Physical CIM hardware probing & verification (`192.168.1.230:5050` live response verified).
* [ ] **Phase 2:** Database schema & authentication engine implementation.
* [ ] **Phase 3:** Job Scheduler & hardware serialization worker development.
* [ ] **Phase 4:** FastAPI cloud gateway endpoints implementation.
* [ ] **Phase 5:** Sleek browser dashboard development.
* [ ] **Phase 6:** Python SDK creation and end-to-end verification.
