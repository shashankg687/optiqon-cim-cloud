"""
Build & Deploy Edge-Native Worker for Quantum Ising Optimizer
Embeds index.html, style.css, app.js, cim_cloud.py, and presets directly into
the Cloudflare Worker to permanently eliminate Error 1016 (Origin DNS Error).
"""

import os
import json
import logging
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_edge_worker")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTAL_DIR = os.path.join(BASE_DIR, "server", "portal")

# Load .env
env_file = os.path.join(BASE_DIR, ".env")
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

PRESETS = {
    "max_cut_petersen": {
        "name": "Petersen Graph (10 Nodes) Max-Cut",
        "problem_type": "MAX_CUT",
        "edges": [
            [0, 1], [1, 2], [2, 3], [3, 4], [4, 0],
            [0, 5], [1, 6], [2, 7], [3, 8], [4, 9],
            [5, 7], [7, 9], [9, 6], [6, 8], [8, 5]
        ]
    },
    "number_partition": {
        "name": "Subset Sum / Number Partitioning",
        "problem_type": "NUMBER_PARTITION",
        "numbers": [19, 17, 13, 9, 6]
    },
    "ising_spin_glass": {
        "name": "Frustrated Spin-Glass (16 Spins)",
        "problem_type": "QUBO",
        "qubo": {
            "0,0": -2.5, "1,1": 2.5, "2,2": -2.5, "3,3": 2.5,
            "0,1": 0.35, "1,2": -0.28, "2,3": 0.42, "0,3": -0.19,
            "4,4": -3.0, "5,5": 3.0, "4,5": 0.55
        }
    }
}


def generate_worker_code(target_origin: str = "") -> str:
    with open(os.path.join(PORTAL_DIR, "index.html"), "r", encoding="utf-8") as f:
        html = f.read()

    with open(os.path.join(PORTAL_DIR, "style.css"), "r", encoding="utf-8") as f:
        css = f.read()

    with open(os.path.join(PORTAL_DIR, "app.js"), "r", encoding="utf-8") as f:
        js = f.read()

    sdk_file = os.path.join(BASE_DIR, "cim_cloud.py")
    sdk = ""
    if os.path.exists(sdk_file):
        with open(sdk_file, "r", encoding="utf-8") as f:
            sdk = f.read()

    html_json = json.dumps(html)
    css_json = json.dumps(css)
    js_json = json.dumps(js)
    sdk_json = json.dumps(sdk)
    presets_json = json.dumps(PRESETS)
    origin_json = json.dumps(target_origin)

    code = f"""// Quantum Ising Optimizer - Edge Native Platform
// High-Throughput Edge UI + Resilience Fallback Engine

const INDEX_HTML = {html_json};
const STYLE_CSS = {css_json};
const APP_JS = {js_json};
const CIM_CLOUD_PY = {sdk_json};
const PRESETS = {presets_json};
const TARGET_ORIGIN = {origin_json};

addEventListener('fetch', event => {{
  event.respondWith(handleRequest(event.request));
}});

async function handleRequest(request) {{
  const url = new URL(request.url);
  const path = url.pathname;

  // 1. Root & Portal Assets - Served 100% from Edge Memory (Zero Error 1016)
  if (path === '/' || path === '/index.html' || path === '/portal/' || path === '/portal/index.html') {{
    return new Response(INDEX_HTML, {{
      headers: {{
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'public, max-age=120'
      }}
    }});
  }}

  if (path === '/style.css' || path === '/portal/style.css') {{
    return new Response(STYLE_CSS, {{
      headers: {{
        'Content-Type': 'text/css; charset=utf-8',
        'Cache-Control': 'public, max-age=3600'
      }}
    }});
  }}

  if (path === '/app.js' || path === '/portal/app.js') {{
    return new Response(APP_JS, {{
      headers: {{
        'Content-Type': 'application/javascript; charset=utf-8',
        'Cache-Control': 'public, max-age=3600'
      }}
    }});
  }}

  if (path === '/cim_cloud.py' || path === '/api/v1/sdk/download' || path === '/api/v1/sdk/cim_cloud.py') {{
    return new Response(CIM_CLOUD_PY, {{
      headers: {{
        'Content-Type': 'text/x-python; charset=utf-8',
        'Content-Disposition': 'attachment; filename="cim_cloud.py"',
        'Cache-Control': 'public, max-age=3600'
      }}
    }});
  }}

  if (path === '/api/v1/presets') {{
    return new Response(JSON.stringify(PRESETS), {{
      headers: {{
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'public, max-age=60'
      }}
    }});
  }}

  // 2. CORS Preflight
  if (request.method === 'OPTIONS') {{
    return new Response(null, {{
      status: 204,
      headers: {{
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': '*',
        'Access-Control-Max-Age': '86400'
      }}
    }});
  }}

  // 3. API Requests Forwarding
  if (!TARGET_ORIGIN) {{
    return getFallbackResponse(path);
  }}

  const targetHost = TARGET_ORIGIN.replace(/^https?:\\/\\//, '');
  const targetUrl = TARGET_ORIGIN + path + url.search;

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
    return getFallbackResponse(path, err.message);
  }}
}}

function getFallbackResponse(path, errMsg = '') {{
  if (path === '/api/v1/hardware/status') {{
    return new Response(JSON.stringify({{
      status: 'STANDBY',
      hardware_url: 'Protected (OPO Cavity Bench)',
      hardware_online: false,
      ping_latency_ms: 0,
      active_queue_depth: 0,
      total_jobs_completed: 21,
      hardware_description: 'Coherent Ising Machine (OPO Pulsed Cavity)'
    }}), {{
      status: 200,
      headers: {{
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      }}
    }});
  }}

  return new Response(JSON.stringify({{
    error: 'Backend Standby',
    detail: 'The local CIM hardware gateway is in standby mode. Start \"python run_server.py\" on the host machine to enable live hardware execution.',
    edge_notice: errMsg
  }}), {{
    status: 503,
    headers: {{
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    }}
  }});
}}
"""
    return code


def deploy_worker(target_origin: str = "") -> bool:
    code = generate_worker_code(target_origin)
    api_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/workers/scripts/{WORKER_NAME}"
    logger.info(f"Deploying Edge Worker '{WORKER_NAME}' (Code Size: {len(code)/1024:.2f} KB, Target: {target_origin or 'Standby'})...")

    req = urllib.request.Request(
        api_url,
        data=code.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/javascript"
        },
        method="PUT"
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode())
            if data.get("success"):
                logger.info(f"==> Edge Worker '{WORKER_NAME}' deployed successfully!")
                return True
            else:
                logger.error(f"Deployment failed: {data}")
                return False
    except Exception as e:
        logger.error(f"Error deploying worker: {e}")
        return False


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "https://cups-postcard-philosophy-december.trycloudflare.com"
    deploy_worker(target)
