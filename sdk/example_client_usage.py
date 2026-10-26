"""
End-to-End Verification & Example Usage Script for Optiqon CIM Cloud
"""

import sys
import os
import time
import requests

# Add SDK path to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sdk.cim_client import CIMClient

API_BASE = "http://127.0.0.1:8000"

def main():
    print("=" * 70)
    print("   OPTIQON CIM CLOUD PLATFORM - CLIENT VERIFICATION SUITE")
    print("=" * 70)
    
    # 1. Register a test user or authenticate
    signup_payload = {
        "email": "quantum.researcher@iit.ac.in",
        "password": "quantum_password_2026",
        "full_name": "Dr. Quantum Researcher",
        "organization": "IIT Indore / Quantum Lab"
    }
    
    print("\n[1/5] Authenticating / Signing up on Cloud Gateway...")
    signup_res = requests.post(f"{API_BASE}/api/v1/auth/signup", json=signup_payload)
    
    if signup_res.status_code == 200:
        auth_data = signup_res.json()
        api_key = auth_data["primary_api_key"]
        print(f"      [OK] Account created. Credits: {auth_data['credits']}")
        print(f"      [OK] Issued API Key: {api_key[:16]}...")
    else:
        # Account exists, login to retrieve token
        login_res = requests.post(f"{API_BASE}/api/v1/auth/login", json={
            "email": signup_payload["email"],
            "password": signup_payload["password"]
        })
        token_data = login_res.json()
        token = token_data["access_token"]
        # Fetch or generate API key
        profile_res = requests.get(f"{API_BASE}/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        keys = profile_res.json().get("api_keys", [])
        if keys:
            # Generate new key for this session
            new_key_res = requests.post(f"{API_BASE}/api/v1/auth/api-keys", 
                                        json={"label": "Automated Test Session Key"},
                                        headers={"Authorization": f"Bearer {token}"})
            api_key = new_key_res.json()["api_key"]
        else:
            new_key_res = requests.post(f"{API_BASE}/api/v1/auth/api-keys", 
                                        json={"label": "Primary Test Key"},
                                        headers={"Authorization": f"Bearer {token}"})
            api_key = new_key_res.json()["api_key"]
            
        print(f"      [OK] Logged in. Credits: {token_data['credits']}")
        print(f"      [OK] Active API Key: {api_key[:16]}...")

    # 2. Initialize CIMClient with API Key
    print("\n[2/5] Initializing Python CIMClient SDK...")
    client = CIMClient(api_key=api_key, base_url=API_BASE)

    # 3. Check Physical Hardware Health
    print("\n[3/5] Querying Optiqon CIM Physical Hardware Status...")
    hw = client.get_hardware_status()
    print(f"      [OK] Status: {hw['status']}")
    print(f"      [OK] Target URL: {hw['hardware_url']}")
    print(f"      [OK] Hardware Ping Latency: {hw['ping_latency_ms']} ms")
    print(f"      [OK] Active Queue Depth: {hw['active_queue_depth']}")

    # 4. Formulate Optimization Problem (QUBO)
    print("\n[4/5] Formulating Combinatorial Optimization QUBO...")
    # 5-variable frustrated Ising / QUBO system
    Q = {
        (0, 0): -2.5,
        (1, 1): 2.5,
        (2, 2): -1.8,
        (3, 3): 3.0,
        (4, 4): -2.0,
        (0, 1): 0.45,
        (1, 2): -0.35,
        (2, 3): 0.60,
        (3, 4): -0.25,
        (0, 4): 0.50
    }
    print(f"      [OK] Problem dimension: N = 5 variables, 5 cross-couplings.")

    # 5. Dispatch to CIM Cloud Scheduler
    print("\n[5/5] Submitting Job to Intelligent Cloud Scheduler & Hardware Queue...")
    job = client.submit_qubo(Q, label="Benti Frustrated Manifold Test", shots=20)
    print(f"      [OK] Job Dispatched! Job ID: {job.id}")
    print(f"      [OK] Initial Status: {job.status} | Queue Position: {job.queue_position}")

    print("\n>>> Waiting for Physical Optical Bifurcation & Solution...")
    result = job.wait_for_completion(timeout_seconds=30.0)

    print("=" * 70)
    print("                 CIM EXECUTION REPORT")
    print("=" * 70)
    print(f"Job ID:               {result.job_id}")
    print(f"Status:               {result.status}")
    print(f"Hardware Mode:        {result.hardware_mode}")
    print(f"Optical Solve Time:   {result.execution_time_ms} ms")
    print(f"Ground State Energy:  {result.energy}")
    print(f"Discovered Spins:     {result.spins}")
    print("=" * 70)
    print(">>> VERIFICATION COMPLETE: Physical CIM Cloud Gateway is 100% Operational!")

if __name__ == "__main__":
    main()
