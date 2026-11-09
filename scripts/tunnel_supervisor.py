"""
Cloudflare Tunnel & Worker Edge Auto-Supervisor for Quantum Ising Optimizer
Maintains active Cloudflare tunnel to local port 8000 and automatically keeps
Cloudflare Worker (quantum-ising-optimizer) synchronized with the live origin.
Includes active HTTP health watchdog, zombie process cleanup, singleton locking, and auto-healing.
"""

import os
import sys
import time
import re
import socket
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

# Singleton lock socket to prevent duplicate supervisors
_lock_socket = None

def acquire_singleton_lock(port=28188) -> bool:
    """Binds a localhost socket to ensure only one supervisor runs on the host."""
    global _lock_socket
    try:
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(("127.0.0.1", port))
        _lock_socket.listen(1)
        return True
    except OSError:
        return False

# Import Edge Worker Compiler
try:
    from scripts.build_edge_worker import deploy_worker
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.build_edge_worker import deploy_worker


def kill_existing_cloudflared(exclude_pid=None):
    """Kills any orphan cloudflared processes to prevent port/stream contention."""
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name']):
            if p.info.get('name') and 'cloudflared' in p.info['name'].lower():
                if exclude_pid and p.info['pid'] == exclude_pid:
                    continue
                try:
                    p.kill()
                    logger.info(f"Cleaned up orphan cloudflared process PID {p.info['pid']}")
                except Exception:
                    pass
    except Exception:
        pass


def verify_tunnel_health(tunnel_url: str) -> bool:
    """Verifies that the public tunnel URL is actually resolving and proxying to port 8000."""
    if not tunnel_url:
        return False
    target = f"{tunnel_url}/api/v1/hardware/status"
    req = urllib.request.Request(
        target,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OptiqonWatchdog/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                return bool(data.get("hardware_online") or data.get("status") in ["ONLINE", "STANDBY"])
    except Exception as e:
        logger.debug(f"Health check probe failed on {target}: {e}")
        return False
    return False


def update_worker_script(target_url: str):
    """Updates Cloudflare Worker with embedded UI + live tunnel API proxy."""
    logger.info(f"Deploying edge-native worker synchronized with origin: {target_url}")
    return deploy_worker(target_url)


def run_tunnel():
    """Runs cloudflared tunnel, captures fresh URL, updates Cloudflare Worker, and actively monitors health."""
    kill_existing_cloudflared()
    time.sleep(1)

    cloudflared_log = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cloudflared.log")
    os.makedirs(os.path.dirname(cloudflared_log), exist_ok=True)
    
    # Truncate logfile cleanly so we never match stale URLs from earlier sessions
    try:
        with open(cloudflared_log, "w", encoding="utf-8") as f:
            f.truncate(0)
    except Exception:
        pass

    cmd = [CLOUDFLARED_PATH, "tunnel", "--url", "http://127.0.0.1:8000", "--logfile", cloudflared_log]
    logger.info(f"Starting cloudflared with fresh logfile: {cloudflared_log}")
    
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
                    content = f.read()
                    matches = re.findall(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", content)
                    if matches:
                        tunnel_url = matches[-1]
                        logger.info(f"==> NEW TUNNEL DISCOVERED: {tunnel_url} <==")
                        time.sleep(1.5)
                        success = update_worker_script(tunnel_url)
                        if success:
                            logger.info(f"==> GATEWAY READY: https://{WORKER_NAME}.shashankg554.workers.dev <==")
                        break
            except Exception:
                pass

    if not tunnel_url:
        logger.warning("Could not extract tunnel URL within timeout")
        proc.kill()
        return

    # Proactive Health-Check Watchdog Loop
    failed_checks = 0
    last_log_check = time.time()
    last_health_check = time.time()

    while True:
        time.sleep(2)
        now = time.time()

        # 1. Process liveness
        if proc.poll() is not None:
            logger.warning(f"cloudflared process terminated (code {proc.returncode}). Restarting...")
            break
            
        # 2. Re-cycle every 18 hours to preempt Cloudflare 24h hard cutoff
        if now - start_time > 18 * 3600:
            logger.info("Tunnel reached 18-hour proactive rotation threshold. Cycling tunnel...")
            break

        # 3. Check for mid-flight tunnel URL update in log file
        if now - last_log_check > 10:
            last_log_check = now
            if os.path.exists(cloudflared_log):
                try:
                    with open(cloudflared_log, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        matches = re.findall(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", content)
                        if matches and matches[-1] != tunnel_url:
                            logger.info(f"Detected mid-flight tunnel URL update: {matches[-1]}")
                            tunnel_url = matches[-1]
                            update_worker_script(tunnel_url)
                except Exception:
                    pass

        # 4. Proactive HTTP Health Check every 10 seconds
        if now - last_health_check > 10:
            last_health_check = now
            is_healthy = verify_tunnel_health(tunnel_url)
            if not is_healthy:
                failed_checks += 1
                logger.warning(f"Tunnel health probe failed ({failed_checks}/3) for {tunnel_url}")
                if failed_checks >= 3:
                    logger.error(f"Tunnel {tunnel_url} is unresponsive/dead. Triggering auto-heal restart!")
                    break
            else:
                if failed_checks > 0:
                    logger.info(f"Tunnel health probe recovered on {tunnel_url}")
                failed_checks = 0

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    kill_existing_cloudflared()


def main():
    if not acquire_singleton_lock():
        logger.warning("Another instance of tunnel_supervisor is already running. Exiting.")
        sys.exit(0)

    logger.info("Starting Cloudflare Tunnel Auto-Supervisor loop with active health watchdog...")
    try:
        while True:
            try:
                run_tunnel()
            except Exception as e:
                logger.error(f"Error in tunnel cycle: {e}")
            logger.info("Sleeping 5 seconds before restarting tunnel...")
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Supervisor received interrupt. Cleaning up...")
    finally:
        kill_existing_cloudflared()


if __name__ == "__main__":
    main()
