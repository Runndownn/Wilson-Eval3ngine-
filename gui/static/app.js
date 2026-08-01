/* Wilson Eval3ngine GUI */
const endpoints = [];
const models = [];
const selectedModelIds = new Set();
let promptPackages = [];
let currentPdfPage = 1;
let currentPdfFile = "";
let pdfDoc = null;
let ws = null;
let reportZoom = 1.0;
let currentSelection = null;
let telemetryRuns = [];
let modalPdfDoc = null;
let modalPdfPage = 1;
let modalPdfUrl = '';
let modalZoom = 1.0;

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  const statusEl = document.getElementById("connection-status");
  const hostUrlEl = document.getElementById("host-url");
  if (hostUrlEl) {
    hostUrlEl.textContent = `${location.protocol}//${location.host}`;
  }
  ws.onopen = () => {
    statusEl?.classList.replace("badge-offline", "badge-online");
    if (statusEl) statusEl.textContent = "Online";
    sendWs({ action: "list_endpoints" });
    sendWs({ action: "list_models" });
    sendWs({ action: "list_reports" });
    sendWs({ action: "list_telemetry" });
    sendWs({ action: "list_prompt_packages" });
    sendWs({ action: "endpoints_status" });
  };
  ws.onclose = () => {
    statusEl?.classList.replace("badge-online", "badge-offline");
    if (statusEl) statusEl.textContent = "Offline";
    setTimeout(connectWebSocket, 2000);
  };
  ws.onerror = () => {
    statusEl?.classList.replace("badge-online", "badge-offline");
    if (statusEl) statusEl.textContent = "Error";
  };
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleMessage(data);
  };
}

function handleMessage(message) {
  const reportOutput = document.getElementById("report-output");
  const faultOutput = document.getElementById("fault-injection-output");
  if (message.action === "list_endpoints") {
    endpoints.length = 0;
    endpoints.push(...(message.endpoints || []));
    renderEndpoints();
    refreshEndpointOptions();
    refreshModelEndpointOptions();
    populateEndpointUrlDropdown();
  }
  if (message.action === "list_models") {
    models.length = 0;
    models.push(...(message.models || []));
    renderModels();
    updateSelectedModels();
    refreshModelDropdown();
    renderModelToggles();
  }
  if (message.action === "list_reports") {
    renderReports(message.reports || []);
  }
  if (message.action === "list_telemetry") {
    telemetryRuns = message.runs || [];
    renderTelemetry(telemetryRuns);
  }
  if (message.action === "list_prompt_packages") {
    promptPackages = message.packages || [];
    populatePromptPackages();
  }
  if (message.action === "endpoints_status") {
    applyEndpointAvailability(message.statuses || []);
  }
  if (message.action === "generate_reports") {
    if (reportOutput) {
      if (message.status === "complete") {
        reportOutput.textContent = message.stdout || "Done";
      } else if (message.status === "started") {
        reportOutput.textContent = "Generating reports...";
      } else if (message.status === "error") {
        reportOutput.textContent = `Error: ${message.error || "Unknown"}`;
      } else if (message.status === "skipped") {
        reportOutput.textContent = `Skipped: ${message.error || "Unknown"}`;
      }
    }
    if (message.status === "complete") {
      sendWs({ action: "list_reports" });
      sendWs({ action: "list_telemetry" });
    }
  }
  if (message.action === "run_game_day") {
    if (faultOutput) {
      if (message.status === "complete") {
        const report = message.report || {};
        const richText = formatGameDayReport(report);
        const rawText = JSON.stringify(report, null, 2);
        faultOutput.innerHTML = `<div class="fault-output-tabs">
          <button class="fault-tab active" data-fault-tab="rich">Rich Text</button>
          <button class="fault-tab" data-fault-tab="raw">Raw JSON</button>
        </div>
        <div class="fault-output-content" id="fault-rich">${escapeHtml(richText)}</div>
        <div class="fault-output-content hidden" id="fault-raw"><pre>${escapeHtml(rawText)}</pre></div>`;
        initFaultOutputTabs();
      } else if (message.status === "started") {
        faultOutput.textContent = "Running fault injection...";
      } else {
        faultOutput.textContent = `Error: ${message.error || "Unknown"}`;
      }
    }
    if (message.status === "complete") {
      sendWs({ action: "list_telemetry" });
    }
  }
  if (message.action === "generate_token") {
    if (message.token) {
      const authInput = document.getElementById("fault-injection-auth");
      if (authInput) authInput.value = message.token;
    }
  }
  if (message.action === "kilo_login") {
    const statusEl = document.getElementById("kilo-login-status");
    if (statusEl) {
      if (message.ok) {
        const modelCount = (message.models || []).length;
        statusEl.textContent = `Kilo Gateway reachable: ${message.message || message.url} — ${modelCount} models available`;
        statusEl.className = "status-message success";
        // Show Kilo models in the Models tab
        renderKiloModels(message.models || []);
        // Auto-configure endpoint and discover models
        autoConfigureKiloEndpoint();
      } else {
        statusEl.textContent = `Kilo Gateway unreachable: ${message.error || 'Unknown error'}`;
        statusEl.className = "status-message error";
      }
    }
  }
}

function formatGameDayReport(report) {
  if (!report || typeof report !== 'object') return 'No report data';
  const lines = [];
  lines.push('=== Fault Injection Report ===');
  lines.push(`Run ID: ${report.runId || 'N/A'}`);
  lines.push(`Started: ${report.startedAt || 'N/A'}`);
  lines.push(`Finished: ${report.finishedAt || 'N/A'}`);
  lines.push(`Status: ${report.status || 'N/A'}`);
  lines.push('');
  if (report.scenarios && report.scenarios.length) {
    lines.push(`Scenarios executed: ${report.scenarios.length}`);
    report.scenarios.forEach((s, i) => {
      lines.push(`  ${i+1}. ${s.name || s.id || 'Scenario'} - ${s.status || 'unknown'}`);
      if (s.details) lines.push(`     Details: ${s.details}`);
    });
  }
  if (report.summary) lines.push(`Summary: ${report.summary}`);
  if (report.results) lines.push(`Results: ${JSON.stringify(report.results, null, 2)}`);
  return lines.join('\n');
}

function initFaultOutputTabs() {
  document.querySelectorAll('.fault-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.fault-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.dataset.faultTab;
      document.querySelectorAll('.fault-output-content').forEach(c => c.classList.add('hidden'));
      const content = document.getElementById(`fault-${target}`);
      if (content) content.classList.remove('hidden');
    });
  });
}

function renderKiloModels(kiloModels) {
  const section = document.getElementById("kilo-models-section");
  const container = document.getElementById("kilo-models-list");
  if (!section || !container) return;
  if (!kiloModels || !kiloModels.length) {
    section.classList.add("hidden");
    return;
  }
  section.classList.remove("hidden");
  container.innerHTML = `
    <div class="kilo-models-header">
      <span class="kilo-models-title">Kilo Gateway Models (${kiloModels.length})</span>
      <button type="button" id="add-kilo-models" class="secondary">Add All to Models</button>
    </div>
    <div class="kilo-models-grid">
      ${kiloModels.map((m) => `
        <label class="kilo-model-chip">
          <input type="checkbox" value="${escapeHtml(m)}" />
          <span>${escapeHtml(m)}</span>
        </label>
      `).join('')}
    </div>
  `;

  const addAllBtn = document.getElementById('add-kilo-models');
  if (addAllBtn) {
    addAllBtn.addEventListener('click', async () => {
      const cbs = container.querySelectorAll('.kilo-model-chip input[type="checkbox"]:checked');
      const selected = Array.from(cbs).map(cb => cb.value);
      if (!selected.length) {
        alert('Select at least one Kilo model to add.');
        return;
      }
      // Find Kilo Gateway endpoint
      const kiloEp = endpoints.find(ep => ep.provider === 'kilo');
      if (!kiloEp) {
        alert('Kilo Gateway endpoint not found. Please run Kilo Login first.');
        return;
      }
      for (const modelId of selected) {
        await fetch('/api/models', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: modelId, endpointId: kiloEp.id, provider: 'kilo' }),
        });
      }
      sendWs({ action: 'list_models' });
      addAllBtn.textContent = 'Added!';
      setTimeout(() => { addAllBtn.textContent = 'Add All to Models'; }, 1200);
    });
  }
}

function autoConfigureKiloEndpoint() {
  const kiloUrl = 'https://api.kilo.ai/api/gateway';
  // Check if Kilo Gateway endpoint already exists
  const existing = endpoints.find(ep => ep.provider === 'kilo');
  if (!existing) {
    fetch('/api/endpoints', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Kilo Gateway',
        url: kiloUrl,
        provider: 'kilo',
        apiKey: ''
      })
    }).then(() => {
      sendWs({ action: 'list_endpoints' });
      return fetch('/api/models/auto-detect', { method: 'POST' });
    }).then(() => {
      sendWs({ action: 'list_models' });
      sendWs({ action: 'endpoints_status' });
    }).catch(() => {
      sendWs({ action: 'list_endpoints' });
    });
  } else {
    fetch('/api/models/auto-detect', { method: 'POST' })
      .then(() => {
        sendWs({ action: 'list_models' });
        sendWs({ action: 'endpoints_status' });
      })
      .catch(() => {});
  }
}

function sendWs(message) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
  }
}

function saveLocalStorage(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
}
function loadLocalStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function formatBytes(bytes) {
  if (bytes === undefined || bytes === null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

function initTabs() {
  const links = document.querySelectorAll(".tab-link");
  const panels = document.querySelectorAll(".tab-panel");
  links.forEach((link) => {
    link.addEventListener("click", () => {
      const target = link.dataset.tab;
      links.forEach((l) => l.classList.remove("active"));
      panels.forEach((p) => p.classList.remove("active"));
      link.classList.add("active");
      const panel = document.getElementById(target);
      if (panel) panel.classList.add("active");
    });
  });
}

// ---------------------------------------------------------------------------
// Direction buttons
// ---------------------------------------------------------------------------

function initDirectionButtons() {
  document.querySelectorAll(".direction-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.target;
      const target = document.getElementById(targetId);
      if (!target) return;
      const isHidden = target.style.display === "none";
      target.style.display = isHidden ? "block" : "none";
      btn.classList.toggle("active", isHidden);
    });
  });
}

// ---------------------------------------------------------------------------
// Help tooltips
// ---------------------------------------------------------------------------

function initHelpIcons() {
  document.querySelectorAll(".help-icon").forEach((icon) => {
    icon.addEventListener("mouseenter", () => {
      const targetId = icon.dataset.help;
      const target = document.getElementById(targetId);
      if (target) target.classList.add("show");
    });
    icon.addEventListener("mouseleave", () => {
      const targetId = icon.dataset.help;
      const target = document.getElementById(targetId);
      if (target) target.classList.remove("show");
    });
  });
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

function populateEndpointUrlDropdown() {
  const select = document.getElementById("endpoint-url");
  if (!select) return;
  // Keep the default and example options, add discovered endpoints
  const discovered = endpoints.filter(ep => ep.url && !ep.url.includes('localhost') && !ep.url.includes('127.0.0.1'));
  // We don't modify the static options; auto-detect will add endpoints via the list
  // The dropdown already has example options
}

function refreshEndpointOptions() {
  const select = document.getElementById("model-endpoint");
  if (!select) return;
  select.innerHTML = endpoints
    .map((ep) => `<option value="${escapeHtml(ep.id)}">${escapeHtml(ep.name)}</option>`)
    .join("");
}

function renderEndpoints() {
  const list = document.getElementById("endpoints-list");
  if (!list) return;
  list.innerHTML = endpoints
    .map(
      (ep, idx) => `
      <div class="list-item">
        <div>
          <div class="name">${escapeHtml(ep.name)}</div>
          <div class="meta">${escapeHtml(ep.provider)} - ${escapeHtml(ep.url)} ${ep.available === true ? '<span class="badge badge-online">Online</span>' : ep.available === false ? '<span class="badge badge-offline">Offline</span>' : ''}</div>
        </div>
        <div class="actions">
          <button data-endpoint-test="${idx}" class="secondary">Test</button>
          <button data-endpoint-delete="${idx}" class="danger">Delete</button>
        </div>
      </div>
    `
    )
    .join("");

  list.querySelectorAll("[data-endpoint-test]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const idx = parseInt(btn.dataset.endpointTest || "0", 10);
      const ep = endpoints[idx];
      if (!ep) return;
      btn.disabled = true;
      btn.textContent = "Testing...";
      try {
        const res = await fetch(`/api/endpoints/${encodeURIComponent(ep.id)}/test`, { method: "POST" });
        const json = await res.json();
        alert(JSON.stringify(json, null, 2));
      } catch (exc) {
        alert(`Endpoint test failed: ${exc}`);
      } finally {
        btn.disabled = false;
        btn.textContent = "Test";
      }
    });
  });

  list.querySelectorAll("[data-endpoint-delete]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const idx = parseInt(btn.dataset.endpointDelete || "0", 10);
      const ep = endpoints[idx];
      if (!ep) return;
      if (!confirm(`Delete endpoint "${ep.name}"?`)) return;
      await fetch(`/api/endpoints/${encodeURIComponent(ep.id)}`, { method: "DELETE" });
      sendWs({ action: "list_endpoints" });
      sendWs({ action: "list_models" });
    });
  });
}

async function initEndpoints() {
  const form = document.getElementById("endpoint-form");
  const autoBtn = document.getElementById("auto-detect-endpoints");
  const kiloLoginBtn = document.getElementById("kilo-login");
  const urlSelect = document.getElementById("endpoint-url");
  const urlCustom = document.getElementById("endpoint-url-custom");

  urlSelect?.addEventListener("change", () => {
    if (urlSelect.value === "__custom__") {
      urlCustom.classList.remove("hidden");
      urlCustom.focus();
    } else {
      urlCustom.classList.add("hidden");
      urlCustom.value = "";
    }
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = document.getElementById("endpoint-name")?.value || "Unnamed";
    let url = urlSelect?.value || "";
    if (url === "__custom__") {
      url = urlCustom?.value?.trim() || "";
    }
    if (!url) {
      alert("Please select or enter an endpoint URL.");
      return;
    }
    const apiKey = document.getElementById("endpoint-api-key")?.value || undefined;
    const provider = document.getElementById("endpoint-provider")?.value || "ollama";
    await fetch("/api/endpoints", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, url, apiKey, provider }),
    });
    if (urlSelect) urlSelect.value = "";
    if (urlCustom) {
      urlCustom.value = "";
      urlCustom.classList.add("hidden");
    }
    sendWs({ action: "list_endpoints" });
  });

  autoBtn?.addEventListener("click", async () => {
    autoBtn.disabled = true;
    autoBtn.textContent = "Detecting...";
    await fetch("/api/endpoints/auto-detect", { method: "POST" });
    sendWs({ action: "list_endpoints" });
    sendWs({ action: "list_models" });
    autoBtn.disabled = false;
    autoBtn.textContent = "Auto-Detect Local";
  });

  kiloLoginBtn?.addEventListener("click", async () => {
    kiloLoginBtn.disabled = true;
    kiloLoginBtn.textContent = "Logging in...";
    sendWs({ action: "kilo_login", host: "gateway" });
    setTimeout(() => {
      kiloLoginBtn.disabled = false;
      kiloLoginBtn.textContent = "Kilo Login";
    }, 2000);
  });

  renderEndpoints();
}

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

function refreshModelEndpointOptions() {
  const select = document.getElementById("model-endpoint");
  if (!select) return;
  select.innerHTML = endpoints
    .map((ep) => `<option value="${escapeHtml(ep.id)}">${escapeHtml(ep.name)}</option>`)
    .join("");
}

function refreshModelDropdown() {
  const select = document.getElementById("model-id");
  if (!select) return;
  const currentVal = select.value;
  select.innerHTML = '<option value="">-- Select a model --</option>' +
    '<option value="__custom__">-- Custom... --</option>' +
    models
      .map((m) => {
        const ep = endpoints.find((e) => e.id === m.endpointId);
        const available = ep ? ep.available : null;
        const disabled = available === false ? "disabled" : "";
        const label = m.id + (ep ? ` (${ep.name})` : "");
        return `<option value="${escapeHtml(m.id)}" ${disabled}>${escapeHtml(label)}</option>`;
      })
      .join("");
  if (currentVal) select.value = currentVal;
}

function renderModels() {
  const list = document.getElementById("models-list");
  if (!list) return;
  list.innerHTML = models
    .map((m, idx) => {
      const endpoint = endpoints.find((ep) => ep.id === m.endpointId);
      return `
        <div class="list-item">
          <div>
            <div class="name">${escapeHtml(m.id)}</div>
            <div class="meta">${escapeHtml(m.provider || "unknown")} - ${endpoint ? escapeHtml(endpoint.name) : "unknown"} ${endpoint && endpoint.available === false ? '<span class="badge badge-offline">Offline</span>' : ''}</div>
          </div>
          <button data-model-delete="${idx}" class="danger">Delete</button>
        </div>
      `;
    })
    .join("");

  list.querySelectorAll("[data-model-delete]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const idx = parseInt(btn.dataset.modelDelete || "0", 10);
      const m = models[idx];
      if (!m) return;
      if (!confirm(`Delete model "${m.id}"?`)) return;
      await fetch(`/api/models/${encodeURIComponent(m.id)}`, { method: "DELETE" });
      sendWs({ action: "list_models" });
    });
  });
}

function renderModelToggles() {
  const container = document.getElementById("selected-models-list");
  if (!container) return;
  container.innerHTML = models
    .map((m) => {
      const ep = endpoints.find((e) => e.id === m.endpointId);
      const label = m.id + (ep ? ` (${ep.name})` : "");
      const checked = selectedModelIds.has(m.id) ? "checked" : "";
      return `<label class="model-toggle">
        <input type="checkbox" value="${escapeHtml(m.id)}" ${checked} />
        <span>${escapeHtml(label)}</span>
      </label>`;
    })
    .join("");

  container.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
    cb.addEventListener("click", (e) => {
      if (e.ctrlKey || e.metaKey || e.shiftKey) {
        // Multi-toggle mode: toggle all visible checkboxes
        const allCbs = container.querySelectorAll('input[type="checkbox"]');
        const newState = cb.checked;
        allCbs.forEach(c => {
          c.checked = newState;
          if (newState) {
            selectedModelIds.add(c.value);
          } else {
            selectedModelIds.delete(c.value);
          }
        });
      } else {
        // Single toggle
        if (cb.checked) {
          selectedModelIds.add(cb.value);
        } else {
          selectedModelIds.delete(cb.value);
        }
      }
    });
  });
}

function updateSelectedModels() {
  renderModelToggles();
}

async function initModels() {
  const form = document.getElementById("model-form");
  const autoBtn = document.getElementById("auto-detect-models");
  const modelIdSelect = document.getElementById("model-id");
  const modelIdCustom = document.getElementById("model-id-custom");

  modelIdSelect?.addEventListener("change", () => {
    if (modelIdSelect.value === "__custom__") {
      modelIdCustom.classList.remove("hidden");
      modelIdCustom.focus();
    } else {
      modelIdCustom.classList.add("hidden");
      modelIdCustom.value = "";
    }
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    let id = modelIdSelect?.value || "";
    if (id === "__custom__") {
      id = modelIdCustom?.value?.trim() || "unknown";
    }
    if (!id) {
      alert("Please select or enter a model ID.");
      return;
    }
    const endpointId = document.getElementById("model-endpoint")?.value || "";
    const provider = endpoints.find((ep) => ep.id === endpointId)?.provider || "ollama";
    await fetch("/api/models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, endpointId, provider }),
    });
    selectedModelIds.add(id);
    updateSelectedModels();
    if (modelIdSelect) modelIdSelect.value = "";
    if (modelIdCustom) {
      modelIdCustom.value = "";
      modelIdCustom.classList.add("hidden");
    }
    sendWs({ action: "list_models" });
  });

  autoBtn?.addEventListener("click", async () => {
    autoBtn.disabled = true;
    autoBtn.textContent = "Detecting...";
    await fetch("/api/models/auto-detect", { method: "POST" });
    sendWs({ action: "list_models" });
    autoBtn.disabled = false;
    autoBtn.textContent = "Auto-Detect from Endpoints";
  });

  renderModels();
}

// ---------------------------------------------------------------------------
// Generate Reports
// ---------------------------------------------------------------------------

function populatePromptPackages() {
  const select = document.getElementById("report-prompt-package");
  if (!select) return;
  select.innerHTML = '<option value="">-- Select a prompt package --</option>' +
    promptPackages
      .map((pkg) => `<option value="${escapeHtml(pkg.id)}">${escapeHtml(pkg.name)}</option>`)
      .join("");

  select?.addEventListener("change", () => {
    const textarea = document.getElementById("report-prompts");
    if (!textarea) return;
    const pkg = promptPackages.find((p) => p.id === select.value);
    if (pkg && pkg.prompts) {
      textarea.value = pkg.prompts.join(", ");
    } else {
      textarea.value = "";
    }
  });
}

function initGenerateReports() {
  const form = document.getElementById("report-form");
  const stopBtn = document.getElementById("stop-reports");
  const selectAllBtn = document.getElementById("select-all-models");
  const selectNoneBtn = document.getElementById("select-none-models");

  selectAllBtn?.addEventListener("click", () => {
    const cbs = document.querySelectorAll('#selected-models-list input[type="checkbox"]');
    cbs.forEach(cb => {
      cb.checked = true;
      selectedModelIds.add(cb.value);
    });
  });

  selectNoneBtn?.addEventListener("click", () => {
    const cbs = document.querySelectorAll('#selected-models-list input[type="checkbox"]');
    cbs.forEach(cb => {
      cb.checked = false;
      selectedModelIds.delete(cb.value);
    });
  });

  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    const promptsTextarea = document.getElementById("report-prompts");
    const prompts = (promptsTextarea?.value || "")
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    const modelIds = Array.from(selectedModelIds);
    if (!modelIds.length) {
      alert("Please select at least one model.");
      return;
    }
    sendWs({
      action: "generate_reports",
      models: modelIds,
      prompts,
    });
  });

  stopBtn?.addEventListener("click", () => {
    const output = document.getElementById("report-output");
    if (output) output.textContent = "Stopping...";
  });
}

// ---------------------------------------------------------------------------
// Fault Injection (formerly Game Day)
// ---------------------------------------------------------------------------

function initFaultInjection() {
  const form = document.getElementById("fault-injection-form");
  const generateTokenBtn = document.getElementById("generate-token");

  generateTokenBtn?.addEventListener("click", () => {
    generateTokenBtn.disabled = true;
    generateTokenBtn.textContent = "Generating...";
    sendWs({
      action: "generate_token",
      environment: "staging",
      operator: "operator",
    });
    setTimeout(() => {
      generateTokenBtn.disabled = false;
      generateTokenBtn.textContent = "Generate Token";
    }, 1500);
  });

  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    const authInput = document.getElementById("fault-injection-auth");
    const envSelect = document.getElementById("fault-injection-env");
    const env = envSelect?.value || "staging";
    if (env !== "staging") {
      alert("Fault Injection is only permitted against isolated staging environments.");
      return;
    }
    if (!authInput?.value) {
      alert("Please enter an authorization token or click Generate Token.");
      return;
    }
    sendWs({
      action: "run_game_day",
      authorization: authInput.value,
    });
  });
}

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

function renderReports(reports) {
  const grid = document.getElementById("reports-grid");
  if (!grid) return;
  const search = (document.getElementById("report-search")?.value || "").toLowerCase();
  const filtered = reports.filter((r) => r.name.toLowerCase().includes(search));
  grid.innerHTML = filtered
    .map(
      (r) => `
      <div class="report-card" data-report-url="${escapeHtml(r.url)}">
        <div class="report-preview" data-report-url="${escapeHtml(r.url)}">
          <canvas class="report-preview-canvas" data-report-url="${escapeHtml(r.url)}" data-page="1"></canvas>
          <div class="report-preview-controls">
            <button class="report-prev-page secondary" data-report-url="${escapeHtml(r.url)}" title="Previous page">◀</button>
            <button class="report-zoom-in secondary" data-report-url="${escapeHtml(r.url)}" title="Zoom in">+</button>
            <button class="report-zoom-out secondary" data-report-url="${escapeHtml(r.url)}" title="Zoom out">−</button>
            <button class="report-next-page secondary" data-report-url="${escapeHtml(r.url)}" title="Next page">▶</button>
            <button class="report-open secondary" data-report-url="${escapeHtml(r.url)}" title="Open in viewer">Open</button>
          </div>
        </div>
        <div class="name">${escapeHtml(r.name)}</div>
        <div class="meta">${formatBytes(r.size_bytes)}</div>
        <div class="actions">
          <a href="${escapeHtml(r.url)}" download class="secondary">Download</a>
        </div>
      </div>
    `
    )
    .join("");

  // Initialize previews
  grid.querySelectorAll(".report-preview").forEach((preview) => {
    const url = preview.dataset.reportUrl;
    const canvas = preview.querySelector(".report-preview-canvas");
    if (url && canvas) {
      renderReportPreview(url, canvas, 1.0);
    }
    // Ctrl+scroll zoom
    preview.addEventListener("wheel", (e) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const canvas = preview.querySelector(".report-preview-canvas");
      if (!canvas) return;
      const delta = e.deltaY < 0 ? 0.1 : -0.1;
      const newZoom = Math.min(3.0, Math.max(0.5, (parseFloat(canvas.dataset.zoom || 1) || 1) + delta));
      canvas.dataset.zoom = newZoom;
      renderReportPreview(url, canvas, newZoom);
    }, { passive: false });
  });

  grid.querySelectorAll(".report-zoom-in").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const url = btn.dataset.reportUrl;
      const preview = btn.closest(".report-preview");
      const canvas = preview?.querySelector(".report-preview-canvas");
      if (url && canvas) {
        const newZoom = Math.min(3.0, (parseFloat(canvas.dataset.zoom || 1) || 1) + 0.25);
        canvas.dataset.zoom = newZoom;
        const page = parseInt(canvas.dataset.page || 1, 10);
        renderReportPreview(url, canvas, newZoom, page);
      }
    });
  });

  grid.querySelectorAll(".report-zoom-out").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const url = btn.dataset.reportUrl;
      const preview = btn.closest(".report-preview");
      const canvas = preview?.querySelector(".report-preview-canvas");
      if (url && canvas) {
        const newZoom = Math.max(0.5, (parseFloat(canvas.dataset.zoom || 1) || 1) - 0.25);
        canvas.dataset.zoom = newZoom;
        const page = parseInt(canvas.dataset.page || 1, 10);
        renderReportPreview(url, canvas, newZoom, page);
      }
    });
  });

  grid.querySelectorAll(".report-prev-page").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const url = btn.dataset.reportUrl;
      const preview = btn.closest(".report-preview");
      const canvas = preview?.querySelector(".report-preview-canvas");
      if (url && canvas) {
        let page = parseInt(canvas.dataset.page || 1, 10);
        if (page > 1) page--;
        canvas.dataset.page = page;
        const zoom = parseFloat(canvas.dataset.zoom || 1) || 1;
        renderReportPreview(url, canvas, zoom, page);
      }
    });
  });

  grid.querySelectorAll(".report-next-page").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const url = btn.dataset.reportUrl;
      const preview = btn.closest(".report-preview");
      const canvas = preview?.querySelector(".report-preview-canvas");
      if (url && canvas) {
        const zoom = parseFloat(canvas.dataset.zoom || 1) || 1;
        let page = parseInt(canvas.dataset.page || 1, 10);
        renderReportPreview(url, canvas, zoom, page + 1).then(doc => {
          if (doc) canvas.dataset.page = page + 1;
        });
      }
    });
  });

  grid.querySelectorAll(".report-open").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const url = btn.dataset.reportUrl || "";
      const viewer = document.getElementById("pdf-viewer");
      const gridEl = document.getElementById("reports-grid");
      if (viewer) viewer.style.display = "block";
      if (gridEl) gridEl.style.display = "none";
      openPdf(url);
    });
  });
}

async function renderReportPreview(url, canvas, zoom, page = 1) {
  if (!url || !canvas) return null;
  try {
    const task = pdfjsLib.getDocument(url);
    const doc = await task.promise;
    const pageNum = Math.min(Math.max(1, page), doc.numPages);
    const page = await doc.getPage(pageNum);
    const scale = zoom * 0.5;
    const viewport = page.getViewport({ scale });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    await page.render({ canvasContext: ctx, viewport }).promise;
    canvas.dataset.page = pageNum;
    return doc;
  } catch (exc) {
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.font = "12px sans-serif";
      ctx.fillStyle = "#e6e9f5";
      ctx.fillText(`Preview: ${url.split('/').pop()}`, 10, 20);
    }
    return null;
  }
}

async function renderTelemetryPdfPreview(url, canvas) {
  if (!url || !canvas) return;
  try {
    const task = pdfjsLib.getDocument(url);
    const doc = await task.promise;
    const page = await doc.getPage(1);
    const maxHeight = 700;
    const unscaledHeight = page.getViewport({ scale: 1 }).height;
    const scale = Math.min(maxHeight / unscaledHeight, 2.0);
    const viewport = page.getViewport({ scale });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    await page.render({ canvasContext: ctx, viewport }).promise;
  } catch (exc) {
    const ctx = canvas.getContext("2d");
    if (ctx) {
      canvas.width = 400;
      canvas.height = 80;
      ctx.fillStyle = '#e6e9f5';
      ctx.font = '12px sans-serif';
      ctx.fillText(`Preview unavailable: ${url.split('/').pop()}`, 10, 20);
    }
  }
}

async function renderFullPdfToContainer(url, container) {
  if (!url || !container) return;
  try {
    const task = pdfjsLib.getDocument(url);
    const doc = await task.promise;
    container.innerHTML = '';
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const scale = 1.2;
      const viewport = page.getViewport({ scale });
      const canvas = document.createElement('canvas');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.maxWidth = '100%';
      canvas.style.height = 'auto';
      canvas.style.display = 'block';
      canvas.style.marginBottom = '12px';
      const ctx = canvas.getContext('2d');
      if (ctx) {
        await page.render({ canvasContext: ctx, viewport }).promise;
      }
      container.appendChild(canvas);
    }
  } catch (exc) {
    container.innerHTML = '<div class="pdf-placeholder">Failed to load PDF</div>';
  }
}

async function renderPdfPagesToContainer(url, container) {
  if (!url || !container) return;
  try {
    const task = pdfjsLib.getDocument(url);
    const doc = await task.promise;
    container.innerHTML = '';
    const containerWidth = container.clientWidth || 400;
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const unscaledViewport = page.getViewport({ scale: 1 });
      const maxWidth = Math.max(100, containerWidth - 12);
      const scale = Math.min(2.0, maxWidth / unscaledViewport.width);
      const viewport = page.getViewport({ scale });
      const canvas = document.createElement('canvas');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.maxWidth = '100%';
      canvas.style.height = 'auto';
      canvas.style.display = 'block';
      canvas.style.marginBottom = '8px';
      const ctx = canvas.getContext('2d');
      if (ctx) {
        await page.render({ canvasContext: ctx, viewport }).promise;
      }
      container.appendChild(canvas);
    }
  } catch (exc) {
    container.innerHTML = '<div class="pdf-placeholder">Failed to load PDF</div>';
  }
}

async function openPdfModal(url) {
  const modal = document.getElementById('pdf-modal');
  const titleEl = document.getElementById('pdf-modal-title');
  const container = document.getElementById('pdf-modal-container');
  const zoomLabel = document.getElementById('pdf-modal-zoom');
  if (!modal || !container) return;

  modalPdfUrl = url;
  modalZoom = 1.0;
  if (titleEl) titleEl.textContent = url.split('/').pop() || 'PDF Viewer';
  if (zoomLabel) zoomLabel.textContent = '100%';
  container.innerHTML = '';

  modal.classList.add('show');

  try {
    const task = pdfjsLib.getDocument(url);
    modalPdfDoc = await task.promise;
    await renderPdfModalPages();
  } catch (exc) {
    container.innerHTML = '<div class="pdf-placeholder">Failed to load PDF</div>';
  }
}

async function renderPdfModalPages() {
  const container = document.getElementById('pdf-modal-container');
  if (!container || !modalPdfDoc) return;

  container.innerHTML = '';
  const containerWidth = container.clientWidth || 800;
  for (let i = 1; i <= modalPdfDoc.numPages; i++) {
    const page = await modalPdfDoc.getPage(i);
    const unscaledViewport = page.getViewport({ scale: 1 });
    const maxWidth = Math.max(100, containerWidth - 24);
    const baseScale = Math.min(2.5, maxWidth / unscaledViewport.width);
    const scale = baseScale * modalZoom;
    const viewport = page.getViewport({ scale });

    const canvas = document.createElement('canvas');
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.maxWidth = '100%';
    canvas.style.height = 'auto';
    canvas.style.display = 'block';
    canvas.style.marginBottom = '12px';
    const ctx = canvas.getContext('2d');
    if (ctx) {
      await page.render({ canvasContext: ctx, viewport }).promise;
    }
    container.appendChild(canvas);
  }
}

function closePdfModal() {
  const modal = document.getElementById('pdf-modal');
  if (modal) modal.classList.remove('show');
  modalPdfDoc = null;
  modalPdfPage = 1;
  modalPdfUrl = '';
  modalZoom = 1.0;
}

async function modalZoomIn() {
  if (!modalPdfDoc) return;
  modalZoom = Math.min(3.0, modalZoom + 0.25);
  const zoomLabel = document.getElementById('pdf-modal-zoom');
  if (zoomLabel) zoomLabel.textContent = `${Math.round(modalZoom * 100)}%`;
  await renderPdfModalPages();
}

async function modalZoomOut() {
  if (!modalPdfDoc) return;
  modalZoom = Math.max(0.5, modalZoom - 0.25);
  const zoomLabel = document.getElementById('pdf-modal-zoom');
  if (zoomLabel) zoomLabel.textContent = `${Math.round(modalZoom * 100)}%`;
  await renderPdfModalPages();
}

async function openPdf(url) {
  const canvas = document.getElementById("pdf-canvas");
  const pageLabel = document.getElementById("pdf-page");
  const openLink = document.getElementById("pdf-open");
  const titleEl = document.getElementById("pdf-title");
  if (!canvas) return;
  currentPdfFile = url;
  if (openLink) openLink.href = url;
  if (titleEl) titleEl.textContent = url.split("/").pop() || "";

  try {
    const task = pdfjsLib.getDocument(url);
    pdfDoc = await task.promise;
    currentPdfPage = 1;
    await renderPdfPage(canvas, pageLabel);
  } catch (exc) {
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.font = "14px sans-serif";
      ctx.fillStyle = "#e6e9f5";
      ctx.fillText(`Failed to load PDF: ${exc}`, 10, 30);
    }
  }
}

async function renderPdfPage(canvas, pageLabel) {
  if (!pdfDoc) return;
  const page = await pdfDoc.getPage(currentPdfPage);
  const scale = 1.5;
  const viewport = page.getViewport({ scale });
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  await page.render({ canvasContext: ctx, viewport }).promise;
  if (pageLabel) pageLabel.textContent = `Page ${currentPdfPage} / ${pdfDoc.numPages}`;
}

function initReports() {
  const refreshButton = document.getElementById("refresh-reports");
  const exportButton = document.getElementById("export-reports");
  const searchInput = document.getElementById("report-search");
  const pdfBack = document.getElementById("pdf-back");
  const pdfPrev = document.getElementById("pdf-prev");
  const pdfNext = document.getElementById("pdf-next");
  const pdfExport = document.getElementById("pdf-export");
  const pdfOpen = document.getElementById("pdf-open");

  refreshButton?.addEventListener("click", () => {
    sendWs({ action: "list_reports" });
  });

  exportButton?.addEventListener("click", () => {
    if (!currentPdfFile) {
      alert("No PDF selected to export.");
      return;
    }
    const a = document.createElement("a");
    a.href = currentPdfFile;
    a.download = currentPdfFile.split("/").pop() || "report.pdf";
    a.target = "_blank";
    a.click();
  });

  searchInput?.addEventListener("input", () => {
    sendWs({ action: "list_reports" });
  });

  pdfBack?.addEventListener("click", () => {
    const viewer = document.getElementById("pdf-viewer");
    const gridEl = document.getElementById("reports-grid");
    if (viewer) viewer.style.display = "none";
    if (gridEl) gridEl.style.display = "grid";
  });

  pdfPrev?.addEventListener("click", async () => {
    if (!pdfDoc || currentPdfPage <= 1) return;
    currentPdfPage -= 1;
    const canvas = document.getElementById("pdf-canvas");
    const pageLabel = document.getElementById("pdf-page");
    await renderPdfPage(canvas, pageLabel);
  });

  pdfNext?.addEventListener("click", async () => {
    if (!pdfDoc || currentPdfPage >= pdfDoc.numPages) return;
    currentPdfPage += 1;
    const canvas = document.getElementById("pdf-canvas");
    const pageLabel = document.getElementById("pdf-page");
    await renderPdfPage(canvas, pageLabel);
  });

  pdfExport?.addEventListener("click", () => {
    if (!currentPdfFile) return;
    const a = document.createElement("a");
    a.href = currentPdfFile;
    a.download = currentPdfFile.split("/").pop() || "report.pdf";
    a.target = "_blank";
    a.click();
  });
}

// ---------------------------------------------------------------------------
// Telemetry Wall
// ---------------------------------------------------------------------------

let dragZIndex = 100;

function makeDraggable(element, handle) {
  let isDragging = false;
  let startX = 0;
  let startY = 0;
  let initialLeft = 0;
  let initialTop = 0;

  handle.addEventListener('mousedown', (e) => {
    isDragging = true;
    startX = e.clientX;
    startY = e.clientY;
    const rect = element.getBoundingClientRect();
    element.style.transform = '';
    element.style.left = `${rect.left}px`;
    element.style.top = `${rect.top}px`;
    initialLeft = rect.left;
    initialTop = rect.top;
    element.classList.add('dragging');
    element.style.zIndex = ++dragZIndex;
    e.preventDefault();
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    element.style.left = `${initialLeft + dx}px`;
    element.style.top = `${initialTop + dy}px`;
  });

  document.addEventListener('mouseup', () => {
    if (isDragging) {
      isDragging = false;
      element.classList.remove('dragging');
    }
  });
}

function getColumnCount(width) {
  if (width >= 1400) return 3;
  if (width >= 1100) return 3;
  if (width >= 800) return 3;
  if (width >= 520) return 2;
  return 1;
}

function renderTelemetry(runs) {
  const wall = document.getElementById('telemetry-wall');
  if (!wall) return;
  if (!runs.length) {
    wall.innerHTML = '';
    wall.style.display = 'none';
    return;
  }
  wall.style.display = 'grid';

  wall.innerHTML = runs.map((run) => {
    const artifacts = run.artifacts || [];
    if (!artifacts.length) return '';

    const pdfArtifacts = artifacts.filter(name => name.endsWith('.pdf'));
    const otherArtifacts = artifacts.filter(name => !name.endsWith('.pdf'));

    const pairs = [];
    for (let i = 0; i < pdfArtifacts.length; i += 2) {
      pairs.push({
        left: pdfArtifacts[i] || null,
        right: pdfArtifacts[i + 1] || null,
        index: Math.floor(i / 2)
      });
    }

    const pairsHtml = pairs.map((pair) => {
      const leftUrl = pair.left ? `/reports/${encodeURIComponent(pair.left)}` : '';
      const rightUrl = pair.right ? `/reports/${encodeURIComponent(pair.right)}` : '';
      return `
        <div class="pdf-pair" data-pair="${pair.index}">
          <div class="pdf-viewer-cell" ${leftUrl ? `data-pdf-url="${escapeHtml(leftUrl)}" title="${escapeHtml(pair.left)}"` : ''}>
            ${leftUrl ? `<div class="pdf-page-stack" data-pdf-url="${escapeHtml(leftUrl)}"></div><div class="pdf-cell-overlay"><button class="pdf-cell-view" data-pdf-url="${escapeHtml(leftUrl)}" title="View full PDF">View</button></div>` : '<div class="pdf-placeholder">No PDF</div>'}
          </div>
          <div class="pdf-viewer-cell" ${rightUrl ? `data-pdf-url="${escapeHtml(rightUrl)}" title="${escapeHtml(pair.right)}"` : ''}>
            ${rightUrl ? `<div class="pdf-page-stack" data-pdf-url="${escapeHtml(rightUrl)}"></div><div class="pdf-cell-overlay"><button class="pdf-cell-view" data-pdf-url="${escapeHtml(rightUrl)}" title="View full PDF">View</button></div>` : '<div class="pdf-placeholder">No PDF</div>'}
          </div>
        </div>
      `;
    }).join('');

    const otherHtml = otherArtifacts.length ? `
      <div class="other-artifacts">
        <div class="other-artifacts-header">Other Artifacts (${otherArtifacts.length})</div>
        <div class="other-artifacts-list">
          ${otherArtifacts.map((name) => `<span class="other-artifact-item">${escapeHtml(name)}</span>`).join('')}
        </div>
      </div>
    ` : '';

    return `
      <div class="run-window" data-run="${escapeHtml(run.runId)}">
        <div class="run-window-header" data-run="${escapeHtml(run.runId)}">
          <span class="run-window-title" title="${escapeHtml(run.runId)}">${escapeHtml(run.runId)}</span>
          <span class="run-window-meta">${escapeHtml(run.type)} · ${formatDate(run.startedAt)}</span>
          <div class="run-window-actions">
            <button class="run-window-action" data-action="zip" data-run="${escapeHtml(run.runId)}" title="Save all artifacts as zip">Save All as Zip</button>
            <button class="run-window-action" data-action="download" data-run="${escapeHtml(run.runId)}" title="Download selected artifact">Download Selected</button>
            <button class="run-window-close" data-run="${escapeHtml(run.runId)}" title="Close run">×</button>
          </div>
        </div>
        <div class="run-window-body">
          ${pairs.length ? `
          <div class="pdf-pair-scroll" data-run="${escapeHtml(run.runId)}">
            ${pairsHtml}
          </div>
          ${pairs.length > 1 ? `
          <div class="pdf-pair-nav">
            <button class="pdf-pair-prev secondary" data-run="${escapeHtml(run.runId)}" title="Previous pair">◀ Prev</button>
            <span class="pdf-pair-indicator" data-run="${escapeHtml(run.runId)}">1 / ${pairs.length}</span>
            <button class="pdf-pair-next secondary" data-run="${escapeHtml(run.runId)}" title="Next pair">Next ▶</button>
          </div>
          ` : ''}
          ` : '<div class="no-pdfs">No PDF artifacts</div>'}
          ${otherHtml}
        </div>
      </div>
    `;
  }).join('');

  // Make run windows draggable
  wall.querySelectorAll('.run-window').forEach((win) => {
    const header = win.querySelector('.run-window-header');
    if (header) makeDraggable(win, header);
  });

  // Navigation buttons
  wall.querySelectorAll('.pdf-pair-prev, .pdf-pair-next').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const runId = btn.dataset.run;
      const scrollContainer = wall.querySelector(`.pdf-pair-scroll[data-run="${runId}"]`);
      if (!scrollContainer) return;
      const pairEl = scrollContainer.querySelector('.pdf-pair');
      const pairWidth = pairEl ? pairEl.offsetWidth : scrollContainer.offsetWidth;
      const direction = btn.classList.contains('pdf-pair-prev') ? -1 : 1;
      scrollContainer.scrollBy({ left: pairWidth * direction, behavior: 'smooth' });
    });
  });

  // Update indicators on scroll
  wall.querySelectorAll('.pdf-pair-scroll').forEach((container) => {
    container.addEventListener('scroll', () => {
      const runId = container.dataset.run;
      const pairEl = container.querySelector('.pdf-pair');
      const pairWidth = pairEl ? pairEl.offsetWidth : container.offsetWidth;
      const currentIndex = Math.round(container.scrollLeft / pairWidth) + 1;
      const totalPairs = container.querySelectorAll('.pdf-pair').length;
      const indicator = wall.querySelector(`.pdf-pair-indicator[data-run="${runId}"]`);
      if (indicator) indicator.textContent = `${Math.max(1, currentIndex)} / ${totalPairs}`;
    });
  });

  // Run window action buttons
  wall.querySelectorAll('.run-window-action').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const runId = btn.dataset.run;
      const action = btn.dataset.action;
      if (action === 'zip') {
        await downloadRunZip(runId);
      } else if (action === 'download') {
        await downloadCurrentArtifact(runId);
      }
    });
  });

  // Run window close buttons - no confirm, direct delete
  wall.querySelectorAll('.run-window-close').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const runId = btn.dataset.run;
      await fetch(`/api/telemetry/runs/${encodeURIComponent(runId)}`, { method: 'DELETE' });
      if (currentSelection && currentSelection.runId === runId) {
        currentSelection = null;
      }
      sendWs({ action: 'list_telemetry' });
    });
  });

  // PDF viewer cell clicks -> select artifact for download and open modal
  wall.querySelectorAll('.pdf-viewer-cell').forEach((cell) => {
    cell.addEventListener('click', (e) => {
      e.stopPropagation();
      const runId = cell.closest('.run-window')?.dataset.run;
      if (!runId) return;
      const pair = cell.closest('.pdf-pair');
      const pairIndex = pair ? parseInt(pair.dataset.pair || '0', 10) : 0;
      const cells = pair ? Array.from(pair.querySelectorAll('.pdf-viewer-cell')) : [];
      const cellIndex = cells.indexOf(cell);
      const stack = cell.querySelector('.pdf-page-stack');
      const url = stack ? stack.dataset.pdfUrl : '';
      const name = url ? url.split('/').pop() || '' : '';

      currentSelection = { runId, index: pairIndex * 2 + cellIndex, url, type: 'PDF', name };

      wall.querySelectorAll('.pdf-viewer-cell.selected').forEach(c => c.classList.remove('selected'));
      cell.classList.add('selected');

      if (url) {
        openPdfModal(url);
      }
    });
  });

  // PDF view buttons -> open modal viewer
  wall.querySelectorAll('.pdf-cell-view').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const url = btn.dataset.pdfUrl;
      if (url) {
        openPdfModal(url);
      }
    });
  });

  // Header click -> expand run window
  wall.querySelectorAll('.run-window-header').forEach((header) => {
    header.addEventListener('click', (e) => {
      if (e.target.closest('.run-window-actions')) return;
      const runId = header.dataset.run;
      expandRunWindow(runId);
    });
  });

  // Render PDF pages into stacks asynchronously via PDF.js
  wall.querySelectorAll('.pdf-page-stack').forEach(async (stack) => {
    const url = stack.dataset.pdfUrl;
    if (url) {
      await renderPdfPagesToContainer(url, stack);
    }
  });
}

function expandRunWindow(runId) {
  const expanded = document.getElementById('telemetry-expanded');
  const titleEl = document.getElementById('telemetry-expanded-title');
  const bodyEl = document.getElementById('telemetry-expanded-body');
  if (!expanded || !titleEl || !bodyEl) return;

  const run = telemetryRuns.find(r => r.runId === runId);
  if (!run) return;

  titleEl.textContent = `${run.runId} - ${run.type} · ${formatDate(run.startedAt)}`;

  const artifacts = run.artifacts || [];
  const pdfArtifacts = artifacts.filter(name => name.endsWith('.pdf'));
  const otherArtifacts = artifacts.filter(name => !name.endsWith('.pdf'));

  if (!pdfArtifacts.length && !otherArtifacts.length) {
    bodyEl.innerHTML = '<div class="empty-items">No artifacts recorded</div>';
  } else {
    const pairs = [];
    for (let i = 0; i < pdfArtifacts.length; i += 2) {
      pairs.push({
        left: pdfArtifacts[i] || null,
        right: pdfArtifacts[i + 1] || null,
        index: Math.floor(i / 2)
      });
    }

    const pairsHtml = pairs.map((pair) => {
      const leftUrl = pair.left ? `/reports/${encodeURIComponent(pair.left)}` : '';
      const rightUrl = pair.right ? `/reports/${encodeURIComponent(pair.right)}` : '';
      return `
        <div class="pdf-pair" data-pair="${pair.index}">
          <div class="pdf-viewer-cell expanded">
            ${leftUrl ? `<div class="expanded-pdf-container" data-pdf-url="${escapeHtml(leftUrl)}"></div>` : ''}
          </div>
          <div class="pdf-viewer-cell expanded">
            ${rightUrl ? `<div class="expanded-pdf-container" data-pdf-url="${escapeHtml(rightUrl)}"></div>` : ''}
          </div>
        </div>
      `;
    }).join('');

    const otherHtml = otherArtifacts.length ? `
      <div class="other-artifacts expanded-other">
        <div class="other-artifacts-header">Other Artifacts (${otherArtifacts.length})</div>
        <div class="other-artifacts-list">
          ${otherArtifacts.map((name) => `<span class="other-artifact-item">${escapeHtml(name)}</span>`).join('')}
        </div>
      </div>
    ` : '';

    bodyEl.innerHTML = `
      ${pairs.length ? `
      <div class="expanded-pdf-pair-scroll" data-run="${escapeHtml(runId)}">
        ${pairsHtml}
      </div>
      ${pairs.length > 1 ? `
      <div class="pdf-pair-nav expanded-nav">
        <button class="pdf-pair-prev secondary" data-run="${escapeHtml(runId)}" title="Previous pair">◀ Prev</button>
        <span class="pdf-pair-indicator" data-run="${escapeHtml(runId)}">1 / ${pairs.length}</span>
        <button class="pdf-pair-next secondary" data-run="${escapeHtml(runId)}" title="Next pair">Next ▶</button>
      </div>
      ` : ''}
      ` : ''}
      ${otherHtml}
    `;
  }

  expanded.classList.add('show');
  const backdrop = document.getElementById('telemetry-backdrop');
  if (backdrop) backdrop.classList.add('show');

  // Render full PDFs in expanded view via PDF.js
  bodyEl.querySelectorAll('.expanded-pdf-container').forEach(async (container) => {
    const url = container.dataset.pdfUrl;
    if (url) {
      await renderFullPdfToContainer(url, container);
    }
  });
}

function collapseRunWindow() {
  const expanded = document.getElementById('telemetry-expanded');
  const backdrop = document.getElementById('telemetry-backdrop');
  if (expanded) expanded.classList.remove('show');
  if (backdrop) backdrop.classList.remove('show');
}

async function downloadRunZip(runId) {
  const url = `/api/telemetry/runs/${encodeURIComponent(runId)}/zip`;
  const a = document.createElement('a');
  a.href = url;
  a.download = `${runId}.zip`;
  a.target = '_blank';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

async function downloadCurrentArtifact(runId) {
  if (!currentSelection || currentSelection.runId !== runId) {
    return;
  }
  const url = currentSelection.url;
  if (!url || url.startsWith('#')) {
    return;
  }
  const a = document.createElement('a');
  a.href = url;
  a.download = currentSelection.name || 'artifact';
  a.target = '_blank';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function applyEndpointAvailability(statuses) {
  statuses.forEach((s) => {
    const ep = endpoints.find((e) => e.id === s.id);
    if (ep) {
      ep.available = s.available;
    }
  });
  renderEndpoints();
  refreshModelDropdown();
  refreshModelEndpointOptions();
}

function initTelemetry() {
  const refreshBtn = document.getElementById('refresh-telemetry');
  const clearBtn = document.getElementById('clear-telemetry');
  const backdrop = document.getElementById('telemetry-backdrop');
  const expandedClose = document.getElementById('telemetry-expanded-close');
  const modalClose = document.getElementById('pdf-modal-close');
  const modalZoomIn = document.getElementById('pdf-modal-zoom-in');
  const modalZoomOut = document.getElementById('pdf-modal-zoom-out');
  const modalBody = document.querySelector('.pdf-modal-body');

  refreshBtn?.addEventListener('click', () => {
    sendWs({ action: 'list_telemetry' });
  });

  clearBtn?.addEventListener('click', async () => {
    await fetch('/api/telemetry/runs', { method: 'DELETE' });
    currentSelection = null;
    sendWs({ action: 'list_telemetry' });
  });

  // Close expanded view
  expandedClose?.addEventListener('click', collapseRunWindow);
  backdrop?.addEventListener('click', () => {
    collapseRunWindow();
    backdrop.classList.remove('show');
  });

  // Close PDF modal
  modalClose?.addEventListener('click', closePdfModal);
  modalZoomIn?.addEventListener('click', (e) => {
    e.stopPropagation();
    modalZoomIn();
  });
  modalZoomOut?.addEventListener('click', (e) => {
    e.stopPropagation();
    modalZoomOut();
  });

  // Ctrl+scroll zoom in modal
  modalBody?.addEventListener('wheel', (e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.1 : -0.1;
    if (e.deltaY < 0) {
      modalZoomIn();
    } else {
      modalZoomOut();
    }
  }, { passive: false });

  // Close modals on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closePdfModal();
      collapseRunWindow();
      if (backdrop) backdrop.classList.remove('show');
    }
  });

  // Navigation for expanded view
  document.body.addEventListener('click', (e) => {
    const target = e.target;
    if (target.classList.contains('pdf-pair-prev') || target.classList.contains('pdf-pair-next')) {
      e.stopPropagation();
      const runId = target.dataset.run;
      const scrollContainer = document.querySelector(`.expanded-pdf-pair-scroll[data-run="${runId}"]`);
      if (!scrollContainer) return;
      const pairEl = scrollContainer.querySelector('.pdf-pair');
      const pairWidth = pairEl ? pairEl.offsetWidth : scrollContainer.offsetWidth;
      const direction = target.classList.contains('pdf-pair-prev') ? -1 : 1;
      scrollContainer.scrollBy({ left: pairWidth * direction, behavior: 'smooth' });
    }
  });
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

function init() {
  initTabs();
  initDirectionButtons();
  initHelpIcons();
  initEndpoints();
  initModels();
  initGenerateReports();
  initFaultInjection();
  initReports();
  initTelemetry();
  renderEndpoints();
  refreshModelEndpointOptions();
  renderModels();
  renderReports([]);
  renderTelemetry([]);
  sendWs({ action: "list_endpoints" });
  sendWs({ action: "list_models" });
  sendWs({ action: "list_reports" });
  sendWs({ action: "list_telemetry" });
  sendWs({ action: "list_prompt_packages" });
  sendWs({ action: "endpoints_status" });
  connectWebSocket();
}

document.addEventListener("DOMContentLoaded", init);
