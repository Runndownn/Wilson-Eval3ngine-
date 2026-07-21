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
let activeJobStatus = null;
let rateLimited = false;
let searchDebounceTimer = null;

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
        sendWs({ action: "list_models" });
        console.error('[PDF] sending list_reports');
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
        const statusEl = document.getElementById("kilo-login-status");
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
        const statusEl = document.getElementById("kilo-login-status");
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
    if (message.action === "kilo_login") {
        const statusEl = document.getElementById("kilo-login-status");
        if (statusEl) {
            if (message.ok) {
                statusEl.textContent = message.message || `Kilo Gateway reachable: ${message.models?.length || 0} models found`;
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
        // Refresh endpoints and models after Kilo login so the new endpoint appears
        if (message.ok) {
            sendWs({ action: "list_endpoints" });
            sendWs({ action: "auto_detect_models" });
        }
    }
}

// Tabs
function initTabs() {
    const tabs = document.querySelectorAll(".tab-link");
    const panels = document.querySelectorAll(".tab-panel");
    const savedTab = localStorage.getItem("we3.activeTab");
    const defaultTab = savedTab || (tabs[0] && (tabs[0].dataset.tab)) || "tab-endpoints";
    
    tabs.forEach((tab) => {
        const target = tab.dataset.tab || "";
        if (target === defaultTab) {
            tab.classList.add("active");
            const panel = document.getElementById(target);
            if (panel) panel.classList.add("active");
        }
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
    
    urlSelect?.addEventListener("change", () => {
        if (urlSelect.value === "__custom__") {
            urlCustom?.classList.remove("hidden");
            urlCustom?.focus();
        } else {
            urlCustom?.classList.add("hidden");
        }
    });
    
    form?.addEventListener("submit", (e) => {
        e.preventDefault();
        const nameInput = document.getElementById("endpoint-name");
        const apiKeyInput = document.getElementById("endpoint-api-key");
        const providerInput = document.getElementById("endpoint-provider");
        
        const url = urlSelect.value === "__custom__" 
            ? (urlCustom?.value || "") 
            : urlSelect.value;
        
        if (!url) return;
        
        sendWs({
            action: "create_endpoint",
            name: nameInput?.value || "Unnamed",
            url: url,
            apiKey: apiKeyInput?.value || null,
            provider: providerInput?.value || "ollama",
        });
        form.reset();
        urlCustom?.classList.add("hidden");
        sendWs({ action: "list_endpoints" });
    });
    
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
    
    const kiloLoginBtn = document.getElementById("kilo-login");
    kiloLoginBtn?.addEventListener("click", () => {
        // Use the selected endpoint URL if it's a Kilo Gateway, otherwise fall back to cloud
        const selectedEndpointId = document.getElementById("model-endpoint")?.value;
        const selectedEndpoint = endpoints.find(ep => ep.id === selectedEndpointId);
        let loginUrl = "https://api.kilo.ai/api/gateway";
        
        if (selectedEndpoint && selectedEndpoint.provider === "kilo") {
            loginUrl = selectedEndpoint.url;
        } else if (selectedEndpoint) {
            // If a non-Kilo endpoint is selected, use that URL with kilo provider
            loginUrl = selectedEndpoint.url;
        }
        
        sendWs({ 
            action: "kilo_login", 
            url: loginUrl,
            apiKey: document.getElementById("endpoint-api-key")?.value || null,
        });
    });
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
        const kiloCol = [];
        const ollamaCol = [];
        const cliCol = [];

        for (const m of models) {
            if (isFreeModel(m.id)) {
                freeModels.push(m);
                continue;
            }
            const ep = endpoints.find(e => e.id === m.endpointId);
            const provider = (ep ? ep.provider : 'unknown').toLowerCase();
            if (provider === 'kilo') kiloCol.push(m);
            else if (provider === 'ollama') ollamaCol.push(m);
            else if (provider === 'kilo_cli') cliCol.push(m);
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

        container.innerHTML = `
            <div class="model-chip-columns">
                ${col("DEBUG-NEW-CODE Free Models", freeModels)}
                ${col("Kilo Gateway", kiloCol)}
                ${col("Ollama", ollamaCol)}
                ${col("Kilo CLI", cliCol)}
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
        const endpointColumns = { kilo: [], ollama: [], kilo_cli: [] };
        const endpointNames = { kilo: "Kilo Gateway", ollama: "Ollama Gateway", kilo_cli: "Kilo CLI" };

        for (const m of models) {
            if (isFreeModel(m.id)) {
                freeModels.push(m);
                continue;
            }
            const ep = endpoints.find(e => e.id === m.endpointId);
            const provider = (ep ? ep.provider : 'unknown').toLowerCase();
            if (provider === 'kilo') endpointColumns.kilo.push(m);
            else if (provider === 'ollama') endpointColumns.ollama.push(m);
            else if (provider === 'kilo_cli') endpointColumns.kilo_cli.push(m);
        }

        const sortChips = (arr) => [...arr].sort((a, b) => a.id.localeCompare(b.id));

        const chipHtml = (m) => `
            <div class="model-chip ${selectedModelIds.has(m.id) ? "selected" : ""}" data-model-id="${escapeHtml(m.id)}">
                <input type="checkbox" ${selectedModelIds.has(m.id) ? "checked" : ""} data-model-id="${escapeHtml(m.id)}" />
                <span>${escapeHtml(m.id)}</span>
            </div>
        `;

        list.innerHTML = `
            ${freeModels.length > 0 ? `
                <div class="selector-free-column">
                    ${sortChips(freeModels).map(chipHtml).join("")}
                </div>
            ` : ""}
            ${endpointColumns.kilo.length > 0 ? `
                <div class="selector-endpoint-column">
                    <div class="selector-column-header">${escapeHtml(endpointNames.kilo)}</div>
                    ${sortChips(endpointColumns.kilo).map(chipHtml).join("")}
                </div>
            ` : ""}
            ${endpointColumns.ollama.length > 0 ? `
                <div class="selector-endpoint-column">
                    <div class="selector-column-header">${escapeHtml(endpointNames.ollama)}</div>
                    ${sortChips(endpointColumns.ollama).map(chipHtml).join("")}
                </div>
            ` : ""}
            ${endpointColumns.kilo_cli.length > 0 ? `
                <div class="selector-endpoint-column">
                    <div class="selector-column-header">${escapeHtml(endpointNames.kilo_cli)}</div>
                    ${sortChips(endpointColumns.kilo_cli).map(chipHtml).join("")}
                </div>
            ` : ""}
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
    const viewLink = document.getElementById("view-reports-link");
    if (!actions) return;
    actions.classList.remove("hidden");
    if (cancelBtn) cancelBtn.classList.toggle("hidden", status === "completed" || status === "failed" || status === "cancelled" || status === "completed_with_errors");
    if (retryBtn) retryBtn.classList.toggle("hidden", status !== "failed" && status !== "completed_with_errors");
    if (viewLink) {
        viewLink.classList.toggle("hidden", status !== "completed" && status !== "completed_with_errors");
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
        container.innerHTML = "";
        return;
    }
    
    container.innerHTML = entries.map(([modelKey, modelState]) => {
        const pct = modelState.percentage || 0;
        const provider = modelState.provider || "unknown";
        const label = modelState.label || modelKey;
        const step = modelState.current_step || "Waiting";
        const completed = modelState.completed_reports || 0;
        const failed = modelState.failed_reports || 0;
        const total = modelState.total_reports || 0;
        const elapsed = formatElapsed(modelState.elapsed_seconds);
        const status = modelState.status || "processing";
        const statusColor = getStatusColor(status);
        const modelError = modelState.error || "";
        
        if (modelError && isRateLimitError(modelError)) {
            rateLimited = true;
            updateRateLimitStatus();
        }
        
        return `
            <div class="progress-model-card">
                <div class="progress-model-header">
                    <span class="progress-model-name">${escapeHtml(label)}</span>
                    <span class="progress-model-provider">${escapeHtml(provider)}</span>
                </div>
                <div class="progress-model-step">${escapeHtml(step)}</div>
                <div class="progress-model-bar-container">
                    <div class="progress-model-bar" style="width: ${pct}%"></div>
                </div>
                <div class="progress-model-meta">
                    <span>${completed}/${total} complete</span>
                    <span class="progress-failed-text">${failed} failed</span>
                    <span>${elapsed}</span>
                    <span style="color: ${statusColor}; font-weight: 600;">${getStatusLabel(status)}</span>
                </div>
                ${modelError ? `<div style="font-size: 11px; color: var(--fail); margin-top: 6px;">${escapeHtml(modelError)}</div>` : ""}
            </div>
        `;
    }).join("");
    
    if (entries.length === 0) {
        rateLimited = false;
        updateRateLimitStatus();
    }
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
    modalClose?.addEventListener("click", closePdfModal);
    modal?.addEventListener("click", (e) => {
        if (e.target === modal) closePdfModal();
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
    if (!container) return;
    
    if (titleEl) titleEl.textContent = url.split("/").pop() || "";
    
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
    
    chartModalClose?.addEventListener("click", () => {
        if (chartModal) chartModal.classList.remove("show");
    });
    chartModal?.addEventListener("click", (e) => {
        if (e.target === chartModal) chartModal.classList.remove("show");
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

function openChartModal(url) {
    const modal = document.getElementById("chart-modal");
    const imgEl = document.getElementById("chart-modal-img");
    if (!modal || !imgEl) return;
    imgEl.src = url;
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
    connectWebSocket();
    if (localStorage.getItem("we3.activeTab") === "tab-generate" || document.getElementById("tab-generate")?.classList.contains("active")) {
        restoreProgressIfActive();
    }
});