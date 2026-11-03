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
    if os.path.exists(supervisor_script):
        try:
            p = subprocess.Popen(
                [sys.executable, supervisor_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f" * Edge Cloudflare Tunnel: CONNECTED (Supervisor PID: {p.pid})")
            print(f" * Public Worker Gateway:  {CLOUDFLARE_WORKER_URL}")
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
