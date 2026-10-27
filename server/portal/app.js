/**
 * Quantum Ising Optimizer - Frontend Client Logic
 */

const API_BASE = window.location.origin;

// State
let currentUser = null;
let authToken = localStorage.getItem("cim_auth_token") || null;
let currentApiKey = localStorage.getItem("cim_api_key") || null;
let pollInterval = null;
let presetsCache = {};

// Initialize on Load
document.addEventListener("DOMContentLoaded", async () => {
  await fetchVisitorCount();
  await fetchPresets();
  await checkHardwareHealth();
  setInterval(checkHardwareHealth, 5000);

  if (authToken) {
    await fetchUserProfile();
  } else {
    updateAuthNav();
  }

  // Load default preset into form
  loadPreset("max_cut_petersen");

  // Setup Drag and Drop
  setupDragAndDrop();

  // Start job polling loop
  pollJobsLoop();
});

// -----------------------------------------------------------------------------
// Hardware Telemetry & Health Check
// -----------------------------------------------------------------------------
async function checkHardwareHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/hardware/status`);
    if (!res.ok) throw new Error("Hardware endpoint error");
    const data = await res.json();

    const pill = document.getElementById("hardware-status-pill");
    const pillText = document.getElementById("hw-status-text");
    const statStatus = document.getElementById("stat-hw-status");
    const statLatency = document.getElementById("stat-hw-latency");
    const statAvgLatency = document.getElementById("stat-avg-latency");
    const statQueue = document.getElementById("stat-queue-depth");
    const statTotal = document.getElementById("stat-total-jobs");

    if (data.hardware_online) {
      pill.className = "status-pill status-online";
      pillText.innerText = `CIM Hardware: ONLINE (${data.ping_latency_ms} ms)`;
      statStatus.innerText = "Online";
      statStatus.style.color = "var(--status-green)";
      statLatency.innerText = `OPO Pulsed Cavity Bench (${data.ping_latency_ms} ms)`;
      statAvgLatency.innerText = `${data.ping_latency_ms || 67.5} ms`;
    } else {
      pill.className = "status-pill status-offline";
      pillText.innerText = "CIM Hardware: STANDBY / CALIBRATING";
      statStatus.innerText = "Standby";
      statStatus.style.color = "var(--status-yellow)";
      statLatency.innerText = "Digital Twin Calibrated";
    }

    statQueue.innerText = data.active_queue_depth || 0;
    statTotal.innerText = `Total Solves: ${data.total_jobs_completed || 0}`;
  } catch (err) {
    console.warn("Hardware health check failed:", err);
  }
}

// -----------------------------------------------------------------------------
// User Authentication & Profile
// -----------------------------------------------------------------------------
async function fetchUserProfile() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    
    if (res.status === 401) {
      logout();
      return;
    }
    
    const data = await res.json();
    currentUser = data.user;
    
    // Update Dashboard Metrics
    document.getElementById("stat-user-credits").innerText = currentUser.credits;
    document.getElementById("stat-user-tier").innerText = `${currentUser.tier.toUpperCase()} TIER`;

    // Store API Key if available
    if (data.api_keys && data.api_keys.length > 0) {
      currentApiKey = currentApiKey || data.api_keys[0].key_id;
      document.getElementById("display-api-key").value = currentApiKey;
    }

    updateAuthNav();
    updateCodeSnippet();
    refreshJobsTable();
  } catch (err) {
    console.error("Profile fetch error:", err);
  }
}

function updateAuthNav() {
  const container = document.getElementById("auth-nav-container");
  if (currentUser) {
    container.innerHTML = `
      <div style="display:flex; align-items:center; gap:16px;">
        <span style="font-size:0.85rem; font-weight:600; color:var(--text-main);">${currentUser.full_name}</span>
        <span class="status-tag completed" style="font-size:0.75rem;">${currentUser.credits} Credits</span>
        <button class="gray-nav-link" style="background:none; border:none; cursor:pointer; font-weight:700; text-decoration:underline;" onclick="openApiKeyModal()">API Key ↗</button>
        <button class="gray-nav-link" style="background:none; border:none; cursor:pointer; color:var(--text-muted);" onclick="logout()">Sign Out</button>
      </div>
    `;
    document.getElementById("stat-user-credits").innerText = currentUser.credits;
    document.getElementById("stat-user-tier").innerText = `${currentUser.tier.toUpperCase()} TIER`;
  } else {
    container.innerHTML = `
      <button id="btn-open-auth" class="gray-nav-link" style="background:none; border:none; cursor:pointer;" onclick="openAuthModal('login')">Sign In</button>
      <button id="btn-open-signup" class="gray-nav-link" style="background:none; border:none; font-weight:700; cursor:pointer; text-decoration:underline;" onclick="openAuthModal('signup')">Sign Up</button>
    `;
    document.getElementById("stat-user-credits").innerText = "--";
    document.getElementById("stat-user-tier").innerText = "Sign in to activate";
  }
}

function openApiKeyModal() {
  const modal = document.getElementById("apikey-modal");
  if (modal) {
    modal.classList.add("active");
    updateCodeSnippet();
  }
}

function closeApiKeyModal() {
  const modal = document.getElementById("apikey-modal");
  if (modal) {
    modal.classList.remove("active");
  }
}

function logout() {
  authToken = null;
  currentApiKey = null;
  currentUser = null;
  localStorage.removeItem("cim_auth_token");
  localStorage.removeItem("cim_api_key");
  updateAuthNav();
  document.getElementById("jobs-table-body").innerHTML = `
    <tr><td colspan="7" class="empty-state">Sign in to view your quantum job history.</td></tr>
  `;
}

// -----------------------------------------------------------------------------
// Auth Modal Handlers
// -----------------------------------------------------------------------------
function openAuthModal(mode) {
  document.getElementById("auth-modal").classList.add("active");
  switchAuthTab(mode);
}

function closeAuthModal() {
  document.getElementById("auth-modal").classList.remove("active");
}

function switchAuthTab(mode) {
  const btnLogin = document.getElementById("auth-tab-login");
  const btnSignup = document.getElementById("auth-tab-signup");
  const formLogin = document.getElementById("form-login");
  const formSignup = document.getElementById("form-signup");

  if (mode === "login") {
    btnLogin.classList.add("active");
    btnSignup.classList.remove("active");
    formLogin.classList.remove("hidden");
    formSignup.classList.add("hidden");
  } else {
    btnLogin.classList.remove("active");
    btnSignup.classList.add("active");
    formLogin.classList.add("hidden");
    formSignup.classList.remove("hidden");
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;

  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Authentication failed");

    authToken = data.access_token;
    localStorage.setItem("cim_auth_token", authToken);
    closeAuthModal();
    await fetchUserProfile();
  } catch (err) {
    alert("Login Error: " + err.message);
  }
}

async function handleSignup(e) {
  e.preventDefault();
  const full_name = document.getElementById("signup-name").value;
  const email = document.getElementById("signup-email").value;
  const organization = document.getElementById("signup-org").value;
  const password = document.getElementById("signup-password").value;

  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name, email, organization, password })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Registration failed");

    authToken = data.access_token;
    currentApiKey = data.primary_api_key;
    localStorage.setItem("cim_auth_token", authToken);
    localStorage.setItem("cim_api_key", currentApiKey);
    
    document.getElementById("display-api-key").value = currentApiKey;

    closeAuthModal();
    alert(`Account created! Welcome, ${full_name}. You have 100 free CIM solve credits.`);
    await fetchUserProfile();
  } catch (err) {
    alert("Signup Error: " + err.message);
  }
}

// -----------------------------------------------------------------------------
// Presets & Form Management
// -----------------------------------------------------------------------------
async function fetchPresets() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/presets`);
    if (res.ok) {
      presetsCache = await res.json();
    }
  } catch (err) {
    console.error("Presets fetch error:", err);
  }
}

function loadPreset(key) {
  const preset = presetsCache[key];
  if (!preset) return;

  document.getElementById("job-label").value = preset.name;
  const typeSelect = document.getElementById("problem-type");
  typeSelect.value = preset.problem_type;

  const dataArea = document.getElementById("problem-data");
  if (preset.qubo) {
    dataArea.value = JSON.stringify(preset.qubo, null, 2);
  } else if (preset.edges) {
    dataArea.value = JSON.stringify(preset.edges, null, 2);
  } else if (preset.numbers) {
    dataArea.value = JSON.stringify(preset.numbers, null, 2);
  }
  handleProblemTypeChange();
}

function handleProblemTypeChange() {
  const type = document.getElementById("problem-type").value;
  const label = document.getElementById("problem-data-label");
  const helper = document.getElementById("problem-helper");

  if (type === "QUBO") {
    label.innerText = "QUBO Coefficients JSON";
    helper.innerText = 'Format: {"i,j": weight} e.g. {"0,0": -2.5, "0,1": 1.2}';
  } else if (type === "MAX_CUT") {
    label.innerText = "Graph Edges JSON";
    helper.innerText = 'Format: [[u, v, weight], ...] e.g. [[0, 1], [1, 2], [2, 0]]';
  } else if (type === "NUMBER_PARTITION") {
    label.innerText = "Number List JSON";
    helper.innerText = 'Format: [int, int, ...] e.g. [19, 17, 13, 9, 6]';
  } else if (type === "ISING") {
    label.innerText = "Ising JSON (linear & quadratic)";
    helper.innerText = 'Format: {"linear": {"0": -1.0}, "quadratic": {"0,1": 0.5}}';
  }
}

// -----------------------------------------------------------------------------
// Job Submission
// -----------------------------------------------------------------------------
async function handleJobSubmit(e) {
  e.preventDefault();

  if (!authToken && !currentApiKey) {
    openAuthModal("signup");
    return;
  }

  const label = document.getElementById("job-label").value;
  const problem_type = document.getElementById("problem-type").value;
  const shots = parseInt(document.getElementById("job-shots").value, 10);
  const rawData = document.getElementById("problem-data").value;

  let parsedData;
  try {
    parsedData = JSON.parse(rawData);
  } catch (err) {
    alert("Invalid JSON format in Problem Coefficients: " + err.message);
    return;
  }

  const payload = {
    label,
    problem_type,
    shots
  };

  if (problem_type === "QUBO") payload.qubo = parsedData;
  else if (problem_type === "MAX_CUT") payload.edges = parsedData;
  else if (problem_type === "NUMBER_PARTITION") payload.numbers = parsedData;
  else if (problem_type === "ISING") {
    payload.linear = parsedData.linear || {};
    payload.quadratic = parsedData.quadratic || {};
  }

  const btn = document.getElementById("btn-submit-job");
  btn.disabled = true;
  btn.innerHTML = `<span class="btn-icon">⏳</span> Dispatching to CIM...`;

  try {
    const headers = { "Content-Type": "application/json" };
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
    else if (currentApiKey) headers["X-CIM-API-Key"] = currentApiKey;

    const res = await fetch(`${API_BASE}/api/v1/jobs/submit`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Job submission rejected");

    // Refresh immediately
    await refreshJobsTable();
    await fetchUserProfile();
  } catch (err) {
    alert("Submission Error: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span class="btn-icon">⚡</span> Dispatch to Optical CIM`;
  }
}

// -----------------------------------------------------------------------------
// Job Polling & Table Rendering
// -----------------------------------------------------------------------------
async function pollJobsLoop() {
  if (authToken || currentApiKey) {
    await refreshJobsTable();
  }
  setTimeout(pollJobsLoop, 1500);
}

async function refreshJobsTable() {
  if (!authToken && !currentApiKey) return;

  try {
    const headers = {};
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
    else if (currentApiKey) headers["X-CIM-API-Key"] = currentApiKey;

    const res = await fetch(`${API_BASE}/api/v1/jobs?limit=25`, { headers });
    if (!res.ok) return;

    const data = await res.json();
    const tbody = document.getElementById("jobs-table-body");

    if (!data.jobs || data.jobs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-muted);">No jobs found. Dispatch a problem above!</td></tr>`;
      return;
    }

    // If there's a recent completed job, update phone inspector
    const latestCompleted = data.jobs.find(j => j.status === "COMPLETED");
    if (latestCompleted && latestCompleted.result_spins) {
      updatePhoneInspector(latestCompleted);
    }

    tbody.innerHTML = data.jobs.map(j => {
      const statusBadge = getStatusBadge(j.status);
      const timeDisplay = j.execution_time_ms ? `${j.execution_time_ms} ms` : "--";
      const energyDisplay = j.result_energy !== null && j.result_energy !== undefined ? j.result_energy.toFixed(3) : "--";

      return `
        <tr>
          <td><span class="table-id-code">${j.job_id.substring(0, 12)}...</span></td>
          <td><strong>${escapeHtml(j.label || "Untitled")}</strong></td>
          <td><span style="font-family:var(--font-mono); font-size:0.75rem;">${j.problem_type}</span></td>
          <td>${statusBadge}</td>
          <td style="font-family:var(--font-mono); font-size:0.78rem;">${timeDisplay}</td>
          <td style="font-family:var(--font-mono); font-size:0.78rem; font-weight:600;">${energyDisplay}</td>
          <td>
            <button class="btn-table-action" onclick="viewJobDetails('${j.job_id}')">Details ↗</button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Job table refresh error:", err);
  }
}

function updatePhoneInspector(job) {
  const container = document.getElementById("phone-spins-container");
  const energyTag = document.getElementById("inspector-energy-tag");
  const latencyTag = document.getElementById("phone-last-latency");

  if (energyTag && job.result_energy !== null && job.result_energy !== undefined) {
    energyTag.innerText = `E₀: ${job.result_energy.toFixed(3)}`;
    energyTag.style.color = "#000000";
  }

  if (latencyTag && job.execution_time_ms) {
    latencyTag.innerText = `${job.execution_time_ms} ms`;
  }

  if (container && job.result_spins) {
    const entries = Object.entries(job.result_spins).slice(0, 16);
    container.innerHTML = entries.map(([k, v]) => `
      <span class="spin-chip-pill ${v > 0 ? 'spin-up' : 'spin-down'}">
        s<sub>${k}</sub> = ${v > 0 ? '+1' : '-1'}
      </span>
    `).join("");
  }
}

function getStatusBadge(status) {
  if (status === "COMPLETED") return `<span class="status-tag completed">COMPLETED</span>`;
  if (status === "RUNNING") return `<span class="status-tag running">RUNNING</span>`;
  if (status === "QUEUED") return `<span class="status-tag queued">QUEUED</span>`;
  if (status === "FAILED") return `<span class="status-tag failed">FAILED</span>`;
  return `<span class="status-tag">${status}</span>`;
}

async function viewJobDetails(jobId) {
  try {
    const headers = {};
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
    else if (currentApiKey) headers["X-CIM-API-Key"] = currentApiKey;

    const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`, { headers });
    if (!res.ok) throw new Error("Could not fetch job details");
    const j = await res.json();

    document.getElementById("modal-job-title").innerText = `Job: ${j.label || j.job_id}`;
    
    let spinsHtml = "";
    if (j.result_spins) {
      spinsHtml = `
        <div style="margin-top:16px;">
          <label style="font-family:var(--font-mono); font-size:0.75rem; font-weight:700; text-transform:uppercase; margin-bottom:8px; display:block;">Discovered Ground State Spins:</label>
          <div class="spin-chips-grid">
            ${Object.entries(j.result_spins).map(([k, v]) => `
              <span class="spin-chip-pill ${v > 0 ? 'spin-up' : 'spin-down'}">
                s<sub>${k}</sub> = ${v > 0 ? '+1' : '-1'}
              </span>
            `).join("")}
          </div>
        </div>
      `;
    }

    document.getElementById("modal-job-body").innerHTML = `
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:14px; font-size:0.85rem; border-bottom:var(--border-hair); padding-bottom:14px;">
        <div><strong>Status:</strong> ${getStatusBadge(j.status)}</div>
        <div><strong>Hardware:</strong> <span style="font-family:var(--font-mono); font-weight:600;">${j.hardware_mode || 'Pending'}</span></div>
        <div><strong>Ground State Energy:</strong> <strong style="font-family:var(--font-mono);">${j.result_energy !== null ? j.result_energy : '--'}</strong></div>
        <div><strong>Optical Latency:</strong> <span style="font-family:var(--font-mono);">${j.execution_time_ms ? j.execution_time_ms + ' ms' : '--'}</span></div>
        <div><strong>Problem Type:</strong> <span style="font-family:var(--font-mono);">${j.problem_type} (${j.num_variables} variables)</span></div>
        <div><strong>Submitted At:</strong> <small style="font-family:var(--font-mono);">${new Date(j.created_at).toLocaleTimeString()}</small></div>
      </div>
      ${spinsHtml}
      ${j.error_message ? `<div style="color:var(--status-red); margin-top:12px; font-family:var(--font-mono); font-size:0.8rem;"><strong>Error:</strong> ${j.error_message}</div>` : ''}
    `;

    document.getElementById("job-modal").classList.add("active");
  } catch (err) {
    alert("Error fetching job: " + err.message);
  }
}

function closeJobModal() {
  document.getElementById("job-modal").classList.remove("active");
}

// -----------------------------------------------------------------------------
// Tabs & SDK Helpers
// -----------------------------------------------------------------------------
function switchLeftTab(tab) {
  const btnSubmit = document.getElementById("tab-btn-submit");
  const btnSdk = document.getElementById("tab-btn-sdk");
  const contentSubmit = document.getElementById("tab-content-submit");
  const contentSdk = document.getElementById("tab-content-sdk");

  if (tab === "submit") {
    btnSubmit.classList.add("active");
    btnSdk.classList.remove("active");
    contentSubmit.classList.add("active");
    contentSdk.classList.remove("active");
  } else {
    btnSubmit.classList.remove("active");
    btnSdk.classList.add("active");
    contentSubmit.classList.remove("active");
    contentSdk.classList.add("active");
  }
}

function toggleApiKeyVisibility() {
  const input = document.getElementById("display-api-key");
  if (input.type === "password") input.type = "text";
  else input.type = "password";
}

function copyApiKey() {
  const input = document.getElementById("display-api-key");
  navigator.clipboard.writeText(input.value);
  alert("API Key copied to clipboard!");
}

async function handleGenerateNewKey() {
  if (!authToken) {
    openAuthModal("login");
    return;
  }
  const label = prompt("Enter a label for this API key:", "Python SDK Client");
  if (!label) return;

  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/api-keys`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ label })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Key generation failed");

    currentApiKey = data.api_key;
    localStorage.setItem("cim_api_key", currentApiKey);
    document.getElementById("display-api-key").value = currentApiKey;
    updateCodeSnippet();
    alert("New API Key generated successfully! Keep it secure.");
  } catch (err) {
    alert("Error: " + err.message);
  }
}

function updateCodeSnippet() {
  const key = currentApiKey || "YOUR_API_KEY";
  const snippet = `from cim_cloud import CIMClient

client = CIMClient(api_key="${key}", base_url="${API_BASE}")

# Define QUBO
Q = {(0, 0): -2.5, (1, 1): 2.5, (0, 1): 0.45}

# Dispatch directly to physical Coherent Ising Machine (CIM)
job = client.submit_qubo(Q, label="Colab Optimization Run")
result = job.wait_for_completion()

print("Optical Solve Latency:", result.execution_time_ms, "ms")
print("Ground State Energy:", result.energy)
print("Optimal Spins:", result.spins)`;

  document.getElementById("sdk-code-snippet").innerHTML = `<code>${escapeHtml(snippet)}</code>`;
}

function copyCodeSnippet() {
  const text = document.getElementById("sdk-code-snippet").innerText;
  navigator.clipboard.writeText(text);
  alert("Code snippet copied to clipboard!");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.innerText = text;
  return div.innerHTML;
}

// -----------------------------------------------------------------------------
// Visitor Counter & File Upload Engine
// -----------------------------------------------------------------------------
async function fetchVisitorCount() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/stats/visitor-count`);
    if (res.ok) {
      const data = await res.json();
      const el = document.getElementById("visitor-count-number");
      if (el && data.visitor_count) {
        el.innerText = data.visitor_count.toLocaleString("en-US", { minimumIntegerDigits: 6 });
      }
    }
  } catch (err) {
    console.warn("Visitor count fetch error:", err);
  }
}

function handleFileUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  processUploadedFile(file);
}

function processUploadedFile(file) {
  const reader = new FileReader();
  const fileName = file.name;
  
  reader.onload = function(evt) {
    const text = evt.target.result.trim();
    const labelInput = document.getElementById("job-label");
    const typeSelect = document.getElementById("problem-type");
    const dataArea = document.getElementById("problem-data");

    // Prepopulate label with clean file name
    labelInput.value = fileName.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");

    if (fileName.endsWith(".json")) {
      try {
        const parsed = JSON.parse(text);
        if (Array.isArray(parsed)) {
          if (parsed.length > 0 && Array.isArray(parsed[0])) {
            typeSelect.value = "MAX_CUT";
          } else {
            typeSelect.value = "NUMBER_PARTITION";
          }
        } else if (typeof parsed === "object") {
          if (parsed.linear || parsed.quadratic) {
            typeSelect.value = "ISING";
          } else {
            typeSelect.value = "QUBO";
          }
        }
        dataArea.value = JSON.stringify(parsed, null, 2);
        handleProblemTypeChange();
      } catch (err) {
        alert("JSON format error: " + err.message);
      }
    } else if (fileName.endsWith(".csv") || fileName.endsWith(".txt")) {
      // Auto-detect coordinate list: u,v or u,v,weight
      const lines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l && !l.startsWith("#"));
      if (lines.length > 0) {
        const sampleParts = lines[0].split(/[,\s\t]+/);
        if (sampleParts.length >= 2 && sampleParts.length <= 3 && !isNaN(Number(sampleParts[0]))) {
          // Graph edge list
          const edges = lines.map(line => line.split(/[,\s\t]+/).map(Number));
          typeSelect.value = "MAX_CUT";
          dataArea.value = JSON.stringify(edges, null, 2);
          handleProblemTypeChange();
        } else {
          dataArea.value = text;
        }
      }
    } else {
      dataArea.value = text;
    }
  };

  reader.readAsText(file);
}

function setupDragAndDrop() {
  const area = document.getElementById("problem-data");
  if (!area) return;

  area.addEventListener("dragover", (e) => {
    e.preventDefault();
    area.style.borderColor = "#000000";
    area.style.background = "#ffffff";
  });

  area.addEventListener("dragleave", (e) => {
    e.preventDefault();
    area.style.borderColor = "";
    area.style.background = "";
  });

  area.addEventListener("drop", (e) => {
    e.preventDefault();
    area.style.borderColor = "";
    area.style.background = "";
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processUploadedFile(e.dataTransfer.files[0]);
    }
  });
}
