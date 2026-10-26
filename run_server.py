"""
Quantum Ising Optimizer Cloud Platform - Gateway Server Launcher
"""

import sys
import os
import uvicorn

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from server.config import SERVER_HOST, SERVER_PORT, CIM_HARDWARE_URL

def main():
    print("=" * 75)
    print("       QUANTUM ISING OPTIMIZER (CIM) CLOUD GATEWAY")
    print("=" * 75)
    print(f" * Target Hardware Bench:  {CIM_HARDWARE_URL}")
    print(f" * Local Gateway URL:      http://127.0.0.1:{SERVER_PORT}")
    print(f" * Interactive Web Portal: http://127.0.0.1:{SERVER_PORT}/")
    print(f" * OpenAPI Swagger Docs:   http://127.0.0.1:{SERVER_PORT}/docs")
    print(f" * Public WAN / Tunnel:    Expose via Cloudflare Tunnel or ngrok:")
    print(f"                           `cloudflared tunnel --url http://127.0.0.1:{SERVER_PORT}`")
    print("=" * 75)
    print(">>> Starting Uvicorn Event Loop...\n")

    uvicorn.run("server.main:app", host=SERVER_HOST, port=SERVER_PORT, reload=False, log_level="info")

if __name__ == "__main__":
    main()
