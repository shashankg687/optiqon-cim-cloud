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
WORKER_NAME = os.getenv("CLOUDFLARE_WORKER_NAME", "quantum-ising-optimizer")
CLOUDFLARED_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cloudflared.exe")


def update_worker_script(target_url: str):
    """Updates Cloudflare Worker proxy target to the new tunnel origin."""
    logger.info(f"Updating Cloudflare Worker proxy target to: {target_url}")
    worker_js = f"""addEventListener('fetch', event => {{
  event.respondWith(handleRequest(event.request));
}});

async function handleRequest(request) {{
  const url = new URL(request.url);
  const targetHost = '{target_url.replace("https://", "")}';
  const targetUrl = '{target_url}' + url.pathname + url.search;
  
  const modifiedHeaders = new Headers(request.headers);
  modifiedHeaders.set('Host', targetHost);
  
  const init = {{
    method: request.method,
    headers: modifiedHeaders,
    redirect: 'follow'
  }};
  
  if (request.method !== 'GET' && request.method !== 'HEAD') {{
    init.body = await request.clone().arrayBuffer();
  }}
  
  try {{
    const response = await fetch(targetUrl, init);
    const newHeaders = new Headers(response.headers);
    newHeaders.set('Access-Control-Allow-Origin', '*');
    newHeaders.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    newHeaders.set('Access-Control-Allow-Headers', '*');
    
    return new Response(response.body, {{
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders
    }});
  }} catch (err) {{
    return new Response('Edge Proxy Gateway Error: ' + err.message, {{ status: 502 }});
  }}
}}
"""
    api_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/workers/scripts/{WORKER_NAME}"
    req = urllib.request.Request(
        api_url,
        data=worker_js.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/javascript"
        },
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())
        if result.get("success"):
            logger.info("Cloudflare Worker script updated successfully!")
            return True
        else:
            logger.error(f"Worker update error: {result}")
            return False

def run_tunnel():
    """Runs cloudflared tunnel, captures URL, updates worker, and monitors health."""
    cmd = [CLOUDFLARED_PATH, "tunnel", "--url", "http://127.0.0.1:8000"]
    logger.info(f"Starting cloudflared: {' '.join(cmd)}")
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    tunnel_url = None
    start_time = time.time()
    
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        print(line, end="", flush=True)
        
        if not tunnel_url:
            match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
            if match:
                tunnel_url = match.group(0)
                logger.info(f"==> NEW TUNNEL DISCOVERED: {tunnel_url} <==")
                update_worker_script(tunnel_url)
        
        # Check for error indicators in log
        if "Unauthorized: Tunnel not found" in line or "failed to dial" in line.lower():
            logger.warning("Tunnel error detected, will restart...")
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
