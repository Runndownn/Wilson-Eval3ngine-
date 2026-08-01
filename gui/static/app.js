/* Wilson Eval3ngine GUI */

// State
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
const pdfPairs = {}; // { "left-0": { doc, currentPage, url }, "right-0": { doc, currentPage, url } }
let currentJobId = localStorage.getItem("we3.currentJobId") || null;
let currentRunId = localStorage.getItem("we3.currentRunId") || null;
let modelsLastFetchedAt = null;  // Timestamp of last auto_detect_models
let modelsRefreshTimer = null;   // Interval for live "N seconds ago" update

let activeJobStatus = null;
let rateLimited = false;
let searchDebounceTimer = null;

// --- Progress dashboard module-level state ---
// The dashboard used to rewrite the entire model-card grid on every
// WebSocket message, causing visible flicker and DOM thrash on
// completed models. These caches let us do keyed DOM updates and
// freeze finished cards.
let modelCardCache = {};
let modelStatusCache = {};
let modelPercentageCache = {};
let modelTimers = {};

// Charts tab state
let chartRunsCache = [];
let chartMetadataCache = {};
let chartOrderCache = [];
let chartCardCache = {};
let chartStatusCache = {};
let chartGenerationActive = false;
let chartGenerationTotal = 0;
let chartGenerationDone = 0;
let chartGenerationRunId = '';

// Utility functions
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function isRateLimitError(text) {
    const base = (text || "").toLowerCase();
    return base.includes("429") || base.includes("rate limit") || base.includes("too many requests") || base.includes("throttl");
}

function updateRateLimitStatus() {
    const generateEl = document.getElementById("generate-rate-limit-status");
    const modelsEl = document.getElementById("models-rate-limit-status");
    const show = rateLimited;
    if (generateEl) generateEl.classList.toggle("hidden", !show);
    if (modelsEl) modelsEl.classList.toggle("hidden", !show);
}

function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
    if (!iso) return "";
    try {
        const d = new Date(iso);
        return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
}

function sendWs(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
    } else {
        console.warn("WebSocket not open, message not sent:", message.action);
    }
}

// WebSocket connection
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
        // Send initial data fetches only after WebSocket is fully open
        sendWs({ action: "list_endpoints" });
        sendWs({ action: "auto_detect_models" });
        sendWs({ action: "list_reports" });
        sendWs({ action: "list_prompt_packages" });
        
        // Restore active job state on reconnection
        if (currentJobId) {
            sendWs({ action: "get_job", job_id: currentJobId });
        }
    };
    ws.onclose = () => {
        statusEl?.classList.replace("badge-online", "badge-offline");
        if (statusEl) statusEl.textContent = "Offline";
        // Re-fetch all data after reconnecting
        setTimeout(() => {
            connectWebSocket();
            // Data fetches will happen in the new ws.onopen
        }, 2000);
    };
    ws.onerror = () => {
        statusEl?.classList.replace("badge-online", "badge-offline");
        if (statusEl) statusEl.textContent = "Error";
    };
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (e) {
            console.error("WebSocket parse error:", e);
        }
    };
}

function handleMessage(message) {
    if (message.action === "list_reports") {
        console.error('[PDF] list_reports received', { reportCount: message.reports?.length, runCount: message.reportRuns?.length });
        renderReports(message.reports || [], message.reportRuns || []);
        // Show "View Reports" link only when real PDF reports exist
        const hasReports = (message.reports?.length > 0) || (message.reportRuns?.length > 0);
        updateViewReportsLink(hasReports);
    }
    if (message.action === "generate_reports") {
        const output = document.getElementById("report-output");
        if (message.status === "started") {
            currentJobId = message.job_id || currentJobId;
            currentRunId = message.runId || currentRunId;
            if (currentJobId) localStorage.setItem("we3.currentJobId", currentJobId);
            if (currentRunId) localStorage.setItem("we3.currentRunId", currentRunId);
            if (output) output.textContent = `Generating reports... Job: ${currentJobId}`;
            showProgressDashboard();
        }
        if (message.status === "complete") {
            if (output) output.textContent = message.stdout || JSON.stringify(message, null, 2);
            hideProgressDashboard();
        }
        if (message.status === "error") {
            if (output) output.textContent = `Error: ${message.error || "Unknown"}`;
            hideProgressDashboard();
        }
        if (message.status === "skipped") {
            if (output) output.textContent = `Skipped: ${message.error || "Unknown"}`;
            hideProgressDashboard();
        }
    }
    if (message.action === "stop_reports") {
        if (message.status === "stopped" || message.status === "no_generation_running") {
            hideProgressDashboard();
            const output = document.getElementById("report-output");
            if (output) output.textContent = message.status === "stopped" ? "Report generation stopped." : "No generation was running.";
        }
    }
    if (message.action === "job_created") {
        currentJobId = message.job_id || currentJobId;
        currentRunId = message.run_id || currentRunId;
        if (currentJobId) localStorage.setItem("we3.currentJobId", currentJobId);
        if (currentRunId) localStorage.setItem("we3.currentRunId", currentRunId);
        activeJobStatus = message.status;
        showProgressDashboard();
        updateProgressDashboard(message);
    }
    if (message.action === "job_progress") {
        currentJobId = message.job_id || currentJobId;
        currentRunId = message.run_id || currentRunId;
        activeJobStatus = message.status || activeJobStatus;
        updateProgressDashboard(message);
    }
    if (message.action === "job_complete") {
        currentJobId = message.job_id || currentJobId;
        currentRunId = message.run_id || currentRunId;
        activeJobStatus = message.status;
        updateProgressDashboard(message);
        const output = document.getElementById("report-output");
        if (output) output.textContent = `Generation complete. Status: ${message.status}`;
        showProgressActions(message.status);
        // Refresh the Reports tab so newly generated PDFs appear immediately
        sendWs({ action: "list_reports" });
        if (message.status === "completed" || message.status === "completed_with_errors" || message.status === "failed" || message.status === "cancelled") {
            // Hide only the progress dashboard (not actions which should remain visible)
            const dashboard = document.getElementById("progress-dashboard");
            if (dashboard) dashboard.classList.add("hidden");
            currentJobId = null;
            currentRunId = null;
            activeJobStatus = null;
            localStorage.removeItem("we3.currentJobId");
            localStorage.removeItem("we3.currentRunId");
        }
    }
    if (message.action === "job_error") {
        currentJobId = message.job_id || currentJobId;
        currentRunId = message.run_id || currentRunId;
        activeJobStatus = message.status;
        updateProgressDashboard(message);
        const output = document.getElementById("report-output");
        if (output) output.textContent = `Error: ${message.error || "Unknown"}`;
        showProgressActions(message.status);
        hideProgressDashboard();
    }
    if (message.action === "job_cancelled") {
        currentJobId = message.job_id || currentJobId;
        currentRunId = message.run_id || currentRunId;
        activeJobStatus = message.status;
        updateProgressDashboard(message);
        const output = document.getElementById("report-output");
        if (output) output.textContent = "Report generation was cancelled.";
        showProgressActions(message.status);
        hideProgressDashboard();
    }
    if (message.action === "get_job") {
        if (message.status === "ok" && message.job) {
            currentJobId = message.job.job_id || currentJobId;
            currentRunId = message.job.run_id || currentRunId;
            if (currentJobId) localStorage.setItem("we3.currentJobId", currentJobId);
            if (currentRunId) localStorage.setItem("we3.currentRunId", currentRunId);
            activeJobStatus = message.status || message.job.status || activeJobStatus;
            showProgressDashboard();
            updateProgressDashboard(message);
            const output = document.getElementById("report-output");
            if (output) output.textContent = `Restored job ${currentJobId}: ${getStatusLabel(activeJobStatus)}`;
            showProgressActions(message.job.status);
        } else if (message.status === "error") {
            hideProgressDashboard();
        }
    }
    if (message.action === "list_endpoints") {
        endpoints.length = 0;
        endpoints.push(...(message.endpoints || []));
        renderEndpoints();
        refreshModelEndpointOptions();
        populateModelDropdown();
    }
    if (message.action === "list_models") {
        models.length = 0;
        models.push(...(message.models || []));
        renderModels();
        updateModelChips();
        populateModelDropdown();
    }
    if (message.action === "list_prompt_packages") {
        promptPackages = message.packages || [];
        populatePromptPackageSelect();
    }
    if (message.action === "test_endpoint") {
        const statusEl = document.getElementById("login-status");
        if (statusEl) {
            if (message.ok) {
                statusEl.textContent = `Connection OK - ${message.models?.length || 0} models found`;
                statusEl.className = "status-message success";
                rateLimited = false;
            } else {
                const errorMsg = message.error || message.details || "Connection failed - check URL and provider";
                statusEl.textContent = `Test failed: ${errorMsg}`;
                statusEl.className = "status-message error";
                if (isRateLimitError(errorMsg)) {
                    rateLimited = true;
                } else {
                    rateLimited = false;
                }
            }
            updateRateLimitStatus();
        }
        // Refresh model dropdown after successful test (models may have changed)
        if (message.ok && message.models) {
            populateModelDropdown();
        }
    }
    if (message.action === "auto_detect_endpoints") {
        const statusEl = document.getElementById("login-status");
        if (statusEl) {
            const count = (message.endpoints || []).length;
            statusEl.textContent = `Auto-detected ${count} endpoint${count !== 1 ? 's' : ''}`;
            statusEl.className = "status-message success";
        }
        // Update endpoints list from the response (includes CLI endpoints)
        if (message.all_endpoints) {
            endpoints.length = 0;
            endpoints.push(...message.all_endpoints);
            renderEndpoints();
            refreshModelEndpointOptions();
            populateModelDropdown();
        } else {
            // Fallback: refresh endpoints list after auto-detect
            sendWs({ action: "list_endpoints" });
        }
    }
    if (message.action === "auto_detect_models") {
        // Refresh models list after auto-detect
        sendWs({ action: "list_models" });
    }
    if (message.action === "endpoints_status") {
        applyEndpointAvailability(message.statuses || []);
    }
    // Handle login responses for all providers (kilo, nvidia, ollama, codex)
    if (["kilo_login", "nvidia_login", "ollama_login", "codex_login"].includes(message.action)) {
        const statusEl = document.getElementById("login-status");
        if (statusEl) {
            if (message.ok) {
                statusEl.textContent = message.message || `${message.provider || 'Provider'} reachable: ${message.models?.length || 0} models found`;
                statusEl.className = "status-message success";
                rateLimited = false;
            } else {
                statusEl.textContent = `Login failed: ${message.error || "Unknown error"}`;
                statusEl.className = "status-message error";
                if (isRateLimitError(message.error || "")) {
                    rateLimited = true;
                } else {
                    rateLimited = false;
                }
            }
            updateRateLimitStatus();
        }
        // Refresh endpoints and models after successful login so the new endpoint appears
        if (message.ok) {
            sendWs({ action: "list_endpoints" });
            sendWs({ action: "auto_detect_models" });
        }
    }
    if (message.action === "list_chart_runs") {
        chartRunsCache = message.runs || [];
        renderChartsGallery(chartRunsCache);
    }
    if (message.action === "chart_metadata") {
        chartMetadataCache = message.charts || {};
        chartOrderCache = message.order || [];
        renderChartsGallery(chartRunsCache);
    }
    if (message.action === "chart_progress") {
        updateChartGenerationProgress(message);
    }
     if (message.action === "generate_charts") {
        chartGenerationActive = false;
        if (message.charts) {
            const runId = message.runId || chartGenerationRunId || "test-run-final";
            // Use server's isSample flag — trust it over runId name
            const isSample = message.isSample === true;
            const charts = Object.entries(message.charts).map(([name, url]) => ({
                name,
                displayName: (chartMetadataCache[name] || {}).name || name,
                description: (chartMetadataCache[name] || {}).description || "",
                category: (chartMetadataCache[name] || {}).category || "General",
                url,
                size_bytes: 0,
            }));
            const existing = chartRunsCache.find(r => r.runId === runId);
            if (existing) {
                existing.charts = charts;
                existing.isSample = isSample;
            } else {
                chartRunsCache.push({
                    runId, type: isSample ? "sample_generation" : "report_generation",
                    models: [], prompts: [], charts, isSample,
                });
            }
            renderChartsGallery(chartRunsCache);
        }
        showChartStatus(`Generated ${message.generated || 0} of ${message.total || 0} charts`, false);
    }
}

// Tabs
function initTabs() {
    const tabs = document.querySelectorAll(".tab-link");
    const panels = document.querySelectorAll(".tab-panel");
    const savedTab = localStorage.getItem("we3.activeTab");
    const defaultTab = savedTab || (tabs[0] && (tabs[0].dataset.tab)) || "tab-endpoints";
    
    // Apply initial active state
    tabs.forEach((tab) => {
        const target = tab.dataset.tab || "";
        if (target === defaultTab) {
            tab.classList.add("active");
            const panel = document.getElementById(target);
            if (panel) panel.classList.add("active");
        }
    });

    tabs.forEach((tab) => {
        const target = tab.dataset.tab || "";
        tab.addEventListener("click", () => {
            tabs.forEach((t) => t.classList.remove("active"));
            panels.forEach((p) => p.classList.remove("active"));
            const target = tab.dataset.tab || "";
            tab.classList.add("active");
            const panel = document.getElementById(target);
            if (panel) panel.classList.add("active");
            localStorage.setItem("we3.activeTab", target);
            if (target === "tab-generate") {
                restoreProgressIfActive();
            }
        });
    });
}

// Programmatically switch to a tab (used by links and cross-tab navigation)
function switchToTab(tabId) {
    const tab = document.querySelector(`.tab-link[data-tab="${tabId}"]`);
    if (tab) {
        tab.click();
    }
}

// Direction buttons (help text toggles)
function initDirectionButtons() {
    document.querySelectorAll(".direction-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const target = btn.dataset.target;
            const targetEl = document.getElementById(target);
            if (targetEl) {
                targetEl.classList.toggle("show");
                btn.classList.toggle("active");
            }
        });
    });
}

// Help icons
function initHelpIcons() {
    document.querySelectorAll(".help-icon").forEach((icon) => {
        icon.addEventListener("mouseenter", (e) => {
            const target = icon.dataset.help;
            const tooltip = document.getElementById(target);
            if (tooltip) tooltip.classList.add("show");
        });
        icon.addEventListener("mouseleave", (e) => {
            const target = icon.dataset.help;
            const tooltip = document.getElementById(target);
            if (tooltip) tooltip.classList.remove("show");
        });
    });
}

// Endpoints
function initEndpoints() {
    const form = document.getElementById("endpoint-form");
    const urlSelect = document.getElementById("endpoint-url");
    const urlCustom = document.getElementById("endpoint-url-custom");
    const testBtn = document.getElementById("test-endpoint");
    const autoDetectBtn = document.getElementById("auto-detect-endpoints");
    
    // Preset URL values map to (display URL, provider). Choosing a preset
    // pre-fills the URL field, provider dropdown, and helps the operator
    // understand which authentication is required.
    const PRESETS = {
        "__nvidia__": {
            url: "https://integrate.api.nvidia.com/v1",
            provider: "nvidia",
            needsApiKey: true,
            apiKeyHint: "nvapi-...",
        },
        "__kilo__": {
            url: "https://api.kilo.ai/api/gateway",
            provider: "kilo",
            needsApiKey: false,  // OAuth via CLI works too
            apiKeyHint: "Bearer token (optional — Login button also works)",
        },
        "__ollama__": {
            url: "http://localhost:11434",
            provider: "ollama",
            needsApiKey: false,
            apiKeyHint: "Not required for local Ollama",
        },
        "__codex__": {
            url: "cli://codex",
            provider: "codex_cli",
            needsApiKey: false,
            apiKeyHint: "Not required for Codex CLI",
        },
    };

    function applyPreset(value) {
        const preset = PRESETS[value];
        if (preset) {
            const providerSelect = document.getElementById("endpoint-provider");
            if (providerSelect) providerSelect.value = preset.provider;
            showLoginForProvider(preset.provider);
            if (urlCustom) {
                urlCustom.classList.remove("hidden");
                urlCustom.value = preset.url;
                urlCustom.focus();
            }
            // Update status message to guide the user
            const status = document.getElementById("endpoint-status");
            if (status) {
                let msg = `Selected ${preset.provider} preset. URL: ${preset.url}`;
                if (preset.needsApiKey) {
                    msg += ` Enter your API key (starts with ${preset.apiKeyHint}) and click Login.`;
                } else {
                    msg += ` ${preset.apiKeyHint}. Click Login to test connectivity.`;
                }
                status.textContent = msg;
                status.className = "status-message status-info";
            }
        }
    }

    urlSelect?.addEventListener("change", () => {
        const v = urlSelect.value;
        if (v === "__custom__") {
            urlCustom?.classList.remove("hidden");
            urlCustom?.focus();
        } else if (PRESETS[v]) {
            applyPreset(v);
        } else {
            urlCustom?.classList.add("hidden");
        }
    });
    
    form?.addEventListener("submit", (e) => {
        e.preventDefault();
        const nameInput = document.getElementById("endpoint-name");
        const apiKeyInput = document.getElementById("endpoint-api-key");
        const providerInput = document.getElementById("endpoint-provider");

        // Resolve URL: if a preset was selected, use its mapped URL even if
        // the custom field was populated by the preset handler.
        let url = "";
        const preset = PRESETS[urlSelect.value];
        if (preset) {
            url = preset.url;
        } else if (urlSelect.value === "__custom__") {
            url = urlCustom?.value || "";
        } else {
            url = urlSelect.value;
        }

        if (!url) {
            showEndpointStatus("Please pick a preset or enter a custom URL", true);
            return;
        }

        sendWs({
            action: "create_endpoint",
            name: nameInput?.value || "Unnamed",
            url: url,
            apiKey: apiKeyInput?.value || null,
            provider: providerInput?.value || "ollama",
        });

        // Show guided next-step message
        showEndpointStatus(
            `Endpoint saved. Switch to the Models tab and click Auto-Detect to pull the available models.`,
            false
        );

        form.reset();
        urlCustom?.classList.add("hidden");
        sendWs({ action: "list_endpoints" });
    });

    function showEndpointStatus(text, isError) {
        const status = document.getElementById("endpoint-status");
        if (!status) return;
        status.textContent = text;
        status.className = "status-message " + (isError ? "status-error" : "status-info");
    }
    
    testBtn?.addEventListener("click", () => {
        const url = urlSelect.value === "__custom__" 
            ? urlCustom?.value 
            : urlSelect.value;
        if (!url || url === "__custom__") return;
        sendWs({ 
            action: "test_endpoint",
            url: url,
            provider: document.getElementById("endpoint-provider")?.value || "ollama",
            apiKey: document.getElementById("endpoint-api-key")?.value || null,
        });
    });
    
    autoDetectBtn?.addEventListener("click", () => {
        sendWs({ action: "auto_detect_endpoints" });
    });
    
    // --- Provider login buttons ---
    // Each provider gets its own Login button. The button visible depends on
    // the provider selected in the dropdown. When clicked, it sends a
    // provider-specific WebSocket action that tests connectivity and persists
    // the endpoint on success.
    const loginButtons = {
        kilo: document.getElementById("login-kilo"),
        nvidia: document.getElementById("login-nvidia"),
        ollama: document.getElementById("login-ollama"),
        codex_cli: document.getElementById("login-codex"),
    };
    const loginStatus = document.getElementById("login-status");
    const providerSelect = document.getElementById("endpoint-provider");
    const apiKeyInput = document.getElementById("endpoint-api-key");
    
    function showLoginForProvider(provider) {
        Object.entries(loginButtons).forEach(([p, btn]) => {
            if (btn) btn.classList.toggle("hidden", p !== provider);
        });
    }
    
    function resolveLoginUrl(provider) {
        // Use the URL from the endpoint form if a preset or custom URL was entered
        const preset = PRESETS[urlSelect.value];
        if (preset && preset.provider === provider) {
            return preset.url;
        }
        if (urlSelect.value === "__custom__") {
            return urlCustom?.value || "";
        }
        // Fall back to provider defaults
        const defaults = {
            kilo: "https://api.kilo.ai/api/gateway",
            nvidia: "https://integrate.api.nvidia.com/v1",
            ollama: "http://localhost:11434",
            codex_cli: "cli://codex",
        };
        return defaults[provider] || "";
    }
    
    function handleProviderLogin(provider) {
        const url = resolveLoginUrl(provider);
        const apiKey = apiKeyInput?.value || null;
        const wsAction = `${provider}_login`;
        
        // Show a pending status
        if (loginStatus) {
            loginStatus.textContent = `Logging in to ${provider}...`;
            loginStatus.className = "status-message status-info";
        }
        
        sendWs({
            action: wsAction,
            url: url,
            apiKey: apiKey,
        });
    }
    
    // Wire up each login button
    Object.entries(loginButtons).forEach(([provider, btn]) => {
        btn?.addEventListener("click", () => handleProviderLogin(provider));
    });
    
    // Show the login button for the currently selected provider
    providerSelect?.addEventListener("change", () => {
        showLoginForProvider(providerSelect.value);
    });
    
    // Initial display: show login button for default selected provider
    showLoginForProvider(providerSelect?.value || "ollama");
}

function renderEndpoints() {
    const list = document.getElementById("endpoints-list");
    if (!list) return;
    list.innerHTML = endpoints.map((ep, idx) => `
        <div class="list-item">
            <div>
                <div class="name">${escapeHtml(ep.name)}</div>
                <div class="meta">${escapeHtml(ep.url)}</div>
            </div>
            <div>
                <button data-endpoint-delete="${escapeHtml(ep.id)}" class="danger">Delete</button>
            </div>
        </div>
    `).join("");
    
    list.querySelectorAll("[data-endpoint-delete]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const id = btn.dataset.endpointDelete;
            sendWs({ action: "delete_endpoint", id });
            sendWs({ action: "list_endpoints" });
        });
    });
}

function refreshModelEndpointOptions() {
    const select = document.getElementById("model-endpoint");
    if (!select) return;
    select.innerHTML = endpoints.map((ep) => 
        `<option value="${escapeHtml(ep.id)}">${escapeHtml(ep.name)}</option>`
    ).join("");
}

function applyEndpointAvailability(statuses) {
    statuses.forEach((s) => {
        const ep = endpoints.find((e) => e.id === s.id);
        if (ep) {
            ep.available = s.available;
        }
    });
    renderEndpoints();
}

// Models
function populateModelDropdown() {
    const select = document.getElementById("model-id");
    if (!select) return;
    
    const selectedEndpointId = document.getElementById("model-endpoint")?.value;
    const modelOptions = [];
    const seenModels = new Set();
    
    for (const ep of endpoints) {
        // Include endpoints that are available (true) or untested CLI endpoints (null)
        if (ep.available !== true && ep.available !== null) continue;
        
        // If an endpoint is selected in the model-endpoint dropdown, only show models for that endpoint
        if (selectedEndpointId && ep.id !== selectedEndpointId) continue;
        
        // For all endpoint types, show models from the models array that are associated with this endpoint
        for (const m of models) {
            if (m.endpointId === ep.id && !seenModels.has(m.id)) {
                seenModels.add(m.id);
                const providerLabel = ep.provider === "ollama" ? "Ollama" : ep.provider === "openai" ? "OpenAI" : ep.provider === "kilo" ? "Kilo Gateway" : ep.provider === "claude_cli" ? "Claude CLI" : ep.provider === "kilo_cli" ? "Kilo CLI" : ep.provider === "codex_cli" ? "Codex CLI" : ep.name;
                modelOptions.push(`<option value="${escapeHtml(m.id)}">${escapeHtml(m.id)} (${escapeHtml(providerLabel)})</option>`);
            }
        }
    }
    
    select.innerHTML = `<option value="">-- Select a model --</option>` + 
        modelOptions.join("") +
        `<option value="__custom__">Custom...</option>`;
}

function initModels() {
    const form = document.getElementById("model-form");
    const modelSelect = document.getElementById("model-id");
    const modelCustom = document.getElementById("model-id-custom");
    const endpointSelect = document.getElementById("model-endpoint");
    
    // Handle endpoint select change - refresh model list to show only models for selected endpoint
    endpointSelect?.addEventListener("change", () => {
        populateModelDropdown();
    });
    
    // Handle model select change - show custom input if Custom selected
    modelSelect?.addEventListener("change", () => {
        if (modelSelect.value === "__custom__") {
            if (modelCustom) modelCustom.classList.remove("hidden");
            modelCustom?.focus();
        } else {
            if (modelCustom) modelCustom.classList.add("hidden");
        }
    });
    
    form?.addEventListener("submit", (e) => {
        e.preventDefault();
        const modelId = modelSelect?.value === "__custom__"
            ? (modelCustom?.value || "")
            : modelSelect?.value;
        if (!modelId) return;
        
        const endpointId = document.getElementById("model-endpoint")?.value;
        sendWs({
            action: "create_model",
            id: modelId,
            endpointId: endpointId,
        });
        form.reset();
        if (modelCustom) modelCustom.classList.add("hidden");
    });
    
    const autoDetectBtn = document.getElementById("auto-detect-models");
    autoDetectBtn?.addEventListener("click", () => {
        sendWs({ action: "auto_detect_models" });
    });
}

// Resolve the display name for a model's endpoint. Priority:
//   1. endpointName already enriched by the server (most reliable)
//   2. Live endpoint lookup by endpointId
//   3. Provider field from the model itself
//   4. URL hint from endpointId
//   5. "Unknown" with the raw id so the operator can debug
function resolveEndpointDisplay(m, endpoints) {
    if (m.endpointName) return { name: m.endpointName, provider: m.provider || m.endpointProvider || "unknown" };
    const ep = endpoints.find(e => e.id === m.endpointId);
    if (ep && ep.name) return { name: ep.name, provider: ep.provider || m.provider || "unknown" };
    if (m.provider) {
        const nice = m.provider.charAt(0).toUpperCase() + m.provider.slice(1);
        return { name: `${nice} (endpoint not found)`, provider: m.provider };
    }
    if (m.endpointId && (m.endpointId.startsWith("http") || m.endpointId.startsWith("https"))) {
        try {
            const host = new URL(m.endpointId).hostname;
            return { name: host, provider: "unknown" };
        } catch (_) {}
    }
    return { name: `Unknown (id: ${m.endpointId || "?"})`, provider: "unknown" };
}

function formatRelativeTime(isoTs) {
    if (!isoTs) return "never";
    const then = new Date(isoTs).getTime();
    if (isNaN(then)) return "unknown";
    const diff = Math.max(0, (Date.now() - then) / 1000);
    if (diff < 5) return "just now";
    if (diff < 60) return `${Math.floor(diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return new Date(isoTs).toLocaleString();
}

function wireRefreshButton() {
    const btn = document.getElementById("models-refresh-now");
    if (!btn) return;
    btn.onclick = () => {
        btn.disabled = true;
        btn.textContent = "Refreshing...";
        sendWs({ action: "auto_detect_models" });
        // Re-enable after a short timeout in case the WS is slow
        setTimeout(() => {
            btn.disabled = false;
            btn.textContent = "Refresh now";
        }, 5000);
    };
    // Start the live-update ticker that refreshes the "N seconds ago" text
    if (modelsRefreshTimer) clearInterval(modelsRefreshTimer);
    modelsRefreshTimer = setInterval(() => {
        const stamp = document.querySelector(".models-refresh-stamp");
        if (stamp && modelsLastFetchedAt) {
            stamp.textContent = `Last refreshed: ${formatRelativeTime(modelsLastFetchedAt)}`;
        }
    }, 1000);
}

function getModelFamily(modelId) {
    let base = modelId.replace(/:latest$/, '');
    const colonIdx = base.indexOf(':');
    if (colonIdx > 0) return base.substring(0, colonIdx);
    return base;
}

function isFreeModel(modelId) {
    const base = (modelId || '').toLowerCase();
    return base.includes('-free') || base.includes(' free ') || base.endsWith(' free') || base.includes('(free)');
}

function sortModelsForColumnLayout(models) {
    return [...models].sort((a, b) => {
        const aFree = isFreeModel(a.id) ? 0 : 1;
        const bFree = isFreeModel(b.id) ? 0 : 1;
        if (aFree !== bFree) return aFree - bFree;
        return a.id.localeCompare(b.id);
    });
}

function groupModelsByEndpointAndFamily(models, endpoints) {
    const groups = {};
    for (const m of models) {
        const ep = endpoints.find(e => e.id === m.endpointId);
        const endpointName = ep ? ep.name : 'Unknown Endpoint';
        const endpointProvider = ep ? ep.provider : 'unknown';
        const family = getModelFamily(m.id);
        
        const key = `${endpointName}|||${endpointProvider}`;
        if (!groups[key]) {
            groups[key] = { endpointName, endpointProvider, families: {} };
        }
        if (!groups[key].families[family]) {
            groups[key].families[family] = [];
        }
        groups[key].families[family].push(m);
    }
    return groups;
}

function renderModels() {
    const grouped = document.getElementById("models-grouped-container");
    if (!grouped) return;

    // Show a live "last refreshed" indicator so the operator knows how fresh
    // the model list is. Updates automatically via the modelsLastFetchedAt
    // timestamp set after auto_detect_models or list_models responses.
    const stamp = modelsLastFetchedAt ? formatRelativeTime(modelsLastFetchedAt) : "never";
    const refreshBanner = `<div class="models-refresh-banner">
        <span class="models-refresh-stamp">Last refreshed: ${escapeHtml(stamp)}</span>
        <button id="models-refresh-now" class="secondary" type="button">Refresh now</button>
   </div>`;
    
    const freeModels = [];
    const standardModels = [];
    for (const m of models) {
        if (isFreeModel(m.id)) {
            freeModels.push(m);
        } else {
            standardModels.push(m);
        }
    }
    
    const groups = groupModelsByEndpointAndFamily(standardModels, endpoints);
    const groupEntries = Object.entries(groups).sort((a, b) => a[0].localeCompare(b[0]));
    
    if (groupEntries.length === 0 && freeModels.length === 0) {
        grouped.innerHTML = '<div class="empty-message">No models loaded. Click Auto-Detect or add models manually.</div>';
    } else {
        const familyCards = [];
        for (const [key, group] of groupEntries) {
            const familyEntries = Object.entries(group.families).sort((a, b) => a[0].localeCompare(b[0]));
            for (const [family, familyModels] of familyEntries) {
                const sorted = sortModelsForColumnLayout(familyModels);
                familyCards.push(`
                    <div class="family-card">
                        <div class="family-card-header">
                            <span class="family-card-name">${escapeHtml(family)}</span>
                            <span class="family-card-meta">${escapeHtml(group.endpointName)} · ${escapeHtml(group.endpointProvider)}</span>
                        </div>
                        <div class="family-card-models">
                            ${sorted.map(m => `
                                <div class="model-item">
                                    <span class="model-name">${escapeHtml(m.id)}</span>
                                    <button data-model-delete="${escapeHtml(m.id)}" class="danger">Delete</button>
                                </div>
                            `).join("")}
                        </div>
                    </div>
                `);
            }
        }
        
        grouped.innerHTML = `
            ${freeModels.length > 0 ? `
                <div class="free-models-section">
                    <div class="free-models-header">Free Models</div>
                    <div class="free-models-grid">
                        ${sortModelsForColumnLayout(freeModels).map(m => `
                            <div class="model-item free-model-item">
                                <span class="model-name">${escapeHtml(m.id)}</span>
                                <button data-model-delete="${escapeHtml(m.id)}" class="danger">Delete</button>
                            </div>
                        `).join("")}
                    </div>
                </div>
            ` : ""}
            ${familyCards.join("")}
        `;
    }
    
    grouped.querySelectorAll("[data-model-delete]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const id = btn.dataset.modelDelete;
            sendWs({ action: "delete_model", id });
            sendWs({ action: "list_models" });
        });
    });
}

function updateModelChips() {
    const container = document.getElementById("model-chips");
    const countEl = document.getElementById("model-chip-count");
    if (!container || !countEl) return;
    
    if (models.length === 0) {
        container.innerHTML = '<div class="empty-message">No models loaded. Click Auto-Detect or add models manually.</div>';
    } else {
        const freeModels = [];
        // Group models by endpoint name so every provider is represented.
        const endpointGroups = {};

        for (const m of models) {
            if (isFreeModel(m.id)) {
                freeModels.push(m);
                continue;
            }
            const resolved = resolveEndpointDisplay(m, endpoints);
            const epName = resolved.name;
            if (!endpointGroups[epName]) {
                endpointGroups[epName] = [];
            }
            endpointGroups[epName].push(m);
        }

        const sortAlpha = (arr) => [...arr].sort((a, b) => a.id.localeCompare(b.id));
        const chip = (m) => `
            <div class="model-chip ${selectedModelIds.has(m.id) ? "selected" : ""}" data-model-id="${escapeHtml(m.id)}">
                <input type="checkbox" ${selectedModelIds.has(m.id) ? "checked" : ""} />
                <span>${escapeHtml(m.id)}</span>
            </div>
        `;
        const col = (header, items) => items.length ? `
            <div class="model-chip-column">
                <div class="model-chip-column-header">${escapeHtml(header)}</div>
                <div class="model-chips">${sortAlpha(items).map(chip).join("")}</div>
            </div>
        ` : "";

        const groupCols = Object.entries(endpointGroups)
            .sort((a, b) => a[0].localeCompare(b[0]))
            .map(([name, items]) => col(name, items))
            .join("");

        container.innerHTML = `
            <div class="model-chip-columns">
                ${col("Free Models", freeModels)}
                ${groupCols}
            </div>
        `;
    }
    
    countEl.textContent = `${selectedModelIds.size} selected`;
    
    container.querySelectorAll(".model-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            const modelId = chip.dataset.modelId;
            if (selectedModelIds.has(modelId)) {
                selectedModelIds.delete(modelId);
            } else {
                selectedModelIds.add(modelId);
            }
            updateModelChips();
        });
    });
}

// Prompt selector
function initModelsSelector() {
    const openBtn = document.getElementById("open-models-selector");
    const modal = document.getElementById("models-selector-modal");
    const closeBtn = document.getElementById("models-selector-close");
    const confirmBtn = document.getElementById("models-confirm");
    const selectAllBtn = document.getElementById("models-select-all");
    const selectVisibleBtn = document.getElementById("models-select-visible");
    const selectNoneBtn = document.getElementById("models-select-none");
    const searchInput = document.getElementById("models-search");
    const countEl = document.getElementById("models-selected-count");
    
    const openModelSelector = () => {
        const list = document.getElementById("models-selector-list");
        if (!list) return;

        const freeModels = [];
        // Group models by their endpoint name so every provider is represented.
        const endpointGroups = {};

        for (const m of models) {
            if (isFreeModel(m.id)) {
                freeModels.push(m);
                continue;
            }
            const ep = endpoints.find(e => e.id === m.endpointId);
            const epName = ep ? ep.name : 'Unknown Endpoint';
            const epProvider = ep ? ep.provider : 'unknown';
            if (!endpointGroups[epName]) {
                endpointGroups[epName] = { name: epName, provider: epProvider, models: [] };
            }
            endpointGroups[epName].models.push(m);
        }

        const sortChips = (arr) => [...arr].sort((a, b) => a.id.localeCompare(b.id));

        const chipHtml = (m) => `
            <div class="model-chip ${selectedModelIds.has(m.id) ? "selected" : ""}" data-model-id="${escapeHtml(m.id)}">
                <input type="checkbox" ${selectedModelIds.has(m.id) ? "checked" : ""} data-model-id="${escapeHtml(m.id)}" />
                <span>${escapeHtml(m.id)}</span>
            </div>
        `;

        const groupEntries = Object.entries(endpointGroups).sort((a, b) => a[1].name.localeCompare(b[1].name));

        list.innerHTML = `
            ${freeModels.length > 0 ? `
                <div class="selector-free-column">
                    ${sortChips(freeModels).map(chipHtml).join("")}
                </div>
            ` : ""}
            ${groupEntries.map(([key, group]) => `
                <div class="selector-endpoint-column">
                    <div class="selector-column-header">${escapeHtml(group.name)} · ${escapeHtml(group.provider)}</div>
                    ${sortChips(group.models).map(chipHtml).join("")}
                </div>
            `).join("")}
        `;
        if (modal) modal.classList.add("show");
        if (countEl) countEl.textContent = `${selectedModelIds.size} selected`;
        
        list?.querySelectorAll(".model-chip").forEach((chip) => {
            chip.addEventListener("click", () => {
                const modelId = chip.dataset.modelId;
                if (selectedModelIds.has(modelId)) {
                    selectedModelIds.delete(modelId);
                } else {
                    selectedModelIds.add(modelId);
                }
                chip.classList.toggle("selected");
                chip.querySelector("input").checked = selectedModelIds.has(modelId);
                if (countEl) countEl.textContent = `${selectedModelIds.size} selected`;
            });
        });
    };
    
    openBtn?.addEventListener("click", openModelSelector);
    closeBtn?.addEventListener("click", () => {
        if (modal) modal.classList.remove("show");
        updateModelChips();
    });
    modal?.addEventListener("click", (e) => {
        if (e.target === modal) modal.classList.remove("show");
    });
    
    selectAllBtn?.addEventListener("click", () => {
        models.forEach((m) => selectedModelIds.add(m.id));
        updateSelectorList();
    });
    selectNoneBtn?.addEventListener("click", () => {
        selectedModelIds.clear();
        updateSelectorList();
    });
    
    function updateSelectorList() {
        const list = document.getElementById("models-selector-list");
        if (list) {
            list.querySelectorAll(".model-chip").forEach((chip) => {
                const modelId = chip.dataset.modelId;
                const checked = selectedModelIds.has(modelId);
                chip.classList.toggle("selected", checked);
                const input = chip.querySelector("input");
                if (input) input.checked = checked;
            });
        }
        if (countEl) countEl.textContent = `${selectedModelIds.size} selected`;
    }
    
    confirmBtn?.addEventListener("click", () => {
        if (modal) modal.classList.remove("show");
        updateModelChips();
    });
    
    searchInput?.addEventListener("input", () => {
        const term = (searchInput?.value || "").toLowerCase();
        document.querySelectorAll("#models-selector-list .model-chip").forEach((chip) => {
            const text = chip.textContent?.toLowerCase() || "";
            chip.style.display = text.includes(term) ? "" : "none";
        });
    });
}

function populatePromptPackageSelect() {
    const select = document.getElementById("report-prompt-package");
    if (!select) return;
    
    const loadingEl = document.getElementById("prompt-packages-loading");
    const errorEl = document.getElementById("prompt-packages-error");
    
    if (promptPackages.length === 0) {
        select.innerHTML = `<option value="">-- No prompt packages available --</option>`;
        if (loadingEl) loadingEl.style.display = "none";
        if (errorEl) {
            errorEl.textContent = "No prompt packages loaded. Check server connection.";
            errorEl.style.display = "block";
        }
    } else {
        select.innerHTML = `<option value="">-- Select a prompt package --</option>` + 
            promptPackages.map((pkg) => `<option value="${escapeHtml(pkg.id)}">${escapeHtml(pkg.name || pkg.id)}</option>`).join("");
        if (loadingEl) loadingEl.style.display = "none";
        if (errorEl) errorEl.style.display = "none";
    }
    
    // Attach change listener to load prompts when a package is selected
    select.onchange = () => {
        const pkgId = select.value;
        const promptsTextarea = document.getElementById("report-prompts");
        if (!pkgId || !promptsTextarea) return;
        
        const pkg = promptPackages.find((p) => p.id === pkgId);
        if (pkg && pkg.prompts && pkg.prompts.length) {
            promptsTextarea.value = pkg.prompts.join(", ");
        } else {
            promptsTextarea.value = "";
        }
    };
}

// Generate Reports
function initGenerateReports() {
    const form = document.getElementById("report-form");
    const stopBtn = document.getElementById("stop-reports");
    const promptCountSlider = document.getElementById("prompt-count");
    const promptCountValue = document.getElementById("prompt-count-value");
    const batchModeSelect = document.getElementById("batch-mode");
    
    const updatePromptCountSlider = () => {
        if (!promptCountSlider || !batchModeSelect) return;
        const mode = batchModeSelect.value;
        const max = mode === "batch" ? 100 : 20;
        promptCountSlider.max = max;
        if (parseInt(promptCountSlider.value) > max) {
            promptCountSlider.value = max;
        }
        if (promptCountValue) {
            promptCountValue.textContent = promptCountSlider.value;
        }
    };
    
    promptCountSlider?.addEventListener("input", () => {
        if (promptCountValue) promptCountValue.textContent = promptCountSlider.value;
    });
    
    batchModeSelect?.addEventListener("change", updatePromptCountSlider);
    updatePromptCountSlider();
    
    form?.addEventListener("submit", (e) => {
        e.preventDefault();
        const promptsText = document.getElementById("report-prompts")?.value || "";
        const prompts = promptsText.split(",").map((p) => p.trim()).filter(Boolean);
        const promptPackage = document.getElementById("report-prompt-package")?.value || "";
        const modelIds = Array.from(selectedModelIds);
        const promptCount = promptCountSlider ? parseInt(promptCountSlider.value) : prompts.length;
        
        if (!modelIds.length) {
            alert("Please add models first.");
            return;
        }
        
        const truncatedPrompts = prompts.slice(0, promptCount);
        
        sendWs({
            action: "generate_reports",
            models: modelIds,
            prompts: truncatedPrompts,
            promptPackage: promptPackage,
            promptCount: promptCount,
        });
    });
    
    stopBtn?.addEventListener("click", () => {
        sendWs({ action: "stop_reports" });
        const output = document.getElementById("report-output");
        if (output) output.textContent = "Stopping...";
    });
    
    const cancelBtn = document.getElementById("cancel-reports");
    const retryBtn = document.getElementById("retry-reports");
    
    cancelBtn?.addEventListener("click", () => {
        if (!currentJobId) return;
        sendWs({ action: "cancel_job", job_id: currentJobId });
    });
    
    retryBtn?.addEventListener("click", () => {
        if (!currentJobId) return;
        const job = activeJobStatus;
        alert("Retry functionality: please regenerate reports from the Generate Reports tab.");
    });
    
    // View Reports link: navigate to the Reports tab and refresh the list
    const viewLink = document.getElementById("view-reports-link");
    viewLink?.addEventListener("click", (e) => {
        e.preventDefault();
        switchToTab("tab-reports");
        sendWs({ action: "list_reports" });
    });
    
    const selectAllBtn = document.getElementById("select-all-models");
    const selectNoneBtn = document.getElementById("select-none-models");
    
    selectAllBtn?.addEventListener("click", () => {
        models.forEach((m) => selectedModelIds.add(m.id));
        updateModelChips();
    });
    selectNoneBtn?.addEventListener("click", () => {
        selectedModelIds.clear();
        updateModelChips();
    });
}

// Prompts Editor
function initPromptsEditor() {
    const editBtn = document.getElementById("edit-prompts");
    const modal = document.getElementById("prompts-modal");
    const closeBtn = document.getElementById("prompts-modal-close");
    const saveBtn = document.getElementById("prompts-save");
    const addBtn = document.getElementById("prompts-add");
    
    editBtn?.addEventListener("click", () => {
        const prompts = document.getElementById("report-prompts")?.value || "";
        const promptList = document.getElementById("prompts-modal-list");
        if (promptList) {
            const lines = prompts.split(",").map((p) => p.trim()).filter(Boolean);
            promptList.innerHTML = lines.map((p, i) => `
                <div class="prompt-item">
                    <textarea data-prompt-index="${i}">${escapeHtml(p)}</textarea>
                    <button class="prompt-remove" data-prompt-index="${i}" title="Remove prompt">\u00D7</button>
                </div>
            `).join("");
            // Attach remove handlers
            promptList.querySelectorAll(".prompt-remove").forEach((btn) => {
                btn.addEventListener("click", () => {
                    btn.closest(".prompt-item")?.remove();
                });
            });
        }
        if (modal) modal.classList.add("show");
    });
    
    closeBtn?.addEventListener("click", () => {
        if (modal) modal.classList.remove("show");
    });
    modal?.addEventListener("click", (e) => {
        if (e.target === modal) modal.classList.remove("show");
    });
    addBtn?.addEventListener("click", () => {
        const promptList = document.getElementById("prompts-modal-list");
        if (promptList) {
            const idx = promptList.querySelectorAll(".prompt-item").length;
            const div = document.createElement("div");
            div.className = "prompt-item";
            div.innerHTML = `
                <textarea data-prompt-index="${idx}"></textarea>
                <button class="prompt-remove" data-prompt-index="${idx}" title="Remove prompt">\u00D7</button>
            `;
            promptList.appendChild(div);
            const removeBtn = div.querySelector(".prompt-remove");
            removeBtn?.addEventListener("click", () => {
                div.remove();
            });
        }
    });
    
    saveBtn?.addEventListener("click", () => {
        const promptList = document.getElementById("prompts-modal-list");
        const prompts = [];
        promptList?.querySelectorAll("textarea").forEach((ta) => {
            const val = ta.value.trim();
            if (val) prompts.push(val);
        });
        document.getElementById("report-prompts").value = prompts.join(", ");
        if (modal) modal.classList.remove("show");
    });
}

function closePromptsModal() {
    const modal = document.getElementById("prompts-modal");
    if (modal) modal.classList.remove("show");
}

function closeModelsSelectorModal() {
    const modal = document.getElementById("models-selector-modal");
    if (modal) modal.classList.remove("show");
}

// Progress dashboard
function showProgressDashboard() {
    const dashboard = document.getElementById("progress-dashboard");
    if (dashboard) dashboard.classList.remove("hidden");
}

function hideProgressDashboard() {
    const dashboard = document.getElementById("progress-dashboard");
    if (dashboard) dashboard.classList.add("hidden");
    // Don't hide progress-actions here - they should remain visible for completed jobs
    localStorage.removeItem("we3.currentJobId");
    localStorage.removeItem("we3.currentRunId");
    currentJobId = null;
    currentRunId = null;
    activeJobStatus = null;
}

function restoreProgressIfActive() {
    if (currentJobId) {
        sendWs({ action: "get_job", job_id: currentJobId });
    }
}

function showProgressActions(status) {
    const actions = document.getElementById("progress-actions");
    const cancelBtn = document.getElementById("cancel-reports");
    const retryBtn = document.getElementById("retry-reports");
    if (!actions) return;
    actions.classList.remove("hidden");
    if (cancelBtn) cancelBtn.classList.toggle("hidden", status === "completed" || status === "completed_with_errors" || status === "failed" || status === "cancelled");
    if (retryBtn) retryBtn.classList.toggle("hidden", status !== "failed" && status !== "completed_with_errors");
    // The "View Reports" link visibility is controlled by updateViewReportsLink()
    // based on whether real PDF reports actually exist — not just on job status.
}

// Show the "View Reports" link only when real PDF reports exist.
// This prevents a dead link from being shown when no reports were generated.
function updateViewReportsLink(hasReports) {
    const viewLink = document.getElementById("view-reports-link");
    if (!viewLink) return;
    if (hasReports) {
        viewLink.classList.remove("hidden");
    } else {
        viewLink.classList.add("hidden");
    }
}
}

function formatElapsed(seconds) {
    if (!seconds && seconds !== 0) return "0s";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
}

function formatEta(isoString) {
    if (!isoString) return "calculating...";
    try {
        const dt = new Date(isoString);
        if (isNaN(dt.getTime())) return "calculating...";
        return dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
        return "calculating...";
    }
}

function getStatusLabel(status) {
    const map = {
        queued: "Queued",
        initializing: "Initializing",
        processing: "Processing",
        finalizing: "Finalizing",
        completed: "Completed",
        completed_with_errors: "Completed with errors",
        failed: "Failed",
        cancelled: "Cancelled",
    };
    return map[status] || status || "Unknown";
}

function getStatusColor(status) {
    const map = {
        queued: "var(--muted)",
        initializing: "var(--accent)",
        processing: "var(--accent)",
        finalizing: "var(--accent)",
        completed: "#4ade80",
        completed_with_errors: "#fbbf24",
        failed: "var(--fail)",
        cancelled: "var(--muted)",
    };
    return map[status] || "var(--text)";
}

function updateProgressDashboard(message) {
    const status = message.status || activeJobStatus || "processing";
    const overall = message.overall || {};
    const models_state = message.models_state || {};
    const reports = message.reports || [];
    
    // Detect rate limits from reports
    const hasRateLimit = reports.some(r => r.error && isRateLimitError(r.error));
    // Detect rate limits from model states
    const modelRateLimit = Object.values(models_state).some(m => m.error && isRateLimitError(m.error));
    if (hasRateLimit || modelRateLimit) {
        rateLimited = true;
    } else if (status === "completed" || status === "failed" || status === "cancelled" || status === "completed_with_errors") {
        rateLimited = false;
    }
    updateRateLimitStatus();
    
    // Update overall status
    const statusLabel = document.getElementById("progress-status-label");
    if (statusLabel) {
        statusLabel.textContent = getStatusLabel(status);
        statusLabel.style.color = getStatusColor(status);
    }
    
    const stepEl = document.getElementById("progress-step");
    if (stepEl) stepEl.textContent = message.current_step || "Processing...";
    
    const percentageEl = document.getElementById("progress-percentage");
    if (percentageEl) percentageEl.textContent = `${overall.percentage || 0}%`;
    
    const progressBar = document.getElementById("progress-bar");
    if (progressBar) progressBar.style.width = `${overall.percentage || 0}%`;
    
    const completedEl = document.getElementById("progress-completed");
    if (completedEl) completedEl.textContent = `${overall.completed_reports || 0} completed`;
    
    const failedEl = document.getElementById("progress-failed");
    if (failedEl) {
        const failedCount = overall.failed_reports || 0;
        failedEl.textContent = `${failedCount} failed`;
        failedEl.classList.toggle("hidden", failedCount === 0);
    }
    
    const processingEl = document.getElementById("progress-processing");
    if (processingEl) processingEl.textContent = `${overall.processing_reports || 0} processing`;
    
    const queuedEl = document.getElementById("progress-queued");
    if (queuedEl) queuedEl.textContent = `${overall.queued_reports || 0} queued`;
    
    const elapsedEl = document.getElementById("progress-elapsed");
    if (elapsedEl) elapsedEl.textContent = `Elapsed: ${formatElapsed(overall.elapsed_seconds)}`;
    
    const etaEl = document.getElementById("progress-eta");
    if (etaEl) {
        const est = overall.estimated_completion;
        etaEl.textContent = `ETA: ${formatEta(est)}`;
        etaEl.classList.toggle("hidden", !est);
    }
    
    // Update model cards
    renderProgressModels(models_state);
    
    // Update report details
    renderProgressReports(reports, status);
    
    activeJobStatus = status;
}

function renderProgressModels(modelsState) {
    const container = document.getElementById("progress-models");
    if (!container) return;

    const entries = Object.entries(modelsState);
    if (entries.length === 0) {
        Object.values(modelCardCache).forEach(el => el.remove());
        modelCardCache = {};
        modelStatusCache = {};
        modelPercentageCache = {};
        Object.values(modelTimers).forEach(t => {
            if (t.intervalId) clearInterval(t.intervalId);
        });
        modelTimers = {};
        rateLimited = false;
        updateRateLimitStatus();
        return;
    }

    const terminalStatuses = ["completed", "completed_with_errors", "failed", "cancelled"];
    const activeKeys = new Set();

    entries.forEach(([modelKey, modelState]) => {
        activeKeys.add(modelKey);

        const pct = modelState.percentage || 0;
        const provider = modelState.provider || "unknown";
        const label = modelState.label || modelKey;
        const step = modelState.current_step || "Waiting";
        const completed = modelState.completed_reports || 0;
        const failed = modelState.failed_reports || 0;
        const total = modelState.total_reports || 0;
        const elapsed = formatElapsed(modelState.elapsed_seconds);
        const incomingStatus = modelState.status || "processing";
        const modelError = modelState.error || "";

        // Status regression guard: once terminal, do not let incoming
        // processing/queued regress it. Important for retry passes where the
        // server momentarily emits a non-terminal status for a model that
        // already finished its initial pass.
        const prevStatus = modelStatusCache[modelKey] || "processing";
        const prevIsTerminal = terminalStatuses.includes(prevStatus);
        const incomingIsTerminal = terminalStatuses.includes(incomingStatus);
        const status = (prevIsTerminal && !incomingIsTerminal) ? prevStatus : incomingStatus;
        modelStatusCache[modelKey] = status;

        if (modelError && isRateLimitError(modelError)) {
            rateLimited = true;
            updateRateLimitStatus();
        }

        const isResponding = status === "processing" &&
            (step.includes("Validating") || step.includes("Preparing prompt") || step.includes("Sending prompt"));

        let card = modelCardCache[modelKey];
        const cardIsNew = !card;
        if (!card) {
            // Build the card structure using DOM API to avoid any HTML-string
            // parsing issues. We capture references to the dynamic bits so we
            // can update them in place on later renders.
            card = document.createElement("div");
            card.className = "progress-model-card";
            card.id = `model-card-${modelKey.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
            card.dataset.modelKey = modelKey;

            const header = document.createElement("div");
            header.className = "progress-model-header";
            const nameEl = document.createElement("span");
            nameEl.className = "progress-model-name";
            const providerEl = document.createElement("span");
            providerEl.className = "progress-model-provider";
            header.appendChild(nameEl);
            header.appendChild(providerEl);
            card.appendChild(header);

            const stepEl = document.createElement("div");
            stepEl.className = "progress-model-step";
            card.appendChild(stepEl);

            const barContainer = document.createElement("div");
            barContainer.className = "progress-model-bar-container";
            const barEl = document.createElement("div");
            barEl.className = "progress-model-bar";
            barEl.style.width = "0%";
            barContainer.appendChild(barEl);
            card.appendChild(barContainer);

            const metaEl = document.createElement("div");
            metaEl.className = "progress-model-meta";
            const s0 = document.createElement("span");  // complete count
            const s1 = document.createElement("span");  // failed count
            s1.className = "progress-failed-text";
            s1.style.display = "none";
            const s2 = document.createElement("span");  // elapsed
            const s3 = document.createElement("span");  // status label
            s3.style.fontWeight = "600";
            metaEl.appendChild(s0);
            metaEl.appendChild(s1);
            metaEl.appendChild(s2);
            metaEl.appendChild(s3);
            card.appendChild(metaEl);

            container.appendChild(card);
            modelCardCache[modelKey] = card;
        }

        // FROZEN-CARD optimization: skip DOM writes for cards already in a
        // terminal state. The server emits state every ~200ms; without this
        // gate, completed cards would visibly flicker their text / numbers /
        // bar while the rest of the job runs. The card stays frozen until
        // the server reports a non-terminal status for this model again
        // (e.g. a retry pass re-queues it).
        if (!cardIsNew && prevIsTerminal && status === prevStatus && card.dataset.frozen === "1") {
            return;
        }

        const statusColor = getStatusColor(status);

        const nameEl = card.querySelector(".progress-model-name");
        if (nameEl) nameEl.textContent = label;
        const providerEl = card.querySelector(".progress-model-provider");
        if (providerEl) providerEl.textContent = provider;
        const stepEl = card.querySelector(".progress-model-step");
        if (stepEl) {
            stepEl.textContent = step;
            stepEl.className = "progress-model-step" + (isResponding ? " model-responding" : "");
        }
        const barEl = card.querySelector(".progress-model-bar");
        if (barEl) {
            // Monotonic percentage: never go backward on a still-running model
            if (status === "completed" || status === "completed_with_errors") {
                modelPercentageCache[modelKey] = 100;
            } else {
                modelPercentageCache[modelKey] = Math.max(modelPercentageCache[modelKey] || 0, pct);
            }
            barEl.style.width = `${modelPercentageCache[modelKey]}%`;
        }
        const metaEl = card.querySelector(".progress-model-meta");
        if (metaEl) {
            const spans = metaEl.querySelectorAll("span");
            if (spans[0]) spans[0].textContent = `${completed}/${total} complete`;
            if (spans[1]) {
                spans[1].textContent = `${failed} failed`;
                spans[1].className = "progress-failed-text";
                spans[1].style.display = failed > 0 ? "inline" : "none";
            }
            if (spans[2]) spans[2].textContent = elapsed;
            if (spans[3]) {
                spans[3].textContent = getStatusLabel(status);
                spans[3].style.color = statusColor;
                spans[3].style.fontWeight = "600";
            }
        }

        let errorEl = card.querySelector(".progress-model-error");
        if (modelError) {
            if (!errorEl) {
                errorEl = document.createElement("div");
                errorEl.className = "progress-model-error";
                card.appendChild(errorEl);
            }
            errorEl.textContent = modelError;
            errorEl.style.fontSize = "11px";
            errorEl.style.color = "var(--fail)";
            errorEl.style.marginTop = "6px";
        } else if (errorEl) {
            errorEl.remove();
        }

        if (terminalStatuses.includes(status)) {
            card.dataset.frozen = "1";
        } else {
            delete card.dataset.frozen;
        }
    });

    // Remove cards for models no longer present in state
    Object.keys(modelCardCache).forEach(key => {
        if (!activeKeys.has(key)) {
            modelCardCache[key].remove();
            delete modelCardCache[key];
            delete modelStatusCache[key];
            delete modelPercentageCache[key];
        }
    });
}

function renderProgressReports(reports, jobStatus) {
    const container = document.getElementById("progress-reports-list");
    if (!container) return;
    
    if (!reports || reports.length === 0) {
        container.innerHTML = `<div class="progress-report-item"><span class="progress-report-status queued">No reports yet</span></div>`;
        return;
    }
    
    container.innerHTML = reports.map(report => {
        const status = report.status || "queued";
        const statusClass = status === "complete" ? "complete" : status === "failed" ? "failed" : status === "processing" ? "processing" : "queued";
        const modelLabel = report.model_label || report.model || "unknown";
        const step = report.step || "Waiting";
        const started = report.started_at ? new Date(report.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "-";
        const finished = report.finished_at ? new Date(report.finished_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "-";
        const elapsed = formatElapsed(report.elapsed_seconds);
        const retryCount = report.retry_count || 0;
        const error = report.error || "";
        
        if (error && isRateLimitError(error)) {
            rateLimited = true;
            updateRateLimitStatus();
        }
        
        return `
            <div class="progress-report-item">
                <div>
                    <div><strong>${escapeHtml(report.id || modelLabel)}</strong></div>
                    <div style="font-size: 11px; color: var(--muted);">${escapeHtml(step)} | Started: ${started} | Finished: ${finished} | Elapsed: ${elapsed} | Retries: ${retryCount}</div>
                    ${error ? `<div style="font-size: 11px; color: var(--fail);">${escapeHtml(error)}</div>` : ""}
                </div>
                <span class="progress-report-status ${statusClass}">${getStatusLabel(status)}</span>
            </div>
        `;
    }).join("");
    
    if (reports.length === 0) {
        rateLimited = false;
        updateRateLimitStatus();
    }
}

// Reports (PDF viewing)
function initReports() {
    const refreshButton = document.getElementById("refresh-reports");
    const clearWallBtn = document.getElementById("clear-wall-o-docs");
    const regenerateBtn = document.getElementById("regenerate-reports");
    const searchInput = document.getElementById("report-search");
    const modalClose = document.getElementById("pdf-modal-close");
    const modal = document.getElementById("pdf-modal");
    const modalZoomIn = document.getElementById("pdf-modal-zoom-in");
    const modalZoomOut = document.getElementById("pdf-modal-zoom-out");
    const modalZoomLabel = document.getElementById("pdf-modal-zoom");
    const rawDataModal = document.getElementById("raw-data-modal");
    const rawDataModalClose = document.getElementById("raw-data-modal-close");
    
    refreshButton?.addEventListener("click", () => {
        sendWs({ action: "list_reports" });
    });
    clearWallBtn?.addEventListener("click", async () => {
        if (!confirm("Clear all reports and telemetry from the Wall-o-Docs? This cannot be undone.")) return;
        await fetch("/api/telemetry/runs", { method: "DELETE" });
        await fetch("/api/reports", { method: "DELETE" });
        sendWs({ action: "list_reports" });
    });
    regenerateBtn?.addEventListener("click", async () => {
        const models = Array.from(selectedModelIds);
        if (!models.length) {
            alert("Select at least one model in the Models tab first.");
            return;
        }
        const prompts = (document.getElementById("report-prompts")?.value || "").split(",").map(p => p.trim()).filter(Boolean);
        if (!prompts.length) {
            alert("Enter at least one prompt or select a prompt package.");
            return;
        }
        sendWs({ action: "generate_reports", models, prompts });
    });
    // Debounce search input to prevent excessive requests
    searchInput?.addEventListener("input", () => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            sendWs({ action: "list_reports" });
        }, 300);
    });
    // PDF modal: X button, backdrop click, and Esc key all close.
    modalClose?.addEventListener("click", closePdfModal);
    modal?.addEventListener("click", (e) => {
        if (e.target === modal ||
            e.target.classList?.contains("pdf-modal-backdrop")) {
            closePdfModal();
        }
    });
    const pdfBackdrop = document.getElementById("pdf-modal-backdrop");
    if (pdfBackdrop) pdfBackdrop.addEventListener("click", closePdfModal);
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modal?.classList.contains("show")) {
            closePdfModal();
        }
    });
    // Raw-data modal: same treatment
    rawDataModalClose?.addEventListener("click", closeRawDataModal);
    rawDataModal?.addEventListener("click", (e) => {
        if (e.target === rawDataModal ||
            e.target.classList?.contains("raw-data-modal-backdrop")) {
            closeRawDataModal();
        }
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && rawDataModal?.classList.contains("show")) {
            closeRawDataModal();
        }
    });
    
    // Modal zoom controls
    const zoomModal = (delta) => {
        if (!modalPdfDoc) return;
        modalZoom = Math.max(0.5, Math.min(3.0, modalZoom + delta));
        if (modalZoomLabel) modalZoomLabel.textContent = `${Math.round(modalZoom * 100)}%`;
        const container = document.getElementById("pdf-modal-container");
        if (!container) return;
        container.innerHTML = "";
        (async () => {
            try {
                for (let i = 1; i <= modalPdfDoc.numPages; i++) {
                    const page = await modalPdfDoc.getPage(i);
                    const viewport = page.getViewport({ scale: modalZoom });
                    const canvas = document.createElement("canvas");
                    canvas.width = viewport.width;
                    canvas.height = viewport.height;
                    canvas.style.width = `${viewport.width}px`;
                    canvas.style.height = `${viewport.height}px`;
                    const ctx = canvas.getContext("2d");
                    await page.render({ canvasContext: ctx, viewport }).promise;
                    container.appendChild(canvas);
                }
            } catch (exc) {
                container.innerHTML = `<div class="pdf-placeholder">Zoom failed: ${exc}</div>`;
            }
        })();
    };
    
    modalZoomIn?.addEventListener("click", () => zoomModal(0.2));
    modalZoomOut?.addEventListener("click", () => zoomModal(-0.2));
}

function renderReports(reports, reportRuns) {
    const grid = document.getElementById("reports-grid");
    if (!grid) return;
    const search = (document.getElementById("report-search")?.value || "").toLowerCase();
    console.error('[PDF] renderReports', { reportCount: reports.length, runCount: reportRuns?.length, search });
    
    let html = "";
    let filteredRuns = [];
    let pairs = [];
    
    // Prefer run-grouped reports from telemetry
    const runs = (reportRuns && reportRuns.length > 0) ? reportRuns : null;
    
    if (runs) {
        filteredRuns = runs.filter(run => {
            const artifacts = (run.artifacts || []).filter(a => a.toLowerCase().endsWith(".pdf"));
            return artifacts.some(a => a.toLowerCase().includes(search));
        });
        
        if (filteredRuns.length === 0) {
            grid.innerHTML = `<div class="empty-message">No reports found. Generate reports from the Generate Reports tab.</div>`;
            return;
        }
        
        filteredRuns.forEach((run, runIdx) => {
            let artifacts = (run.artifacts || []).filter(a => a.toLowerCase().endsWith(".pdf"));
            if (search) {
                artifacts = artifacts.filter(a => a.toLowerCase().includes(search));
            }
            if (artifacts.length === 0) return;
            
            const runId = run.runId || run.run_id || `run-${runIdx + 1}`;
            const startedAt = run.startedAt || "";
            
            // Group artifacts into pairs
            pairs = [];
            for (let i = 0; i < artifacts.length; i += 2) {
                const pair = [artifacts[i]];
                if (i + 1 < artifacts.length) pair.push(artifacts[i + 1]);
                pairs.push(pair);
            }
            
            html += `<div class="report-run-container">`;
            html += `<div class="report-run-header"><span>Run ${escapeHtml(runId)}${startedAt ? ' - ' + escapeHtml(formatDate(startedAt)) : ''}</span></div>`;
            
            pairs.forEach((pair, pairIdx) => {
                const left = pair[0];
                const right = pair[1];
                const singleClass = pair.length === 1 ? ' single' : '';
                const globalIdx = runIdx * 100 + pairIdx;
                
                html += `<div class="report-pair-row">`;
                html += `<div class="pdf-pair-scroll"><div class="pdf-pair${singleClass}">`;
                
                if (left) {
                    html += `<div class="pdf-cell-wrapper">`;
                    html += `<div class="pdf-cell-title">${escapeHtml(left)}</div>`;
                    html += `<div class="pdf-viewer-cell" data-url="/reports/${escapeHtml(left)}" data-scale="0.65">`;
                    html += `<button class="pdf-cell-remove" data-run="${escapeHtml(runId)}" data-artifact="${escapeHtml(left)}" title="Remove PDF">×</button>`;
                    html += `<div class="pdf-cell-overlay"><button class="pdf-cell-view" data-url="/reports/${escapeHtml(left)}">View Full</button></div>`;
                    html += `<div class="pdf-cell-zoom"><button class="pdf-zoom-btn pdf-zoom-in" data-side="left" data-pair="${globalIdx}">+</button><span class="pdf-zoom-label" id="pdf-zoom-label-left-${globalIdx}">65%</span><button class="pdf-zoom-btn pdf-zoom-out" data-side="left" data-pair="${globalIdx}">−</button></div>`;
                    html += `<div class="pdf-page-stack" id="pdf-stack-left-${globalIdx}"></div>`;
                    html += `<div class="pdf-pair-nav">`;
                    html += `<button class="secondary" data-side="left" data-pair="${globalIdx}" data-delta="-1">Prev</button>`;
                    html += `<span class="pdf-pair-indicator" id="pdf-indicator-left-${globalIdx}">Page -</span>`;
                    html += `<button class="secondary" data-side="left" data-pair="${globalIdx}" data-delta="1">Next</button>`;
                    html += `</div></div>`;
                    html += `</div>`;
                }
                if (right) {
                    html += `<div class="pdf-cell-wrapper">`;
                    html += `<div class="pdf-cell-title">${escapeHtml(right)}</div>`;
                    html += `<div class="pdf-viewer-cell" data-url="/reports/${escapeHtml(right)}" data-scale="0.65">`;
                    html += `<button class="pdf-cell-remove" data-run="${escapeHtml(runId)}" data-artifact="${escapeHtml(right)}" title="Remove PDF">×</button>`;
                    html += `<div class="pdf-cell-overlay"><button class="pdf-cell-view" data-url="/reports/${escapeHtml(right)}">View Full</button></div>`;
                    html += `<div class="pdf-cell-zoom"><button class="pdf-zoom-btn pdf-zoom-in" data-side="right" data-pair="${globalIdx}">+</button><span class="pdf-zoom-label" id="pdf-zoom-label-right-${globalIdx}">65%</span><button class="pdf-zoom-btn pdf-zoom-out" data-side="right" data-pair="${globalIdx}">−</button></div>`;
                    html += `<div class="pdf-page-stack" id="pdf-stack-right-${globalIdx}"></div>`;
                    html += `<div class="pdf-pair-nav">`;
                    html += `<button class="secondary" data-side="right" data-pair="${globalIdx}" data-delta="-1">Prev</button>`;
                    html += `<span class="pdf-pair-indicator" id="pdf-indicator-right-${globalIdx}">Page -</span>`;
                    html += `<button class="secondary" data-side="right" data-pair="${globalIdx}" data-delta="1">Next</button>`;
                    html += `</div></div>`;
                    html += `</div>`;
                }
                
                html += `</div></div></div>`;
            });
            
            html += `</div>`;
        });
    } else {
        // Fallback: flat list grouped into pairs
        const filtered = reports.filter((r) => r.name.toLowerCase().includes(search));
        
        if (filtered.length === 0) {
            grid.innerHTML = `<div class="empty-message">No reports found. Generate reports from the Generate Reports tab.</div>`;
            return;
        }
        
        pairs = [];
        for (let i = 0; i < filtered.length; i += 2) {
            const pair = [filtered[i]];
            if (i + 1 < filtered.length) {
                pair.push(filtered[i + 1]);
            }
            pairs.push(pair);
        }
        
        pairs.forEach((pair, idx) => {
            const left = pair[0];
            const right = pair[1];
            const singleClass = pair.length === 1 ? ' single' : '';
            
            html += `<div class="report-pair-row">`;
            html += `<div class="report-pair-header"><span>Pair ${idx + 1}${pair.length === 2 ? ` (${escapeHtml(left.name).replace('-evaluation.pdf', '')} vs ${escapeHtml(right.name).replace('-evaluation.pdf', '')})` : ` (${escapeHtml(left.name).replace('-evaluation.pdf', '')})`}</span></div>`;
            html += `<div class="pdf-pair-scroll"><div class="pdf-pair${singleClass}">`;
            
            if (left) {
                const runForLeft = reportRuns.find(r => (r.artifacts || []).includes(left.name));
                const runIdLeft = runForLeft ? (runForLeft.runId || runForLeft.run_id) : "";
                html += `<div class="pdf-cell-wrapper">`;
                html += `<div class="pdf-cell-title">${escapeHtml(left.name)}</div>`;
                html += `<div class="pdf-viewer-cell" data-url="${escapeHtml(left.url)}" data-scale="0.65">`;
                html += `<button class="pdf-cell-remove" data-run="${escapeHtml(runIdLeft)}" data-artifact="${escapeHtml(left.name)}" title="Remove PDF">×</button>`;
                html += `<div class="pdf-cell-overlay"><button class="pdf-cell-view" data-url="${escapeHtml(left.url)}">View Full</button></div>`;
                html += `<div class="pdf-cell-zoom"><button class="pdf-zoom-btn pdf-zoom-in" data-side="left" data-pair="${idx}">+</button><span class="pdf-zoom-label" id="pdf-zoom-label-left-${idx}">65%</span><button class="pdf-zoom-btn pdf-zoom-out" data-side="left" data-pair="${idx}">−</button></div>`;
                html += `<div class="pdf-page-stack" id="pdf-stack-left-${idx}"></div>`;
                html += `<div class="pdf-pair-nav">`;
                html += `<button class="secondary" data-side="left" data-pair="${idx}" data-delta="-1">Prev</button>`;
                html += `<span class="pdf-pair-indicator" id="pdf-indicator-left-${idx}">Page -</span>`;
                html += `<button class="secondary" data-side="left" data-pair="${idx}" data-delta="1">Next</button>`;
                html += `</div></div>`;
                html += `</div>`;
            }
            if (right) {
                const runForRight = reportRuns.find(r => (r.artifacts || []).includes(right.name));
                const runIdRight = runForRight ? (runForRight.runId || runForRight.run_id) : "";
                html += `<div class="pdf-cell-wrapper">`;
                html += `<div class="pdf-cell-title">${escapeHtml(right.name)}</div>`;
                html += `<div class="pdf-viewer-cell" data-url="${escapeHtml(right.url)}" data-scale="0.65">`;
                html += `<button class="pdf-cell-remove" data-run="${escapeHtml(runIdRight)}" data-artifact="${escapeHtml(right.name)}" title="Remove PDF">×</button>`;
                html += `<div class="pdf-cell-overlay"><button class="pdf-cell-view" data-url="${escapeHtml(right.url)}">View Full</button></div>`;
                html += `<div class="pdf-cell-zoom"><button class="pdf-zoom-btn pdf-zoom-in" data-side="right" data-pair="${idx}">+</button><span class="pdf-zoom-label" id="pdf-zoom-label-right-${idx}">65%</span><button class="pdf-zoom-btn pdf-zoom-out" data-side="right" data-pair="${idx}">−</button></div>`;
                html += `<div class="pdf-page-stack" id="pdf-stack-right-${idx}"></div>`;
                html += `<div class="pdf-pair-nav">`;
                html += `<button class="secondary" data-side="right" data-pair="${idx}" data-delta="-1">Prev</button>`;
                html += `<span class="pdf-pair-indicator" id="pdf-indicator-right-${idx}">Page -</span>`;
                html += `<button class="secondary" data-side="right" data-pair="${idx}" data-delta="1">Next</button>`;
                html += `</div></div>`;
                html += `</div>`;
            }
            
            html += `</div></div></div>`;
        });
    }
    
    grid.innerHTML = html;
    
    // Wire up View Full buttons
    grid.querySelectorAll(".pdf-cell-view").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const url = btn.dataset.url;
            if (url) openPdfModal(url);
        });
    });
    
    // Wire up navigation buttons
    grid.querySelectorAll(".pdf-pair-nav button").forEach((btn) => {
        btn.addEventListener("click", () => {
            const side = btn.dataset.side;
            const pairIdx = parseInt(btn.dataset.pair);
            const delta = parseInt(btn.dataset.delta);
            navigatePdf(side, pairIdx, delta);
        });
    });
    
    // Wire up zoom buttons
    grid.querySelectorAll(".pdf-zoom-in").forEach((btn) => {
        btn.addEventListener("click", () => {
            const side = btn.dataset.side;
            const pairIdx = parseInt(btn.dataset.pair);
            zoomPdfCell(side, pairIdx, 0.1);
        });
    });
    grid.querySelectorAll(".pdf-zoom-out").forEach((btn) => {
        btn.addEventListener("click", () => {
            const side = btn.dataset.side;
            const pairIdx = parseInt(btn.dataset.pair);
            zoomPdfCell(side, pairIdx, -0.1);
        });
    });
    
    // Wire up Ctrl+wheel on each cell
    grid.querySelectorAll(".pdf-viewer-cell").forEach((cell) => {
        cell.addEventListener("wheel", (e) => {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                const side = cell.querySelector(".pdf-page-stack")?.id?.split("-")[2];
                const pairIdx = parseInt(cell.querySelector(".pdf-page-stack")?.id?.split("-")[3]);
                if (side && !isNaN(pairIdx)) {
                    zoomPdfCell(side, pairIdx, e.deltaY < 0 ? 0.1 : -0.1);
                }
            }
        }, { passive: false });
        
        // Prevent any default click behavior on the cell itself
        cell.addEventListener("click", (e) => {
            // Only prevent default if the click target is the cell itself or the page stack
            if (e.target === cell || e.target.classList.contains("pdf-page-stack") || e.target.tagName === "CANVAS") {
                e.preventDefault();
            }
        });
    });
    
    // Wire up remove buttons
    grid.querySelectorAll(".pdf-cell-remove").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const runId = btn.dataset.run;
            const artifact = btn.dataset.artifact;
            if (!artifact) return;
            if (runId) {
                await fetch(`/api/telemetry/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifact)}`, { method: "DELETE" });
            } else {
                await fetch(`/api/reports/${encodeURIComponent(artifact)}`, { method: "DELETE" });
            }
            sendWs({ action: "list_reports" });
        });
    });
    
    // Load PDFs
    if (runs) {
        filteredRuns.forEach((run, runIdx) => {
            const artifacts = (run.artifacts || []).filter(a => a.toLowerCase().endsWith(".pdf"));
            artifacts.forEach((art, artIdx) => {
                const side = artIdx % 2 === 0 ? 'left' : 'right';
                const pairIdx = runIdx * 100 + Math.floor(artIdx / 2);
                if (side === 'left' || artIdx % 2 === 0) {
                    loadPdfInCell('left', pairIdx, `/reports/${art}`, 0.65);
                } else {
                    loadPdfInCell('right', pairIdx, `/reports/${art}`, 0.65);
                }
            });
        });
    } else {
        pairs.forEach((pair, idx) => {
            if (pair[0]) loadPdfInCell('left', idx, pair[0].url, 0.65);
            if (pair[1]) loadPdfInCell('right', idx, pair[1].url, 0.65);
        });
    }
    console.error('[PDF] renderReports complete', { htmlLength: html.length, pairCount: pairs?.length || 0 });
}

async function loadPdfInCell(side, pairIndex, url, scale = 0.65) {
    const key = `${side}-${pairIndex}`;
    const stackEl = document.getElementById(`pdf-stack-${key}`);
    const indicatorEl = document.getElementById(`pdf-indicator-${key}`);
    const zoomLabelEl = document.getElementById(`pdf-zoom-label-${key}`);
    const cellEl = stackEl?.closest(".pdf-viewer-cell");
    if (!stackEl) {
        console.error('[PDF] loadPdfInCell: stackEl not found for key', key);
        return;
    }
    if (typeof pdfjsLib === 'undefined') {
        stackEl.innerHTML = '<div class="pdf-placeholder" style="color:#e5484d">PDF library not loaded. Check console.</div>';
        console.error('[PDF] pdfjsLib is undefined');
        return;
    }
    console.error('[PDF] loadPdfInCell start', { key, url, scale });
    
    // Update cell data attribute
    if (cellEl) cellEl.dataset.scale = String(scale);
    
    // Show loading state
    stackEl.innerHTML = '<div class="pdf-placeholder" style="color:#1f3a8a;background:#e6e9f5;border:1px solid #9aa3c7">Loading PDF...</div>';
    
    try {
        // Fetch PDF data manually to avoid worker/CORS fetch issues
        const response = await fetch(url);
        console.error('[PDF] fetch response', { url, status: response.status, ok: response.ok });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const arrayBuffer = await response.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);
        console.error('[PDF] fetched bytes', { url, length: uint8Array.length, firstBytes: Array.from(uint8Array.slice(0, 20)) });
        
        if (uint8Array.length === 0) {
            stackEl.innerHTML = '<div class="pdf-placeholder" style="color:#e5484d">PDF file is empty</div>';
            return;
        }
        
        // Try both approaches: direct data and Blob URL
        let doc;
        try {
            const task = pdfjsLib.getDocument({ data: uint8Array });
            doc = await task.promise;
            console.error('[PDF] pdf.js doc loaded via data', { url, numPages: doc.numPages });
        } catch (dataErr) {
            console.error('[PDF] data approach failed, trying Blob URL', { error: dataErr });
            const blob = new Blob([uint8Array], { type: 'application/pdf' });
            const blobUrl = URL.createObjectURL(blob);
            try {
                const task = pdfjsLib.getDocument(blobUrl);
                doc = await task.promise;
                console.error('[PDF] pdf.js doc loaded via Blob URL', { url, numPages: doc.numPages });
            } finally {
                URL.revokeObjectURL(blobUrl);
            }
        }
        pdfPairs[key] = { doc, currentPage: 1, url, numPages: doc.numPages, scale };
        
        if (doc.numPages === 0) {
            stackEl.innerHTML = '<div class="pdf-placeholder" style="color:#e5484d">PDF has no pages</div>';
            return;
        }
        
        // Update zoom label
        if (zoomLabelEl) zoomLabelEl.textContent = `${Math.round(scale * 100)}%`;
        
        // Render all pages
        stackEl.innerHTML = '';
        for (let i = 1; i <= doc.numPages; i++) {
            try {
                const page = await doc.getPage(i);
                const viewport = page.getViewport({ scale });
                console.error('[PDF] page viewport', { page: i, width: viewport.width, height: viewport.height });
                const canvas = document.createElement('canvas');
                canvas.width = viewport.width;
                canvas.height = viewport.height;
                canvas.style.width = `${viewport.width}px`;
                canvas.style.height = `${viewport.height}px`;
                canvas.style.border = '1px solid red';
                canvas.dataset.page = i;
                const ctx = canvas.getContext('2d');
                if (!ctx) {
                    const placeholder = document.createElement('div');
                    placeholder.className = 'pdf-placeholder';
                    placeholder.textContent = `Failed to get canvas context for page ${i}`;
                    stackEl.appendChild(placeholder);
                    continue;
                }
                // Fill white background first to avoid transparent/blank rendering
                ctx.fillStyle = '#ffffff';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                try {
                    await Promise.race([
                        page.render({ canvasContext: ctx, viewport }).promise,
                        new Promise((_, reject) => setTimeout(() => reject(new Error('render timeout')), 15000)),
                    ]);
                } catch (renderErr) {
                    console.error('[PDF] page.render error', { page: i, error: renderErr });
                    const placeholder = document.createElement('div');
                    placeholder.className = 'pdf-placeholder';
                    placeholder.textContent = `Render timeout/error page ${i}: ${renderErr}`;
                    stackEl.appendChild(placeholder);
                    continue;
                }
                stackEl.appendChild(canvas);
                console.error('[PDF] page rendered', { page: i });
            } catch (pageErr) {
                console.error('[PDF] page render error', { page: i, error: pageErr });
                const placeholder = document.createElement('div');
                placeholder.className = 'pdf-placeholder';
                placeholder.textContent = `Failed to render page ${i}: ${pageErr}`;
                stackEl.appendChild(placeholder);
            }
        }
        
        if (indicatorEl) indicatorEl.textContent = `Page 1 / ${doc.numPages}`;
        console.error('[PDF] loadPdfInCell complete', { key, numPages: doc.numPages });
    } catch (exc) {
        console.error('[PDF] loadPdfInCell FAILED', { key, url, error: exc });
        stackEl.innerHTML = `<div class="pdf-placeholder" style="color:#e5484d;background:#fff0f0">Failed to load PDF: ${exc}</div>`;
    }
}

function zoomPdfCell(side, pairIndex, delta) {
    const key = `${side}-${pairIndex}`;
    const state = pdfPairs[key];
    const stackEl = document.getElementById(`pdf-stack-${key}`);
    const zoomLabelEl = document.getElementById(`pdf-zoom-label-${key}`);
    const cellEl = stackEl?.closest(".pdf-viewer-cell");
    if (!state || !stackEl) return;
    
    const newScale = Math.max(0.4, Math.min(2.5, state.scale + delta));
    state.scale = newScale;
    if (cellEl) cellEl.dataset.scale = String(newScale);
    if (zoomLabelEl) zoomLabelEl.textContent = `${Math.round(newScale * 100)}%`;
    
    // Re-render all pages at new scale
    (async () => {
        try {
        stackEl.innerHTML = '';
        for (let i = 1; i <= state.doc.numPages; i++) {
            const page = await state.doc.getPage(i);
            const viewport = page.getViewport({ scale: newScale });
            const canvas = document.createElement('canvas');
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            canvas.style.width = `${viewport.width}px`;
            canvas.style.height = `${viewport.height}px`;
            canvas.dataset.page = i;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            try {
                await Promise.race([
                    page.render({ canvasContext: ctx, viewport }).promise,
                    new Promise((_, reject) => setTimeout(() => reject(new Error('render timeout')), 15000)),
                ]);
            } catch (renderErr) {
                console.error('[PDF] zoom page.render error', { page: i, error: renderErr });
                const placeholder = document.createElement('div');
                placeholder.className = 'pdf-placeholder';
                placeholder.textContent = `Render timeout/error page ${i}: ${renderErr}`;
                stackEl.appendChild(placeholder);
                continue;
            }
            stackEl.appendChild(canvas);
        }
            // Restore scroll position to current page
            const pageCanvas = stackEl.querySelector(`canvas[data-page="${state.currentPage}"]`);
            if (pageCanvas) pageCanvas.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (exc) {
            stackEl.innerHTML = `<div class="pdf-placeholder">Zoom failed: ${exc}</div>`;
        }
    })();
}

function navigatePdf(side, pairIndex, delta) {
    const key = `${side}-${pairIndex}`;
    const state = pdfPairs[key];
    if (!state) return;
    
    const newPage = state.currentPage + delta;
    if (newPage < 1 || newPage > state.numPages) return;
    
    state.currentPage = newPage;
    const stackEl = document.getElementById(`pdf-stack-${key}`);
    const indicatorEl = document.getElementById(`pdf-indicator-${key}`);
    
    // Scroll to the page
    if (stackEl) {
        const pageCanvas = stackEl.querySelector(`canvas[data-page="${newPage}"]`);
        if (pageCanvas) {
            pageCanvas.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
    
    if (indicatorEl) indicatorEl.textContent = `Page ${newPage} / ${state.numPages}`;
}

async function openPdfModal(url) {
    const container = document.getElementById("pdf-modal-container");
    const titleEl = document.getElementById("pdf-modal-title");
    const modal = document.getElementById("pdf-modal");
    const modalZoomLabel = document.getElementById("pdf-modal-zoom");
    const openLink = document.getElementById("pdf-open");
    if (!container) return;
    
    if (titleEl) titleEl.textContent = url.split("/").pop() || "";
    // Set "Open Original" to point to the real report URL so it opens in a new tab
    if (openLink) openLink.href = url;
    
    // Show loading state
    container.innerHTML = '<div class="pdf-placeholder" style="color:#1f3a8a;background:#e6e9f5;border:1px solid #9aa3c7">Loading PDF...</div>';
    modal.classList.add("show");
    
    try {
        // Fetch PDF data manually to avoid worker/CORS fetch issues
        const response = await fetch(url);
        console.error('[PDF] modal fetch response', { url, status: response.status, ok: response.ok });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const arrayBuffer = await response.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);
        
        if (uint8Array.length === 0) {
            container.innerHTML = '<div class="pdf-placeholder" style="color:#e5484d">PDF file is empty</div>';
            return;
        }
        
        // Try both approaches: direct data and Blob URL
        let doc;
        try {
            const task = pdfjsLib.getDocument({ data: uint8Array });
            doc = await task.promise;
        } catch (dataErr) {
            console.error('[PDF] modal data approach failed, trying Blob URL', { error: dataErr });
            const blob = new Blob([uint8Array], { type: 'application/pdf' });
            const blobUrl = URL.createObjectURL(blob);
            try {
                const task = pdfjsLib.getDocument(blobUrl);
                doc = await task.promise;
            } finally {
                URL.revokeObjectURL(blobUrl);
            }
        }
        
        modalPdfDoc = doc;
        modalZoom = 1.2;
        if (modalZoomLabel) modalZoomLabel.textContent = `${Math.round(modalZoom * 100)}%`;
        
        if (doc.numPages === 0) {
            container.innerHTML = '<div class="pdf-placeholder" style="color:#e5484d">PDF has no pages</div>';
            return;
        }
        
        container.innerHTML = '';
        for (let i = 1; i <= doc.numPages; i++) {
            const page = await doc.getPage(i);
            const viewport = page.getViewport({ scale: modalZoom });
            const canvas = document.createElement('canvas');
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            canvas.style.width = `${viewport.width}px`;
            canvas.style.height = `${viewport.height}px`;
            canvas.style.border = '1px solid red';
            const ctx = canvas.getContext('2d');
            // Fill white background first to avoid transparent/blank rendering
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            try {
                await Promise.race([
                    page.render({ canvasContext: ctx, viewport }).promise,
                    new Promise((_, reject) => setTimeout(() => reject(new Error('render timeout')), 15000)),
                ]);
            } catch (renderErr) {
                console.error('[PDF] modal page.render error', { page: i, error: renderErr });
                const placeholder = document.createElement('div');
                placeholder.className = 'pdf-placeholder';
                placeholder.textContent = `Render timeout/error page ${i}: ${renderErr}`;
                container.appendChild(placeholder);
                continue;
            }
            container.appendChild(canvas);
        }
    } catch (exc) {
        console.error('[PDF] modal FAILED', { url, error: exc });
        container.innerHTML = `<div class="pdf-placeholder" style="color:#e5484d;background:#fff0f0">Failed to load PDF: ${exc}</div>`;
    }
}

function closePdfModal() {
    const modal = document.getElementById("pdf-modal");
    if (modal) modal.classList.remove("show");
}

// Keep old openPdf for backward compatibility (used by Telemetry Wall if needed)
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
        await renderPdfPage();
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

async function renderPdfPage() {
    if (!pdfDoc) return;
    const canvas = document.getElementById("pdf-canvas");
    const pageLabel = document.getElementById("pdf-page");
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

// Telemetry Wall
function initTelemetry() {
    const refreshBtn = document.getElementById("refresh-telemetry");
    const clearBtn = document.getElementById("clear-telemetry");
    const backdrop = document.getElementById("telemetry-backdrop");
    const expandedClose = document.getElementById("telemetry-expanded-close");
    const modal = document.getElementById("pdf-modal");
    const modalClose = document.getElementById("pdf-modal-close");
    const rawDataModal = document.getElementById("raw-data-modal");
    const rawDataModalClose = document.getElementById("raw-data-modal-close");
    const chartModal = document.getElementById("chart-modal");
    const chartModalClose = document.getElementById("chart-modal-close");
    
    refreshBtn?.addEventListener("click", () => {
        sendWs({ action: "list_telemetry" });
    });
    
    clearBtn?.addEventListener("click", async () => {
        await fetch("/api/telemetry/runs", { method: "DELETE" });
        currentSelection = null;
        sendWs({ action: "list_telemetry" });
    });
    
    expandedClose?.addEventListener("click", collapseRunWindow);
    backdrop?.addEventListener("click", () => {
        collapseRunWindow();
        if (backdrop) backdrop.classList.remove("show");
    });
    
    modalClose?.addEventListener("click", closePdfModal);
    modal?.addEventListener("click", (e) => {
        if (e.target === modal) closePdfModal();
    });
    
    rawDataModalClose?.addEventListener("click", () => {
        if (rawDataModal) rawDataModal.classList.remove("show");
    });
    rawDataModal?.addEventListener("click", (e) => {
        if (e.target === rawDataModal) rawDataModal.classList.remove("show");
    });
    
    const rawDataCopyBtn = document.getElementById("raw-data-copy");
    rawDataCopyBtn?.addEventListener("click", () => {
        const bodyEl = document.getElementById("raw-data-modal-content");
        if (bodyEl) {
            navigator.clipboard.writeText(bodyEl.textContent || "");
        }
    });
    
    // Chart modal close: X button, click-on-backdrop, Esc key.
    // The X button click bubbles through the content; if the modal content has
    // its own pointerdown/mousedown handlers (drag/resize), they should call
    // stopPropagation so the close handler can still fire on the X button.
    if (chartModalClose) {
        const closeHandler = (e) => {
            e.stopPropagation();
            e.preventDefault();
            closeChartModal();
        };
        chartModalClose.addEventListener("click", closeHandler);
        chartModalClose.addEventListener("pointerup", closeHandler);
        // Also explicitly stop pointerdown/mousedown so drag handlers don't capture
        chartModalClose.addEventListener("pointerdown", (e) => e.stopPropagation());
        chartModalClose.addEventListener("mousedown", (e) => e.stopPropagation());
    }
    // Click outside the modal content (on the backdrop or the modal container
    // itself) closes the modal. The backdrop is the .chart-modal-backdrop div;
    // clicking anywhere except .chart-modal-content closes.
    if (chartModal) {
        chartModal.addEventListener("click", (e) => {
            // e.target === chartModal means user clicked the empty fixed-
            // positioned container itself; .chart-modal-backdrop means they
            // clicked the semi-transparent overlay. Both should close.
            if (e.target === chartModal ||
                e.target.classList?.contains("chart-modal-backdrop")) {
                closeChartModal();
            }
        });
    }
    // Also handle the backdrop explicitly in case pointer-events behave oddly
    const chartBackdrop = document.getElementById("chart-modal-backdrop");
    if (chartBackdrop) {
        chartBackdrop.addEventListener("click", closeChartModal);
    }

    // Esc key closes the chart modal if it's open
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && chartModal?.classList.contains("show")) {
            closeChartModal();
        }
    });
}

function renderTelemetry(runs) {
    const wall = document.getElementById("telemetry-wall");
    if (!wall) return;
    if (!runs.length) {
        wall.innerHTML = "";
        return;
    }
    
    wall.innerHTML = runs.map((run) => `
        <div class="run-window" data-run="${escapeHtml(run.runId || run.run_id)}">
            <div class="run-window-header" data-run="${escapeHtml(run.runId || run.run_id)}">
                <span class="run-window-title">${escapeHtml(run.runId || run.run_id)}</span>
                <span class="run-window-meta">${escapeHtml(run.type || "unknown")} &#8226; ${formatDate(run.startedAt)}</span>
                <div class="run-window-actions">
                    <button class="run-window-action" data-action="raw" data-run="${escapeHtml(run.runId || run.run_id)}">Raw Data</button>
                    <button class="run-window-action" data-action="zip" data-run="${escapeHtml(run.runId || run.run_id)}">Save All as Zip</button>
                    <button class="run-window-close" data-run="${escapeHtml(run.runId || run.run_id)}" title="Close run">\u00D7</button>
                </div>
            </div>
        </div>
    `).join("");
    
    // Attach event handlers for telemetry actions
    wall.querySelectorAll(".run-window-action").forEach((btn) => {
        btn.addEventListener("click", () => {
            const runId = btn.dataset.run;
            const action = btn.dataset.action;
            if (action === "raw") {
                openRawDataModal(runId);
            } else if (action === "zip") {
                window.open(`/api/telemetry/runs/${runId}/zip`, "_blank");
            }
        });
    });
    
    wall.querySelectorAll(".run-window-close").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const runId = btn.dataset.run;
            await fetch(`/api/telemetry/runs/${encodeURIComponent(runId)}`, { method: "DELETE" });
            sendWs({ action: "list_telemetry" });
        });
    });
    
    // Make run window header clickable to expand
    wall.querySelectorAll(".run-window-header").forEach((header) => {
        header.addEventListener("click", () => {
            const runId = header.dataset.run;
            expandRunWindow(runId);
        });
    });
}

function openRawDataModal(runId) {
    const run = telemetryRuns.find((r) => (r.runId || r.run_id) === runId);
    if (!run) return;
    
    const modal = document.getElementById("raw-data-modal");
    const bodyEl = document.getElementById("raw-data-modal-content");
    if (!modal || !bodyEl) return;
    
    bodyEl.textContent = JSON.stringify(run, null, 2);
    modal.classList.add("show");
}

function closeRawDataModal() {
    const modal = document.getElementById("raw-data-modal");
    if (modal) modal.classList.remove("show");
}

function openChartModal(chart, runId, isSample) {
    const modal = document.getElementById("chart-modal");
    const imgEl = document.getElementById("chart-modal-img");
    if (!modal || !imgEl) return;

    // chart can be a string (legacy URL) or an object
    const chartUrl = typeof chart === "string" ? chart : (chart?.url || "");
    const chartName = typeof chart === "string" ? "" : (chart?.name || "");
    const chartDisplay = typeof chart === "string" ? "" : (chart?.displayName || chartName);
    const chartDesc = typeof chart === "string" ? "" : (chart?.description || "");

    imgEl.src = chartUrl;

    // Set title
    const titleEl = document.getElementById("chart-modal-title");
    if (titleEl) titleEl.textContent = chartDisplay || chartName || "Chart Viewer";

    // Set description
    const descEl = document.getElementById("chart-modal-desc");
    if (descEl) descEl.textContent = chartDesc || "";

    // Show/hide sample badge
    const sampleBadge = modal.querySelector(".chart-modal-sample-badge");
    if (sampleBadge) sampleBadge.style.display = isSample ? "inline-flex" : "none";

    // Mark the modal as sample/non-sample
    modal.classList.toggle("chart-modal-sample", !!isSample);

    // Set up the delete button with run_id and chart_name
    const deleteBtn = document.getElementById("chart-modal-delete");
    if (deleteBtn) {
        deleteBtn.onclick = null; // Remove any existing handler
        if (chartName && runId) {
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                fetch(`/api/charts/runs/${encodeURIComponent(runId)}/${encodeURIComponent(chartName)}`, { method: "DELETE" })
                    .then(() => {
                        closeChartModal();
                        // Re-render gallery to remove the card
                        const idx = chartRunsCache.findIndex(r => r.runId === runId);
                        if (idx >= 0) {
                            chartRunsCache[idx].charts = chartRunsCache[idx].charts.filter(c => c.name !== chartName);
                        }
                        renderChartsGallery(chartRunsCache);
                    })
                    .catch(err => console.error("Failed to delete chart:", err));
            };
            deleteBtn.style.display = "inline-flex";
        } else {
            deleteBtn.style.display = "none";
        }
    }

    // Set up close-all button
    const closeAllBtn = document.getElementById("chart-modal-close-all");
    if (closeAllBtn) {
        closeAllBtn.onclick = null;
        closeAllBtn.onclick = (e) => {
            e.stopPropagation();
            closeChartModal();
        };
        closeAllBtn.style.display = "inline-flex";
    }

    // Set up maximize button
    const maximizeBtn = document.getElementById("chart-modal-maximize");
    if (maximizeBtn) {
        maximizeBtn.onclick = null;
        maximizeBtn.onclick = (e) => {
            e.stopPropagation();
            const content = document.getElementById("chart-modal-content");
            if (content) content.classList.toggle("chart-modal-maximized");
            const isMax = content?.classList.contains("chart-modal-maximized");
            maximizeBtn.textContent = isMax ? "↖" : "Maximize";
        };
        maximizeBtn.style.display = "inline-flex";
    }

    modal.classList.add("show");
}

function closeChartModal() {
    const modal = document.getElementById("chart-modal");
    if (modal) modal.classList.remove("show");
}

function expandRunWindow(runId) {
    const expanded = document.getElementById("telemetry-expanded");
    const titleEl = document.getElementById("telemetry-expanded-title");
    const bodyEl = document.getElementById("telemetry-expanded-body");
    if (!expanded || !bodyEl) return;
    
    const run = telemetryRuns.find((r) => (r.runId || r.run_id) === runId);
    if (!run) return;
    
    if (titleEl) titleEl.textContent = `${run.runId || run.run_id} - ${run.type || "unknown"}`;
    
    const artifacts = run.artifacts || [];
    if (!artifacts.length) {
        bodyEl.innerHTML = "<div class=\"empty-items\">No artifacts recorded</div>";
    } else {
        bodyEl.innerHTML = `<div class="telemetry-artifacts-grid">` + artifacts.map((art) => {
            const isPdf = art.toLowerCase().endsWith(".pdf");
            const icon = isPdf ? "📄" : "📎";
            const href = `/reports/${encodeURIComponent(art)}`;
            return `<div class="telemetry-artifact-card">
                <a href="${escapeHtml(href)}" target="_blank" class="telemetry-artifact-link">
                    <span class="telemetry-artifact-icon">${icon}</span>
                    <span class="telemetry-artifact-name">${escapeHtml(art)}</span>
                </a>
            </div>`;
        }).join("") + `</div>`;
    }
    
    expanded.classList.add("show");
    const backdrop = document.getElementById("telemetry-backdrop");
    if (backdrop) backdrop.classList.add("show");
}

function collapseRunWindow() {
    const expanded = document.getElementById("telemetry-expanded");
    const backdrop = document.getElementById("telemetry-backdrop");
    if (expanded) expanded.classList.remove("show");
    if (backdrop) backdrop.classList.remove("show");
}

// ---------------------------------------------------------------------------
// Charts tab
// ---------------------------------------------------------------------------
function initCharts() {
    const generateBtn = document.getElementById("generate-charts-btn");
    const refreshBtn = document.getElementById("refresh-charts-btn");

    if (generateBtn) {
        generateBtn.addEventListener("click", () => {
            if (chartGenerationActive) {
                alert("Chart generation already in progress. Please wait.");
                return;
            }
            startChartGeneration();
        });
    }

    if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {
            sendWs({ action: "list_chart_runs" });
            if (!ws || ws.readyState !== WebSocket.OPEN) {
                fetch("/api/charts/metadata").then(r => r.json()).then(d => {
                    chartMetadataCache = d.charts || {};
                    chartOrderCache = d.order || [];
                }).catch(() => {});
                fetch("/api/charts/runs").then(r => r.json()).then(d => {
                    chartRunsCache = d.runs || [];
                    renderChartsGallery(chartRunsCache);
                }).catch(() => {});
            }
        });
    }

    // Initial load: fetch metadata + runs via REST (works without WS)
    // When no chart runs exist on disk, the backend auto-generates sample
    // charts so the gallery always has something to show.
    showChartStatus("Loading charts...", true);
    fetch("/api/charts/metadata").then(r => r.json()).then(d => {
        chartMetadataCache = d.charts || {};
        chartOrderCache = d.order || [];
    }).catch(() => {}).finally(() => {
        fetch("/api/charts/runs").then(r => r.json()).then(d => {
            chartRunsCache = d.runs || [];
            renderChartsGallery(chartRunsCache);
        }).catch(() => {}).finally(() => {
            showChartStatus("", false);
        });
    });
}

function startChartGeneration() {
    let runId = "test-run-final";
    if (chartRunsCache.length > 0) {
        // Prefer non-sample runs — never send "sample-charts" as the runId
        // when real data could be available, so real charts never land in
        // the sample-charts directory.
        const reportRuns = chartRunsCache.filter(r =>
            !r.isSample && (r.type === "report_generation" || (r.runId && r.runId.startsWith("run-")))
        );
        const fallbackRuns = chartRunsCache.filter(r => !r.isSample);
        const selected = reportRuns[0] || fallbackRuns[0];
        runId = selected ? selected.runId : "test-run-final";
    }

    chartGenerationActive = true;
    chartGenerationTotal = chartOrderCache.length || 22;
    chartGenerationDone = 0;
    chartGenerationRunId = runId;

    showChartStatus(`Starting chart generation for ${runId}...`, true);
    updateChartProgressBar(0, chartGenerationTotal);

    if (ws && ws.readyState === WebSocket.OPEN) {
        sendWs({ action: "generate_charts", runId });
    } else {
        fetch("/api/charts/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ runId }),
        }).then(r => r.json()).then(result => {
            chartGenerationActive = false;
            showChartStatus(`Generated ${result.generated || 0} of ${result.total || 0} charts`, false);
            if (result.charts) {
                // Use the server's isSample flag; fall back to runId check only as safety net
                const isSample = result.isSample === true || runId === "sample-charts";
                const responseRunId = result.runId || runId;
                const charts = Object.entries(result.charts).map(([name, url]) => ({
                    name,
                    displayName: (chartMetadataCache[name] || {}).name || name,
                    description: (chartMetadataCache[name] || {}).description || "",
                    category: (chartMetadataCache[name] || {}).category || "General",
                    url,
                    size_bytes: 0,
                }));
                const existing = chartRunsCache.find(r => r.runId === responseRunId);
                if (existing) existing.charts = charts;
                else chartRunsCache.push({ runId: responseRunId, type: isSample ? "sample_generation" : "report_generation", models: [], prompts: [], charts, isSample });
                renderChartsGallery(chartRunsCache);
            }
        }).catch(err => {
            chartGenerationActive = false;
            showChartStatus(`Generation failed: ${err}`, false);
        });
    }
}

function updateChartGenerationProgress(msg) {
    if (msg.status === "started") {
        chartGenerationActive = true;
        chartGenerationTotal = msg.total || chartGenerationTotal;
        chartGenerationDone = msg.index || 0;
        showChartStatus(msg.chartDisplayName || "Generating charts...", true);
        updateChartProgressBar(chartGenerationDone, chartGenerationTotal);
    } else if (msg.status === "completed" || msg.status === "complete") {
        chartGenerationDone = Math.max(chartGenerationDone, (msg.index || 0) + 1);
        showChartStatus(`${msg.chartDisplayName || msg.chartName} done (${chartGenerationDone}/${chartGenerationTotal})`, true);
        updateChartProgressBar(chartGenerationDone, chartGenerationTotal);
    } else if (msg.status === "failed") {
        showChartStatus(`Failed: ${msg.chartName} - ${msg.error || "unknown error"}`, true);
    }
}

function showChartStatus(text, isActive) {
    const bar = document.getElementById("charts-status-bar");
    const textEl = document.getElementById("charts-status-text");
    const spinner = document.getElementById("charts-spinner");
    if (bar) bar.classList.toggle("hidden", !text);
    if (textEl) textEl.textContent = text;
    if (spinner) spinner.style.display = isActive ? "inline-block" : "none";
}

function updateChartProgressBar(done, total) {
    const bar = document.getElementById("charts-progress-bar");
    const progressEl = document.getElementById("charts-status-progress");
    if (bar) {
        const pct = total > 0 ? Math.round((done / total) * 100) : 0;
        bar.style.width = `${pct}%`;
    }
    if (progressEl) progressEl.textContent = `${done} / ${total}`;
}

function renderChartsGallery(runs) {
    const gallery = document.getElementById("charts-gallery");
    if (!gallery) return;

    if (!runs || runs.length === 0) {
        gallery.innerHTML = `<div class="empty-message">No chart runs found. Chart generation may have failed — try clicking "Generate Charts" to create sample visualizations.</div>`;
        return;
    }

    const activeRunIds = new Set();

    runs.forEach(run => {
        const runId = run.runId || run.run_id || "unknown";
        activeRunIds.add(runId);

        let section;
        const isSample = run.isSample === true || (run.runId || "").toLowerCase().includes("sample");

        // Check if this run was already deleted in session
        // (The backend excludes these, but we guard for edge cases)

        section = chartCardCache[runId];
        if (!section) {
            section = document.createElement("div");
            section.className = isSample
                ? "chart-run-section chart-run-section-sample"
                : "chart-run-section";
            section.dataset.runId = runId;
            if (isSample) section.dataset.isSample = "true";

            const header = document.createElement("div");
            header.className = isSample
                ? "chart-run-header chart-run-header-sample"
                : "chart-run-header";
            const titleEl = document.createElement("span");
            titleEl.className = "chart-run-title";
            const sampleBadge = document.createElement("span");
            sampleBadge.className = "chart-sample-badge";
            sampleBadge.textContent = "SAMPLE";
            sampleBadge.title = "Sample chart — generated from synthetic data. Not tied to any real evaluation run.";
            const metaEl = document.createElement("span");
            metaEl.className = "chart-run-meta";
            const countEl = document.createElement("span");
            countEl.className = "chart-run-count";

            // Action buttons: minimize/expand and close (delete) for the run frame
            const actionsEl = document.createElement("div");
            actionsEl.className = "chart-run-actions";

            const minimizeBtn = document.createElement("button");
            minimizeBtn.className = "chart-run-minimize";
            minimizeBtn.title = "Minimize/expand this run frame";
            minimizeBtn.textContent = "−";
            minimizeBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                const grid = section.querySelector(".chart-run-charts");
                if (!grid) return;
                const isMin = grid.classList.toggle("minimized");
                minimizeBtn.textContent = isMin ? "+" : "−";
            });

            const deleteBtn = document.createElement("button");
            deleteBtn.className = "chart-run-delete-all";
            deleteBtn.title = "Remove this run and all its charts";
            deleteBtn.textContent = "×";
            deleteBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                // No confirmation — clicking × should just close/delete the frame.
                fetch(`/api/charts/runs/${encodeURIComponent(runId)}/all`, { method: "DELETE" })
                    .then(() => {
                        chartCardCache[runId]?.remove();
                        delete chartCardCache[runId];
                        Object.keys(chartStatusCache).forEach(k => {
                            if (k.startsWith(runId + "::")) delete chartStatusCache[k];
                        });
                        const idx = chartRunsCache.findIndex(r => r.runId === runId);
                        if (idx >= 0) chartRunsCache.splice(idx, 1);
                        // Re-render to update cache view
                        renderChartsGallery(chartRunsCache);
                    })
                    .catch(err => console.error("Failed to delete run charts:", err));
            });

            actionsEl.appendChild(minimizeBtn);
            actionsEl.appendChild(deleteBtn);

            header.appendChild(titleEl);
            header.appendChild(sampleBadge);
            header.appendChild(metaEl);
            header.appendChild(countEl);
            header.appendChild(actionsEl);

            const grid = document.createElement("div");
            grid.className = "chart-run-charts";

            section.appendChild(header);
            section.appendChild(grid);
            gallery.appendChild(section);
            chartCardCache[runId] = section;
        }

        const titleEl = section.querySelector(".chart-run-title");
        if (titleEl) titleEl.textContent = `Run: ${runId}`;

        // Update or create the sample badge
        let badge = section.querySelector(".chart-sample-badge");
        if (!badge) {
            badge = document.createElement("span");
            badge.className = "chart-sample-badge";
            badge.textContent = "SAMPLE";
            badge.title = "Sample chart — generated from synthetic data. Not tied to any real evaluation run.";
            const hdr = section.querySelector(".chart-run-header");
            if (hdr) hdr.insertBefore(badge, hdr.querySelector(".chart-run-meta"));
        }
        badge.style.display = isSample ? "inline-flex" : "none";

        const header = section.querySelector(".chart-run-header");
        if (header) {
            header.classList.toggle("chart-run-header-sample", isSample);
        }
        section.classList.toggle("chart-run-section-sample", isSample);
        section.dataset.isSample = isSample ? "true" : "false";

        const metaEl = section.querySelector(".chart-run-meta");
        if (metaEl) {
            const models = run.models || [];
            const prompts = run.prompts || [];
            const type = isSample ? "sample" : (run.type || "report_generation");
            metaEl.textContent = `${type} • ${models.length} model${models.length !== 1 ? "s" : ""} • ${prompts.length} prompt${prompts.length !== 1 ? "s" : ""}`;
        }
        const countEl = section.querySelector(".chart-run-count");
        const charts = run.charts || [];
        if (countEl) countEl.textContent = `${charts.length} chart${charts.length !== 1 ? "s" : ""}`;

        const grid = section.querySelector(".chart-run-charts");
        if (!grid) return;

        const seenCardNames = new Set();
        charts.forEach(chart => {
            const cardKey = runId + "::" + chart.name;
            seenCardNames.add(cardKey);

            let entry = chartStatusCache[cardKey];
            let card = entry && entry.card;
            if (!card) {
                card = document.createElement("div");
                card.className = isSample ? "chart-card chart-card-sample" : "chart-card";
                card.href = chart.url || "#";
                card.dataset.chartName = chart.name;
                card.dataset.runId = runId;

                // Build card content via DOM API (no HTML strings to mangle)
                const img = document.createElement("img");
                img.className = "chart-card-img";
                img.loading = "lazy";

                const body = document.createElement("div");
                body.className = "chart-card-body";
                const ct = document.createElement("div");
                ct.className = "chart-card-title";
                const cc = document.createElement("div");
                cc.className = "chart-card-category";
                const cd = document.createElement("div");
                cd.className = "chart-card-desc";
                const cm = document.createElement("div");
                cm.className = "chart-card-meta";
                
                // Sample badge
                const sb = document.createElement("span");
                sb.className = "chart-card-sample-badge";
                sb.textContent = "S";
                sb.title = "Sample chart — generated from synthetic data";

                // Delete button for individual chart deletion
                const delBtn = document.createElement("button");
                delBtn.className = "chart-card-delete-btn";
                delBtn.title = "Delete this chart";
                delBtn.innerHTML = "×";
                delBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    fetch(`/api/charts/runs/${encodeURIComponent(runId)}/${encodeURIComponent(chart.name)}`, { method: "DELETE" })
                        .then(() => {
                            card.remove();
                            const cacheKey = runId + "::" + chart.name;
                            delete chartStatusCache[cacheKey];
                            // Update run chart count
                            const charts = run.charts.filter(c => c.name !== chart.name);
                            run.charts = charts;
                            const countEl = section.querySelector(".chart-run-count");
                            if (countEl) countEl.textContent = `${charts.length} chart${charts.length !== 1 ? "s" : ""}`;
                        })
                        .catch(err => console.error("Failed to delete chart:", err));
                });

                body.appendChild(ct);
                body.appendChild(cc);
                body.appendChild(cd);
                body.appendChild(cm);
                body.appendChild(sb);
                body.appendChild(delBtn);
                card.appendChild(img);
                card.appendChild(body);

                card.addEventListener("click", (e) => {
                    // Don't open modal if delete button was clicked
                    if (e.target === delBtn) return;
                    if (typeof openChartModal === "function") {
                        openChartModal(chart, runId, isSample);
                    } else {
                        window.open(chart.url, "_blank");
                    }
                });

                grid.appendChild(card);
                chartStatusCache[cardKey] = { card };
            } else if (grid !== card.parentElement) {
                grid.appendChild(card);
            }

            const img = card.querySelector(".chart-card-img");
            if (img) {
                const newSrc = chart.url || "";
                if (img.getAttribute("src") !== newSrc) img.src = newSrc;
                img.alt = chart.displayName || chart.name || "Chart";
            }
            const titleE = card.querySelector(".chart-card-title");
            if (titleE) titleE.textContent = chart.displayName || chart.name || "Chart";
            const catE = card.querySelector(".chart-card-category");
            if (catE) catE.textContent = chart.category || "Chart";
            const descE = card.querySelector(".chart-card-desc");
            if (descE) descE.textContent = chart.description || "";
            const metaE = card.querySelector(".chart-card-meta");
            if (metaE) metaE.textContent = formatBytes(chart.size_bytes || 0);
            // Store chart URL on the card for the click handler
            card.dataset.chartUrl = chart.url || "#";
        });

        // Remove chart cards no longer in this run
        Array.from(grid.children).forEach(child => {
            const childKey = runId + "::" + child.dataset.chartName;
            if (!seenCardNames.has(childKey)) {
                child.remove();
                delete chartStatusCache[childKey];
            }
        });
    });

    // Remove run sections no longer present
    Object.keys(chartCardCache).forEach(rid => {
        if (!activeRunIds.has(rid)) {
            chartCardCache[rid].remove();
            delete chartCardCache[rid];
            Object.keys(chartStatusCache).forEach(k => {
                if (k.startsWith(rid + "::")) delete chartStatusCache[k];
            });
        }
    });
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initDirectionButtons();
    initHelpIcons();
    initEndpoints();
    initModels();
    initGenerateReports();
    initPromptsEditor();
    initModelsSelector();
    initReports();
    initCharts();
    initTelemetry();
    connectWebSocket();
    if (localStorage.getItem("we3.activeTab") === "tab-generate" || document.getElementById("tab-generate")?.classList.contains("active")) {
        restoreProgressIfActive();
    }
});