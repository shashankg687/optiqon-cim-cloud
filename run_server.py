"""
Quantum Ising Optimizer Cloud Platform - Gateway Server Launcher
"""

import sys
import os
import subprocess
import uvicorn

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from server.config import SERVER_HOST, SERVER_PORT, CIM_HARDWARE_URL, CLOUDFLARE_WORKER_URL, CLOUDFLARE_TUNNEL_TOKEN

def start_tunnel_background():
    """Starts the Cloudflare tunnel supervisor in a background process."""
    supervisor_script = os.path.join(os.path.dirname(__file__), "scripts", "tunnel_supervisor.py")
    log_file = os.path.join(os.path.dirname(__file__), "data", "tunnel_supervisor.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    if os.path.exists(supervisor_script):
        try:
            log_fp = open(log_file, "a", encoding="utf-8")
            p = subprocess.Popen(
                [sys.executable, supervisor_script],
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(__file__),
                env=os.environ.copy()
            )
            print(f" * Edge Cloudflare Tunnel: LAUNCHED (Supervisor PID: {p.pid})")
            print(f" * Public Worker Gateway:  {CLOUDFLARE_WORKER_URL}")
            print(f" * Tunnel Log Output:     {log_file}")
            return p
        except Exception as e:
            print(f" * Edge Cloudflare Tunnel: Auto-start failed ({e})")
    return None

def main():
    print("=" * 75)
    print("       QUANTUM ISING OPTIMIZER (CIM) CLOUD GATEWAY")
    print("=" * 75)
    print(f" * Target Hardware Bench:  {CIM_HARDWARE_URL}")
    print(f" * Local Gateway URL:      http://127.0.0.1:{SERVER_PORT}")
    print(f" * Interactive Web Portal: http://127.0.0.1:{SERVER_PORT}/")
    print(f" * OpenAPI Swagger Docs:   http://127.0.0.1:{SERVER_PORT}/docs")
    tunnel_proc = start_tunnel_background()
    print("=" * 75)
    print(">>> Starting Uvicorn Event Loop...\n")

    try:
        uvicorn.run("server.main:app", host=SERVER_HOST, port=SERVER_PORT, reload=False, log_level="info")
    finally:
        if tunnel_proc:
            try:
                tunnel_proc.terminate()
            except Exception:
                pass

if __name__ == "__main__":
    main()
