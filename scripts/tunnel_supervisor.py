"""
Cloudflare Tunnel & Worker Edge Auto-Supervisor for Quantum Ising Optimizer
Maintains active Cloudflare tunnel to local port 8000 and automatically keeps
Cloudflare Worker (quantum-ising-optimizer) synchronized with the live origin.
"""

import os
import sys
import time
import re
import subprocess
import urllib.request
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tunnel_supervisor")

# Load .env if present
env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(env_file):
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "a8b4615741899637a8281b36013b167f")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_TUNNEL_TOKEN = os.getenv("CLOUDFLARE_TUNNEL_TOKEN", "")
WORKER_NAME = os.getenv("CLOUDFLARE_WORKER_NAME", "quantum-ising-optimizer")
CLOUDFLARED_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cloudflared.exe")


# Import Edge Worker Compiler
try:
    from scripts.build_edge_worker import deploy_worker
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.build_edge_worker import deploy_worker


def update_worker_script(target_url: str):
    """Updates Cloudflare Worker with embedded UI + live tunnel API proxy."""
    logger.info(f"Deploying edge-native worker synchronized with origin: {target_url}")
    return deploy_worker(target_url)

def run_tunnel():
    """Runs cloudflared tunnel, captures live URL via logfile, updates Cloudflare Worker, and monitors health."""
    cloudflared_log = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cloudflared.log")
    os.makedirs(os.path.dirname(cloudflared_log), exist_ok=True)
    
    # Track offset to ignore old log entries from previous runs
    start_offset = os.path.getsize(cloudflared_log) if os.path.exists(cloudflared_log) else 0

    cmd = [CLOUDFLARED_PATH, "tunnel", "--url", "http://127.0.0.1:8000", "--logfile", cloudflared_log]
    logger.info(f"Starting cloudflared with logfile: {cloudflared_log} (offset: {start_offset})")
    
    proc = subprocess.Popen(cmd)
    
    tunnel_url = None
    start_time = time.time()
    
    # Poll log file for trycloudflare URL (up to 30 seconds)
    for _ in range(60):
        time.sleep(0.5)
        if proc.poll() is not None:
            logger.error(f"cloudflared exited unexpectedly with code {proc.returncode}")
            break
        if os.path.exists(cloudflared_log):
            try:
                with open(cloudflared_log, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(start_offset)
                    content = f.read()
                    matches = re.findall(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", content)
                    if matches:
                        tunnel_url = matches[-1]
                        logger.info(f"==> NEW TUNNEL DISCOVERED: {tunnel_url} <==")
                        success = update_worker_script(tunnel_url)
                        if success:
                            logger.info(f"==> GATEWAY READY: https://{WORKER_NAME}.shashankg554.workers.dev <==")
                        break
            except Exception:
                pass

    if not tunnel_url:
        logger.warning("Could not extract tunnel URL within timeout")

    # Monitor process health
    while True:
        time.sleep(2)
        if proc.poll() is not None:
            logger.warning("cloudflared stopped, will restart...")
            break
        # Re-cycle tunnel every 20 hours to prevent Cloudflare 24h hard cutoff
        if time.time() - start_time > 20 * 3600:
            logger.info("Tunnel 20-hour rotation window reached. Cycling tunnel...")
            break

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

def main():
    logger.info("Starting Cloudflare Tunnel Auto-Supervisor loop...")
    while True:
        try:
            run_tunnel()
        except Exception as e:
            logger.error(f"Error in tunnel cycle: {e}")
        logger.info("Sleeping 5 seconds before restarting tunnel...")
        time.sleep(5)

if __name__ == "__main__":
    main()
