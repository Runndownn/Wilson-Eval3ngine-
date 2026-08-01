const state = {
  endpoints: [],
  models: [],
  packages: [],
  chartRuns: [],
  telemetryRuns: [],
  reports: [],
  chartMetadata: {},
  selectedModels: new Set(),
  prompts: [],
  job: null,
  ws: null,
  reconnectTimer: null,
  collapsedRuns: new Set(JSON.parse(localStorage.getItem("we3.collapsedRuns") || "[]")),
  openFamilies: new Set(JSON.parse(localStorage.getItem("we3.openFamilies") || "[]")),
};

const $ = (id) => document.getElementById(id);
const terminalStates = new Set(["completed", "completed_with_errors", "failed", "cancelled", "interrupted"]);

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = value ?? "";
  return node.innerHTML;
}

function escapeAttr(value) {
  return escapeHtml(String(value ?? "")).replaceAll('"', "&quot;");
}

function formatDate(value) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleString();
}

function formatBytes(value) {
  const size = Number(value || 0);
  if (!size) return "Not recorded";
  if (size < 1024) return `${size} B`;
  if (size < 1048576) return `${Math.ceil(size / 1024)} KB`;
  return `${(size / 1048576).toFixed(1)} MB`;
}

function showToast(message, isError = false) {
  const element = $("toast");
  element.textContent = String(message || "Unknown error");
  element.classList.toggle("error", isError);
  element.classList.add("show");
  window.clearTimeout(element._hideTimer);
  element._hideTimer = window.setTimeout(() => element.classList.remove("show"), 4500);
}

function setBusy(element, busy, label = "Working…") {
  if (!element) return;
  if (busy) {
    element.dataset.previousLabel = element.textContent;
    element.textContent = label;
    element.disabled = true;
  } else {
    element.textContent = element.dataset.previousLabel || element.textContent;
    element.disabled = false;
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const detail = payload?.detail || payload?.error || `${response.status} ${response.statusText}`;
    const error = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    error.status = response.status;
    throw error;
  }
  return payload || {};
}

function stableRender(render) {
  const x = window.scrollX;
  const y = window.scrollY;
  render();
  requestAnimationFrame(() => window.scrollTo({ left: x, top: y, behavior: "instant" }));
}

function setTab(name) {
  document.querySelectorAll(".tab").forEach((button) => {
    const active = button.dataset.tab === name;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "step" : "false");
  });
  document.querySelectorAll(".panel").forEach((panel) => panel.classList.toggle("active", panel.id === `panel-${name}`));
  localStorage.setItem("we3.tab", name);
  if (name === "charts") refreshCharts();
  if (name === "reports") refreshReports();
}

function setConnectionState(connected, text) {
  $("health-dot").classList.toggle("online", connected);
  $("health-text").textContent = text;
}

function send(action, payload = {}) {
  if (state.ws?.readyState !== WebSocket.OPEN) return false;
  state.ws.send(JSON.stringify({ action, ...payload }));
  return true;
}

function connect() {
  window.clearTimeout(state.reconnectTimer);
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  state.ws = new WebSocket(`${protocol}://${location.host}/ws`);
  state.ws.onopen = () => {
    setConnectionState(true, "Connected");
    const jobId = localStorage.getItem("we3.job");
    if (jobId) send("subscribe_job", { job_id: jobId });
  };
  state.ws.onclose = () => {
    setConnectionState(false, "Reconnecting");
    state.reconnectTimer = window.setTimeout(connect, 1800);
  };
  state.ws.onerror = () => setConnectionState(false, "Connection error");
  state.ws.onmessage = (event) => {
    try {
      handleSocketMessage(JSON.parse(event.data));
    } catch (error) {
      console.error("Invalid WebSocket payload", error);
    }
  };
}

function normalizeLegacyJob(message, status) {
  return {
    job_id: message.job_id || state.job?.job_id,
    run_id: message.run_id || state.job?.run_id,
    status: status || message.status,
    current_step: message.current_step || message.error || state.job?.current_step,
    overall_percentage: message.overall?.percentage ?? message.overall_percentage,
    completed_reports: message.overall?.completed_reports ?? message.completed_reports,
    failed_reports: message.overall?.failed_reports ?? message.failed_reports,
    total_reports:
      (message.overall?.completed_reports || 0) +
        (message.overall?.failed_reports || 0) +
        (message.overall?.processing_reports || 0) +
        (message.overall?.queued_reports || 0) ||
      state.job?.total_reports,
    current_model: message.current_model,
    models_state: message.models_state || state.job?.models_state,
    error: message.error,
  };
}

function finishJob(job) {
  updateJob(job);
  if (job && terminalStates.has(job.status)) {
    localStorage.removeItem("we3.job");
    refreshReports();
    refreshCharts();
  }
}

function handleSocketMessage(message) {
  if (message.error && !["job_error", "job_cancelled"].includes(message.action)) {
    showToast(message.error, true);
    return;
  }
  switch (message.action) {
    case "generate_reports":
    case "retry_job": {
      const job = message.job || normalizeLegacyJob(message, message.status || "queued");
      if (job?.job_id) localStorage.setItem("we3.job", job.job_id);
      updateJob(job);
      break;
    }
    case "job_created": {
      const job = normalizeLegacyJob(message, message.status || "initializing");
      if (job.job_id) localStorage.setItem("we3.job", job.job_id);
      updateJob(job);
      break;
    }
    case "job_update":
      finishJob(message.job);
      break;
    case "job_progress":
      updateJob(normalizeLegacyJob(message, message.status || "running"));
      break;
    case "job_complete":
      finishJob(normalizeLegacyJob(message, "completed"));
      break;
    case "job_error":
      finishJob(normalizeLegacyJob(message, "failed"));
      break;
    case "job_cancelled":
    case "cancel_job":
      finishJob(message.job || normalizeLegacyJob(message, "cancelled"));
      break;
    case "charts_generated":
      refreshCharts();
      break;
    default:
      break;
  }
}

async function refreshOverview() {
  try {
    const overview = await api("/api/overview");
    $("stat-endpoints").textContent = overview.endpoints ?? state.endpoints.length;
    $("stat-models").textContent = overview.models ?? state.models.length;
    $("stat-runs").textContent = overview.runs ?? state.telemetryRuns.length;
    $("stat-reports").textContent = overview.reports ?? state.reports.length;
  } catch {
    $("stat-endpoints").textContent = state.endpoints.length;
    $("stat-models").textContent = state.models.length;
    $("stat-runs").textContent = state.telemetryRuns.length;
    $("stat-reports").textContent = state.reports.length;
  }
}

async function refreshEndpoints() {
  try {
    const payload = await api("/api/endpoints");
    state.endpoints = payload.endpoints || [];
    renderEndpoints();
    renderEndpointOptions();
    refreshOverview();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshModels() {
  try {
    const payload = await api("/api/models");
    state.models = payload.models || [];
    const registered = new Set(state.models.map((model) => model.id));
    for (const id of [...state.selectedModels]) if (!registered.has(id)) state.selectedModels.delete(id);
    renderModels();
    renderModelSelector();
    updateRunSummary();
    refreshOverview();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshPackages() {
  try {
    const payload = await api("/api/prompts/packages");
    state.packages = payload.packages || [];
    $("prompt-package").innerHTML =
      '<option value="">Custom prompt set</option>' +
      state.packages
        .map((item) => `<option value="${escapeAttr(item.id)}">${escapeHtml(item.name || item.id)} · ${(item.prompts || []).length}</option>`)
        .join("");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshReports() {
  try {
    const payload = await api("/api/reports");
    state.reports = payload.reports || [];
    renderReports();
    refreshOverview();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshCharts() {
  const button = $("refresh-charts");
  setBusy(button, true, "Refreshing…");
  try {
    const [runsPayload, metadataPayload, telemetryPayload] = await Promise.all([
      api("/api/charts/runs"),
      api("/api/charts/metadata"),
      api("/api/telemetry/runs"),
    ]);
    state.chartRuns = runsPayload.runs || [];
    state.chartMetadata = metadataPayload.charts || {};
    state.telemetryRuns = telemetryPayload.runs || [];
    renderCharts();
    refreshOverview();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

function endpointModelCount(endpointId) {
  return state.models.filter((model) => model.endpointId === endpointId).length;
}

function renderEndpoints() {
  const root = $("endpoint-list");
  if (!state.endpoints.length) {
    root.innerHTML = '<div class="empty">No endpoints configured.</div>';
    return;
  }
  root.innerHTML = state.endpoints
    .map((endpoint) => {
      const count = endpointModelCount(endpoint.id);
      const status = endpoint.available === true ? "online" : endpoint.available === false ? "offline" : "not tested";
      const statusClass = endpoint.available === true ? "ok" : endpoint.available === false ? "bad" : "warn";
      return `<article class="endpoint-card">
        <div class="endpoint-status"><span class="pill ${statusClass}">${status}</span><span class="endpoint-model-count"><strong>${count}</strong> registered model${count === 1 ? "" : "s"}</span></div>
        <div class="endpoint-copy"><h4>${escapeHtml(endpoint.name || endpoint.id)}</h4><p>${escapeHtml(endpoint.provider)} · ${escapeHtml(endpoint.url)}</p><small>Last tested: ${escapeHtml(formatDate(endpoint.lastTested))}</small></div>
        <div class="endpoint-actions"><button data-test-endpoint="${escapeAttr(endpoint.id)}">Test & reconcile models</button><button class="danger" data-delete-endpoint="${escapeAttr(endpoint.id)}">Remove</button></div>
      </article>`;
    })
    .join("");

  root.querySelectorAll("[data-test-endpoint]").forEach((button) =>
    button.addEventListener("click", async () => {
      setBusy(button, true, "Testing…");
      try {
        const result = await api(`/api/endpoints/${encodeURIComponent(button.dataset.testEndpoint)}/test`, { method: "POST" });
        if (!result.ok) throw new Error(result.error || "Connection test failed");
        const discovered = await api("/api/models/auto-detect", { method: "POST" });
        await Promise.all([refreshEndpoints(), refreshModels()]);
        const found = (result.models || []).length;
        const added = (discovered.added || []).filter((item) => item.endpointId === button.dataset.testEndpoint).length;
        showToast(`Connection healthy · ${found} model${found === 1 ? "" : "s"} found · ${added} added to the registry`);
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(button, false);
      }
    }),
  );

  root.querySelectorAll("[data-delete-endpoint]").forEach((button) =>
    button.addEventListener("click", async () => {
      setBusy(button, true, "Removing…");
      try {
        await api(`/api/endpoints/${encodeURIComponent(button.dataset.deleteEndpoint)}`, { method: "DELETE" });
        await Promise.all([refreshEndpoints(), refreshModels()]);
        showToast("Endpoint and linked models removed");
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(button, false);
      }
    }),
  );
}

function renderEndpointOptions() {
  $("model-endpoint").innerHTML = state.endpoints.length
    ? state.endpoints.map((endpoint) => `<option value="${escapeAttr(endpoint.id)}">${escapeHtml(endpoint.name || endpoint.id)}</option>`).join("")
    : '<option value="">Configure an endpoint first</option>';
}

function modelProvider(model) {
  return model.provider || state.endpoints.find((endpoint) => endpoint.id === model.endpointId)?.provider || "unknown";
}

function modelFamily(model) {
  const raw = String(model.id || "");
  const id = raw.toLowerCase();
  const known = [
    [/llama/, "Llama"],
    [/mistral|mixtral/, "Mistral"],
    [/gemma/, "Gemma"],
    [/qwen/, "Qwen"],
    [/deepseek/, "DeepSeek"],
    [/phi[-_ ]?\d|microsoft\/phi/, "Phi"],
    [/claude/, "Claude"],
    [/gpt|o1|o3|o4|codex/, "OpenAI"],
    [/nemotron/, "Nemotron"],
    [/command-r|cohere/, "Command"],
    [/embed|embedding|bge|nomic/, "Embeddings"],
    [/vision|multimodal|[-_]vl\b/, "Vision"],
    [/guard|moderation|safety/, "Safety"],
  ];
  for (const [pattern, label] of known) if (pattern.test(id)) return label;
  const tail = raw.split("/").pop().split(":")[0].split(/[-_]/)[0];
  return tail ? tail.charAt(0).toUpperCase() + tail.slice(1) : "Other";
}

function modelRole(model) {
  const id = String(model.id || "").toLowerCase();
  if (/embed|embedding|bge|nomic/.test(id)) return "Retrieval and semantic similarity";
  if (/vision|multimodal|[-_]vl\b/.test(id)) return "Vision and multimodal evaluation";
  if (/code|coder|codex|starcoder/.test(id)) return "Code generation and technical analysis";
  if (/reason|o1|o3|o4|r1/.test(id)) return "Reasoning and multi-step analysis";
  if (/guard|moderation|safety/.test(id)) return "Safety and policy classification";
  if (/mini|small|tiny|1b|3b|4b|7b|8b/.test(id)) return "Fast, cost-conscious evaluation";
  if (/70b|120b|large|pro|max/.test(id)) return "High-depth generation and analysis";
  return "General instruction following and analysis";
}

function modelDescription(model) {
  const endpoint = model.endpointName || model.endpointId || "an unlabelled endpoint";
  return `${modelFamily(model)} family model for ${modelRole(model).toLowerCase()}. Registered through ${endpoint} using the ${modelProvider(model)} adapter.`;
}

function filteredModels(searchId, providerId) {
  const query = ($(searchId)?.value || "").toLowerCase();
  const provider = $(providerId)?.value || "";
  return state.models.filter((model) => {
    const searchable = `${model.id} ${modelFamily(model)} ${model.endpointName || ""} ${modelProvider(model)}`.toLowerCase();
    return (!query || searchable.includes(query)) && (!provider || modelProvider(model) === provider);
  });
}

function popularScore(model) {
  const id = String(model.id || "").toLowerCase();
  let score = 0;
  if (/instruct|chat/.test(id)) score += 30;
  if (/llama|mistral|qwen|gemma|gpt|claude|nemotron/.test(id)) score += 20;
  if (/70b|32b|27b|14b|8b|7b/.test(id)) score += 10;
  if (/embed|guard|moderation/.test(id)) score -= 15;
  if (model.endpointAvailable === false) score -= 50;
  return score;
}

function modelChoiceMarkup(model, compact = false) {
  const selected = state.selectedModels.has(model.id);
  return `<button type="button" class="model-choice ${compact ? "compact" : ""} ${selected ? "selected" : ""}" aria-pressed="${selected}" data-model="${escapeAttr(model.id)}">
    <span class="model-choice-check">✓</span>
    <span class="model-choice-main"><span class="model-choice-title">${escapeHtml(model.id)}</span><span class="model-choice-meta">${escapeHtml(modelFamily(model))} · ${escapeHtml(modelProvider(model))}</span></span>
    <span class="pill ${model.endpointAvailable === false ? "bad" : "ok"}">${model.endpointAvailable === false ? "offline" : "ready"}</span>
  </button>`;
}

function wireModelChoices(root) {
  root.querySelectorAll("[data-model]").forEach((button) =>
    button.addEventListener("click", () => {
      const id = button.dataset.model;
      if (state.selectedModels.has(id)) state.selectedModels.delete(id);
      else state.selectedModels.add(id);
      renderSelectedModels();
      updateRunSummary();
      if (!$("model-picker-overlay").classList.contains("hidden")) {
        renderModelPicker();
      } else {
        renderModelSelector();
      }
    }),
  );
}

function renderModels() {
  const items = filteredModels("model-search", "model-provider-filter");
  $("model-result-count").textContent = `${items.length} model${items.length === 1 ? "" : "s"}`;
  const root = $("model-grid");
  if (!items.length) {
    root.innerHTML = '<div class="empty">No models match the current filters.</div>';
    return;
  }
  root.innerHTML = items
    .map(
      (model) => `<article class="model-card">
        <div class="section-title"><div class="model-card-pills"><span class="pill">${escapeHtml(modelFamily(model))}</span><span class="pill ${model.endpointAvailable === false ? "bad" : "ok"}">${escapeHtml(modelProvider(model))}</span></div><button class="danger" data-delete-model="${escapeAttr(model.id)}">Remove</button></div>
        <div class="model-id">${escapeHtml(model.id)}</div>
        <p class="model-description">${escapeHtml(modelDescription(model))}</p>
        <div class="model-lineage"><span>Endpoint: ${escapeHtml(model.endpointName || model.endpointId || "Unlinked")}</span><span>Endpoint ID: ${escapeHtml(model.endpointId || "—")}</span><span>Role: ${escapeHtml(modelRole(model))}</span></div>
      </article>`,
    )
    .join("");
  root.querySelectorAll("[data-delete-model]").forEach((button) =>
    button.addEventListener("click", async () => {
      const id = button.dataset.deleteModel;
      setBusy(button, true, "Removing…");
      try {
        await api(`/api/models/${encodeURIComponent(id)}`, { method: "DELETE" });
        state.selectedModels.delete(id);
        await refreshModels();
        showToast(`${id} removed`);
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(button, false);
      }
    }),
  );
}

function renderModelSelector() {
  const items = filteredModels("generation-model-search", "generation-provider-filter");
  const popular = [...items].sort((a, b) => popularScore(b) - popularScore(a) || a.id.localeCompare(b.id)).slice(0, 6);
  const popularRoot = $("popular-models");
  popularRoot.innerHTML = popular.length ? popular.map((model) => modelChoiceMarkup(model, true)).join("") : '<div class="empty compact-empty">No popular models match the current filters.</div>';
  wireModelChoices(popularRoot);

  renderSelectedModels();
}

function renderSelectedModels() {
  const chipsRoot = $("selected-model-chips");
  if (!chipsRoot) return;
  if (!state.selectedModels.size) {
    chipsRoot.innerHTML = '<div class="empty compact-empty">No models selected yet. Open the picker to choose.</div>';
    return;
  }
  const selected = state.models.filter((model) => state.selectedModels.has(model.id));
  chipsRoot.innerHTML = selected
    .map((model) => `<span class="selected-model-chip">${escapeHtml(model.id)}<span class="muted">·</span><button type="button" data-remove-model="${escapeAttr(model.id)}" aria-label="Remove ${escapeHtml(model.id)}">✕</button></span>`)
    .join("");
  chipsRoot.querySelectorAll("[data-remove-model]").forEach((button) =>
    button.addEventListener("click", () => {
      const id = button.dataset.removeModel;
      state.selectedModels.delete(id);
      renderSelectedModels();
      renderModelSelector();
      updateRunSummary();
    }),
  );
}

function renderModelPicker() {
  const pickerItems = filteredModels("picker-model-search", "picker-provider-filter");
  const popular = [...pickerItems].sort((a, b) => popularScore(b) - popularScore(a) || a.id.localeCompare(b.id)).slice(0, 6);
  const popularRoot = $("picker-popular-grid");
  popularRoot.innerHTML = popular.length ? popular.map((model) => modelChoiceMarkup(model, true)).join("") : '<div class="empty compact-empty">No popular models match the current filters.</div>';
  wireModelChoices(popularRoot);

  const groups = new Map();
  for (const model of pickerItems) {
    const family = modelFamily(model);
    if (!groups.has(family)) groups.set(family, []);
    groups.get(family).push(model);
  }
  const familyRoot = $("picker-model-families");
  if (!groups.size) {
    familyRoot.innerHTML = '<div class="empty compact-empty">No model families match the current filters.</div>';
    updatePickerSelectionCount();
    return;
  }
  familyRoot.innerHTML = [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([family, models]) => {
      const selected = models.filter((model) => state.selectedModels.has(model.id)).length;
      const open = state.openFamilies.has(family);
      return `<section class="model-family ${open ? "open" : ""}" data-family="${escapeAttr(family)}">
        <button type="button" class="model-family-header" data-toggle-family="${escapeAttr(family)}" aria-expanded="${open}">
          <span><strong>${escapeHtml(family)}</strong><small>${models.length} model${models.length === 1 ? "" : "s"} · ${selected} selected</small></span><span class="family-chevron">⌄</span>
        </button>
        <div class="model-family-body">${models.map((model) => modelChoiceMarkup(model)).join("")}</div>
      </section>`;
    })
    .join("");
  familyRoot.querySelectorAll("[data-toggle-family]").forEach((button) =>
    button.addEventListener("click", () => {
      const family = button.dataset.toggleFamily;
      if (state.openFamilies.has(family)) state.openFamilies.delete(family);
      else state.openFamilies.add(family);
      localStorage.setItem("we3.openFamilies", JSON.stringify([...state.openFamilies]));
      renderModelPicker();
    }),
  );
  wireModelChoices(familyRoot);
  updatePickerSelectionCount();
}

function updatePickerSelectionCount() {
  const count = $("picker-selection-count");
  if (count) count.textContent = `${state.selectedModels.size} selected`;
}

function openModelPicker() {
  $("model-picker-overlay").classList.remove("hidden");
  $("model-picker-dialog").focus();
  document.body.classList.add("dialog-open");
  renderModelPicker();
}

function closeModelPicker() {
  $("model-picker-overlay").classList.add("hidden");
  document.body.classList.remove("dialog-open");
}

function applyPackage() {
  const selected = state.packages.find((item) => item.id === $("prompt-package").value);
  state.prompts = (selected?.prompts || []).slice();
  $("prompt-count").max = Math.max(1, state.prompts.length);
  $("prompt-count").value = Math.max(1, state.prompts.length);
  renderPrompts();
  updateRunSummary();
}

function renderPrompts() {
  const root = $("prompt-list");
  if (!state.prompts.length) {
    root.innerHTML = '<div class="empty">Choose a package or add a custom prompt.</div>';
    return;
  }
  root.innerHTML = state.prompts
    .map((prompt, index) => `<div class="prompt-row"><span class="pill">${index + 1}</span><textarea data-prompt="${index}" aria-label="Prompt ${index + 1}">${escapeHtml(prompt)}</textarea><button class="danger" type="button" data-remove-prompt="${index}">Remove</button></div>`)
    .join("");
  root.querySelectorAll("[data-prompt]").forEach((textarea) =>
    textarea.addEventListener("input", () => {
      state.prompts[Number(textarea.dataset.prompt)] = textarea.value;
      updateRunSummary();
    }),
  );
  root.querySelectorAll("[data-remove-prompt]").forEach((button) =>
    button.addEventListener("click", () => {
      state.prompts.splice(Number(button.dataset.removePrompt), 1);
      $("prompt-count").max = Math.max(1, state.prompts.length);
      $("prompt-count").value = Math.min(Number($("prompt-count").value), Math.max(1, state.prompts.length));
      renderPrompts();
      updateRunSummary();
    }),
  );
}

function updateRunSummary() {
  const count = Math.min(Number($("prompt-count").value || state.prompts.length), state.prompts.length);
  const prompts = state.prompts.slice(0, count).map((item) => item.trim()).filter(Boolean);
  $("prompt-count-label").textContent = count;
  $("selection-count").textContent = `${state.selectedModels.size} selected`;
  $("summary-models").textContent = state.selectedModels.size;
  $("summary-prompts").textContent = prompts.length;
  $("summary-requests").textContent = state.selectedModels.size * prompts.length;
  $("summary-mode").textContent = $("execution-mode").value;
  const ready = state.selectedModels.size > 0 && prompts.length > 0;
  $("generation-readiness").textContent = ready ? `Ready to run ${state.selectedModels.size * prompts.length} model-prompt requests.` : "Select at least one model and add a prompt.";
  $("generation-readiness").classList.toggle("ready", ready);
  $("start-generation").disabled = !ready;
}

function updateJob(job) {
  if (!job) return;
  state.job = { ...(state.job || {}), ...job };
  const status = state.job.status || "queued";
  const total = Number(state.job.total_reports || 0);
  const completed = Number(state.job.completed_reports || 0);
  const failed = Number(state.job.failed_reports || 0);
  const percentage = Math.min(100, Number(state.job.overall_percentage ?? (total ? Math.round(((completed + failed) / total) * 100) : 0)));
  $("job-progress-bar").style.width = `${percentage}%`;
  $("job-percent").textContent = `${percentage}%`;
  $("job-status").textContent = status.replaceAll("_", " ");
  $("job-status").className = `pill ${status === "completed" ? "ok" : ["failed", "cancelled", "interrupted"].includes(status) ? "bad" : "warn"}`;
  $("job-step").textContent = state.job.current_step || "Working";
  $("job-complete").textContent = completed;
  $("job-failed").textContent = failed;
  $("job-total").textContent = total || "—";
  $("job-current").textContent = state.job.current_model || state.job.current_invocation || "—";
  $("job-card").classList.remove("hidden");
  $("job-models").innerHTML =
    Object.entries(state.job.models_state || {})
      .map(([id, item]) => `<div class="item"><span class="pill ${item.status === "completed" ? "ok" : item.status === "failed" ? "bad" : "warn"}">${escapeHtml(item.status || "queued")}</span><div class="item-main"><div class="item-title">${escapeHtml(id)}</div><div class="item-meta">${escapeHtml(item.current_step || "")}</div></div><span class="muted">${Number(item.percentage || 0)}%</span></div>`)
      .join("") || '<div class="muted">Waiting for per-model events…</div>';
  const action = $("cancel-job");
  if (terminalStates.has(status) && status !== "completed") {
    action.textContent = "Retry run";
    action.classList.remove("danger");
    action.dataset.action = "retry";
    action.disabled = false;
  } else if (terminalStates.has(status)) {
    action.textContent = "Run completed";
    action.dataset.action = "done";
    action.disabled = true;
  } else {
    action.textContent = status === "cancelling" ? "Cancelling…" : "Cancel run";
    action.classList.add("danger");
    action.dataset.action = "cancel";
    action.disabled = status === "cancelling";
  }
}

function normalizeCharts(run) {
  if (Array.isArray(run.charts)) return run.charts;
  if (run.chartUrls && typeof run.chartUrls === "object") {
    return Object.entries(run.chartUrls).map(([name, url]) => ({ name, url, displayName: state.chartMetadata[name]?.name, category: state.chartMetadata[name]?.category, description: state.chartMetadata[name]?.description }));
  }
  return [];
}

function mergedChartRuns() {
  const existing = new Map(state.chartRuns.map((run) => [run.runId, { ...run, charts: normalizeCharts(run) }]));
  for (const telemetry of state.telemetryRuns.filter((run) => run.type === "report_generation")) {
    const current = existing.get(telemetry.runId);
    if (current) existing.set(telemetry.runId, { ...telemetry, ...current, charts: current.charts });
    else existing.set(telemetry.runId, { ...telemetry, charts: [], missing: true });
  }
  return [...existing.values()].sort((a, b) => new Date(b.finishedAt || b.timestamp || 0) - new Date(a.finishedAt || a.timestamp || 0));
}

async function generateChartsForRun(runId, button) {
  setBusy(button, true, "Generating…");
  try {
    const result = await api("/api/charts/generate", { method: "POST", body: JSON.stringify({ runId }) });
    showToast(result.reused ? "Existing chart set is already complete" : `Generated ${result.generated || 0} charts for ${runId}`);
    await refreshCharts();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

function renderCharts() {
  const root = $("chart-runs");
  const runs = mergedChartRuns();
  if (!runs.length) {
    root.innerHTML = '<div class="empty">No evidence runs are available. Complete a report run or generate the explicit demonstration set.</div>';
    return;
  }
  const colors = ["cyan", "yellow", "violet", "green", "orange", ""];
  root.innerHTML = runs
    .filter((run) => {
      // Do not render empty frames — a run-window frame remains visible
      // only while it contains one or more charts.
      const charts = normalizeCharts(run);
      return charts.length > 0;
    })
    .map((run, index) => {
      const runId = run.runId;
      const charts = normalizeCharts(run);
      const collapsed = state.collapsedRuns.has(runId);
      const deleted = Array.isArray(run.deletedCharts) ? run.deletedCharts : [];
      const missingCount = Math.max(0, Object.keys(state.chartMetadata).length - charts.length);
      const stateLabel = run.isSample ? "demo run" : charts.length ? "evidence run" : deleted.includes("__all__") ? "charts deleted" : "charts missing";
      return `<section class="chart-run-frame ${collapsed ? "collapsed" : ""}" data-color="${colors[index % colors.length]}" data-run-id="${escapeAttr(runId)}">
        <header class="chart-run-head">
          <div class="chart-run-title"><span class="pill ${charts.length ? "ok" : "warn"}">${stateLabel}</span><h3>${escapeHtml(run.runName || runId)}</h3><p>${escapeHtml((run.models || []).join(", ") || (run.isSample ? "Synthetic demonstration models" : "Models not recorded"))} · ${escapeHtml(formatDate(run.finishedAt || run.timestamp))}</p></div>
          <div class="chart-run-actions"><button data-run-detail="${escapeAttr(runId)}">Data & metadata</button><button data-toggle-run="${escapeAttr(runId)}">${collapsed ? "Expand" : "Minimize"}</button><button class="primary" data-generate-run="${escapeAttr(runId)}">${charts.length ? `Generate ${missingCount ? "missing" : "again"}` : "Generate charts"}</button>${charts.length ? `<button class="danger" data-delete-run="${escapeAttr(runId)}">Delete charts</button>` : ""}</div>
        </header>
        <div class="chart-run-summary"><span><strong>${charts.length}</strong> available</span><span><strong>${missingCount}</strong> missing</span><span><strong>${(run.prompts || []).length}</strong> prompts</span><span><strong>${(run.models || []).length}</strong> models</span></div>
        <div class="chart-run-body"><div class="chart-grid">${charts
          .map((chart) => {
            const meta = state.chartMetadata[chart.name] || {};
            return `<article class="chart-card"><button class="chart-close" data-delete-chart="${escapeAttr(runId)}::${escapeAttr(chart.name)}" aria-label="Delete ${escapeAttr(chart.displayName || chart.name)}">×</button><button class="chart-card-image-button" data-open-chart="${escapeAttr(runId)}::${escapeAttr(chart.name)}"><img loading="lazy" src="${escapeAttr(chart.url)}" alt="${escapeAttr(chart.displayName || meta.name || chart.name)}"><span class="chart-load-fallback">Chart image unavailable</span></button><h4>${escapeHtml(chart.displayName || meta.name || chart.name)}</h4><p class="chart-card-description">${escapeHtml(chart.description || meta.description || "Generated evaluation chart.")}</p><div class="chart-card-footer"><span class="pill">${escapeHtml(chart.category || meta.category || "Analysis")}</span><button data-chart-detail="${escapeAttr(runId)}::${escapeAttr(chart.name)}">Data</button></div></article>`;
          })
          .join("") || `<div class="empty run-empty"><h4>No chart files are currently available</h4><p>${deleted.length ? "Deleted charts stay deleted after refresh. Use Generate charts to explicitly restore this run." : "This evidence run is ready for chart generation."}</p><button class="primary" data-generate-run="${escapeAttr(runId)}">Generate charts for this run</button></div>`}</div></div>
      </section>`;
    })
    .join("");

  root.querySelectorAll("img").forEach((image) => {
    image.addEventListener("load", () => image.closest(".chart-card")?.classList.add("image-ready"));
    image.addEventListener("error", () => image.closest(".chart-card")?.classList.add("image-failed"));
  });
  root.querySelectorAll("[data-toggle-run]").forEach((button) =>
    button.addEventListener("click", () => {
      const id = button.dataset.toggleRun;
      if (state.collapsedRuns.has(id)) state.collapsedRuns.delete(id);
      else state.collapsedRuns.add(id);
      localStorage.setItem("we3.collapsedRuns", JSON.stringify([...state.collapsedRuns]));
      stableRender(renderCharts);
    }),
  );
  root.querySelectorAll("[data-run-detail]").forEach((button) => button.addEventListener("click", () => openRun(button.dataset.runDetail)));
  root.querySelectorAll("[data-generate-run]").forEach((button) => button.addEventListener("click", () => generateChartsForRun(button.dataset.generateRun, button)));
  root.querySelectorAll("[data-open-chart]").forEach((button) => button.addEventListener("click", () => openChart(...button.dataset.openChart.split("::"))));
  root.querySelectorAll("[data-chart-detail]").forEach((button) =>
    button.addEventListener("click", () => {
      const [runId, name] = button.dataset.chartDetail.split("::");
      const run = runs.find((item) => item.runId === runId);
      openDrawer(name, { ...(state.chartMetadata[name] || {}), runId, models: run?.models, prompts: run?.prompts });
    }),
  );
  root.querySelectorAll("[data-delete-chart]").forEach((button) =>
    button.addEventListener("click", async () => {
      const [runId, name] = button.dataset.deleteChart.split("::");
      setBusy(button, true, "…");
      try {
        await api(`/api/charts/runs/${encodeURIComponent(runId)}/${encodeURIComponent(name)}`, { method: "DELETE" });
        closeChart();

        // After deletion, refresh the chart runs data. If the run no longer
        // has any charts, the renderCharts() filter will automatically hide
        // the empty run-window frame.
        await refreshCharts();

        // Check whether the run frame should be removed
        const runFrame = root.querySelector(`[data-run-id="${escapeAttr(runId)}"]`);
        if (runFrame) {
          const remainingCards = runFrame.querySelectorAll(".chart-card").length;
          if (remainingCards === 0) {
            runFrame.remove();
          }
        }
        showToast(`${name} deleted. The chart and its evidence are removed.`);
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(button, false);
      }
    }),
  );
  root.querySelectorAll("[data-delete-run]").forEach((button) =>
    button.addEventListener("click", async () => {
      const runId = button.dataset.deleteRun;
      setBusy(button, true, "Deleting…");
      try {
        await api(`/api/charts/runs/${encodeURIComponent(runId)}/all`, { method: "DELETE" });
        closeChart();
        await refreshCharts();
        showToast(`Charts for ${runId} deleted. The evidence run remains available for explicit regeneration.`);
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(button, false);
      }
    }),
  );
}

function openChart(runId, name) {
  const run = mergedChartRuns().find((item) => item.runId === runId);
  const chart = normalizeCharts(run || {}).find((item) => item.name === name);
  if (!run || !chart) return;
  const meta = state.chartMetadata[name] || {};
  $("chart-window-title").textContent = chart.displayName || meta.name || name;
  $("chart-window-category").textContent = chart.category || meta.category || "Analysis";
  $("chart-window-image").src = chart.url;
  $("chart-window-image").alt = chart.displayName || meta.name || name;
  $("chart-window-empty").classList.add("hidden");
  $("chart-window-description").textContent = chart.description || meta.description || "No chart description is available.";
  const fields = { Run: runId, Models: (run.models || []).join(", ") || "Not recorded", Prompts: (run.prompts || []).length, Package: run.promptPackage || "Custom / not recorded", Finished: formatDate(run.finishedAt), File: chart.url, Size: formatBytes(chart.size_bytes || chart.sizeBytes) };
  $("chart-window-metadata").innerHTML = Object.entries(fields).map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`).join("");
  $("chart-window").classList.remove("hidden");
  $("chart-window").focus();
}

function closeChart() {
  $("chart-window").classList.add("hidden");
  $("chart-window").classList.remove("fullscreen");
  $("chart-window-fullscreen").textContent = "Full screen";
}

function initializeChartWindow() {
  const windowElement = $("chart-window");
  const handle = $("chart-window-handle");
  const resize = windowElement.querySelector(".resize-handle");
  let drag = null;
  handle.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button") || windowElement.classList.contains("fullscreen")) return;
    drag = { x: event.clientX, y: event.clientY, left: windowElement.offsetLeft, top: windowElement.offsetTop };
    handle.setPointerCapture(event.pointerId);
  });
  handle.addEventListener("pointermove", (event) => {
    if (!drag) return;
    windowElement.style.left = `${Math.max(0, drag.left + event.clientX - drag.x)}px`;
    windowElement.style.top = `${Math.max(0, drag.top + event.clientY - drag.y)}px`;
  });
  handle.addEventListener("pointerup", () => (drag = null));
  let sizing = null;
  resize.addEventListener("pointerdown", (event) => {
    if (windowElement.classList.contains("fullscreen")) return;
    sizing = { x: event.clientX, y: event.clientY, width: windowElement.offsetWidth, height: windowElement.offsetHeight };
    resize.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  resize.addEventListener("pointermove", (event) => {
    if (!sizing) return;
    windowElement.style.width = `${Math.max(520, sizing.width + event.clientX - sizing.x)}px`;
    windowElement.style.height = `${Math.max(380, sizing.height + event.clientY - sizing.y)}px`;
  });
  resize.addEventListener("pointerup", () => (sizing = null));
  $("chart-window-close").addEventListener("click", closeChart);
  $("chart-window-fullscreen").addEventListener("click", () => {
    const full = windowElement.classList.toggle("fullscreen");
    $("chart-window-fullscreen").textContent = full ? "Restore window" : "Full screen";
  });
  $("chart-window-data").addEventListener("click", () => windowElement.querySelector(".chart-metadata")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  $("chart-window-image").addEventListener("error", () => $("chart-window-empty").classList.remove("hidden"));
  $("chart-window-image").addEventListener("load", () => $("chart-window-empty").classList.add("hidden"));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !windowElement.classList.contains("hidden")) closeChart();
  });
}

function reportSummary(report) {
  const models = report.models || [];
  if (models.length) return `Evaluation evidence for ${models.length} model${models.length === 1 ? "" : "s"}: ${models.slice(0, 3).join(", ")}${models.length > 3 ? ` and ${models.length - 3} more` : ""}.`;
  if (report.runId) return `Evaluation report produced by evidence run ${report.runId}.`;
  return "Legacy evaluation artifact. Open the PDF to inspect its methodology, findings, and evidence.";
}

function renderReports() {
  const root = $("report-grid");
  if (!state.reports.length) {
    root.innerHTML = '<div class="empty">No PDF reports generated.</div>';
    return;
  }
  root.innerHTML = state.reports
    .map(
      (report) => `<article class="report-card">
        <div class="section-title"><div><span class="pill ${report.status === "completed" ? "ok" : report.status ? "warn" : "ok"}">PDF report</span><h3>${escapeHtml(report.name)}</h3></div><span class="muted">${escapeHtml(formatBytes(report.sizeBytes || report.size_bytes))}</span></div>
        <div class="report-understanding"><strong>What this report contains</strong><p>${escapeHtml(reportSummary(report))}</p><dl><dt>Run</dt><dd>${escapeHtml(report.runId || "Legacy artifact")}</dd><dt>Models</dt><dd>${escapeHtml((report.models || []).join(", ") || "Not recorded")}</dd><dt>Modified</dt><dd>${escapeHtml(formatDate(report.modified))}</dd></dl></div>
        <button type="button" class="report-view-toggle primary" data-toggle-report="${escapeAttr(report.name)}">View report in card</button>
        <div class="report-viewer" data-report-viewer="${escapeAttr(report.name)}" hidden><iframe class="pdf-preview" loading="lazy" data-src="${escapeAttr(report.url)}#toolbar=1&navpanes=0&view=FitH" title="Preview of ${escapeAttr(report.name)}"></iframe></div>
        <div class="report-integrity"><span>SHA-256</span><code>${escapeHtml(report.sha256 || "Not recorded")}</code></div>
        <div class="actions"><a class="btn" target="_blank" rel="noopener" href="${escapeAttr(report.url)}">Open full report</a>${report.runId ? `<a class="btn" href="/api/telemetry/runs/${encodeURIComponent(report.runId)}/zip">Export evidence bundle</a>` : ""}<button class="danger" data-delete-report="${escapeAttr(report.name)}">Delete</button></div>
      </article>`,
    )
    .join("");
  root.querySelectorAll("[data-toggle-report]").forEach((button) =>
    button.addEventListener("click", () => {
      const viewer = root.querySelector(`[data-report-viewer="${CSS.escape(button.dataset.toggleReport)}"]`);
      const iframe = viewer.querySelector("iframe");
      const opening = viewer.hidden;
      viewer.hidden = !opening;
      if (opening && !iframe.src) iframe.src = iframe.dataset.src;
      button.textContent = opening ? "Hide in-card viewer" : "View report in card";
    }),
  );
  root.querySelectorAll("[data-delete-report]").forEach((button) =>
    button.addEventListener("click", async () => {
      setBusy(button, true, "Deleting…");
      try {
        await api(`/api/reports/${encodeURIComponent(button.dataset.deleteReport)}`, { method: "DELETE" });
        await refreshReports();
        showToast("Report deleted");
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(button, false);
      }
    }),
  );
}

async function openRun(runId) {
  try {
    const payload = await api(`/api/telemetry/runs/${encodeURIComponent(runId)}`);
    openDrawer(`Run ${runId}`, payload.run || payload);
  } catch (error) {
    const local = mergedChartRuns().find((item) => item.runId === runId);
    if (local) openDrawer(`Run ${runId}`, local);
    else showToast(error.message, true);
  }
}

function openDrawer(title, data) {
  $("drawer-title").textContent = title;
  $("drawer-json").textContent = JSON.stringify(data, null, 2);
  $("drawer").classList.add("open");
}

async function submitGeneration(event) {
  event.preventDefault();
  const count = Math.min(Number($("prompt-count").value), state.prompts.length);
  const prompts = state.prompts.slice(0, count).map((item) => item.trim()).filter(Boolean);
  if (!state.selectedModels.size) return showToast("Select at least one model", true);
  if (!prompts.length) return showToast("Add at least one prompt", true);
  const request = { models: [...state.selectedModels], prompts, promptPackage: $("prompt-package").value, promptCount: prompts.length, executionMode: $("execution-mode").value, batchSize: 1, timeoutSeconds: 600, failurePolicy: "continue", autoCharts: true };
  const submit = $("start-generation");
  setBusy(submit, true, "Starting…");
  try {
    try {
      const payload = await api("/api/jobs", { method: "POST", body: JSON.stringify(request) });
      localStorage.setItem("we3.job", payload.job.job_id);
      updateJob(payload.job);
      send("subscribe_job", { job_id: payload.job.job_id });
      showToast("Evaluation job started");
    } catch (error) {
      if (error.status !== 405) throw error;
      if (!send("generate_reports", request)) throw new Error("The compatibility connection is offline");
      showToast("Evaluation submitted through the compatibility connection");
    }
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(submit, false);
  }
}

async function initializeData() {
  await Promise.all([refreshEndpoints(), refreshModels(), refreshPackages(), refreshReports(), refreshCharts()]);
  const jobId = localStorage.getItem("we3.job");
  if (jobId) {
    try {
      const payload = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      updateJob(payload.job);
      if (terminalStates.has(payload.job.status)) localStorage.removeItem("we3.job");
    } catch {
      send("get_job", { job_id: jobId });
    }
  }
}

function init() {
  document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => setTab(button.dataset.tab)));
  $("drawer-close").addEventListener("click", () => $("drawer").classList.remove("open"));
  $("endpoint-provider").addEventListener("change", () => {
    const provider = $("endpoint-provider").value;
    if (provider.endsWith("_cli")) {
      $("endpoint-url").value = `cli://${provider.replace("_cli", "")}`;
      $("endpoint-key").value = "";
      $("endpoint-key").disabled = true;
    } else $("endpoint-key").disabled = false;
  });
  $("endpoint-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = event.submitter;
    setBusy(submit, true, "Saving…");
    try {
      await api("/api/endpoints", { method: "POST", body: JSON.stringify({ name: $("endpoint-name").value, url: $("endpoint-url").value, provider: $("endpoint-provider").value, apiKey: $("endpoint-key").value || null }) });
      event.currentTarget.reset();
      $("endpoint-key").disabled = false;
      await Promise.all([refreshEndpoints(), refreshModels()]);
      showToast("Endpoint saved");
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(submit, false);
    }
  });
  $("detect-endpoints").addEventListener("click", async (event) => {
    setBusy(event.currentTarget, true, "Detecting…");
    try {
      await api("/api/endpoints/auto-detect", { method: "POST" });
      await refreshEndpoints();
      showToast("Endpoint detection completed");
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(event.currentTarget, false);
    }
  });
  $("refresh-endpoints").addEventListener("click", async (event) => {
    setBusy(event.currentTarget, true, "Checking…");
    try {
      await api("/api/endpoints/status", { method: "POST" });
      await Promise.all([refreshEndpoints(), refreshModels()]);
      showToast("Endpoint health refreshed");
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(event.currentTarget, false);
    }
  });
  $("model-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = event.submitter;
    setBusy(submit, true, "Adding…");
    try {
      await api("/api/models", { method: "POST", body: JSON.stringify({ id: $("model-id").value.trim(), endpointId: $("model-endpoint").value }) });
      $("model-id").value = "";
      await refreshModels();
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(submit, false);
    }
  });
  $("detect-models").addEventListener("click", async (event) => {
    setBusy(event.currentTarget, true, "Discovering…");
    try {
      const result = await api("/api/models/auto-detect", { method: "POST" });
      await refreshModels();
      showToast(`Model discovery completed · ${(result.added || []).length} new model${(result.added || []).length === 1 ? "" : "s"}`);
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(event.currentTarget, false);
    }
  });
  $("model-search").addEventListener("input", renderModels);
  $("model-provider-filter").addEventListener("change", renderModels);
  $("generation-model-search").addEventListener("input", renderModelSelector);
  $("generation-provider-filter").addEventListener("change", renderModelSelector);
  $("prompt-package").addEventListener("change", applyPackage);
  $("add-prompt").addEventListener("click", () => {
    state.prompts.push("");
    $("prompt-count").max = Math.max(1, state.prompts.length);
    $("prompt-count").value = Math.max(1, state.prompts.length);
    renderPrompts();
    updateRunSummary();
  });
  $("prompt-count").addEventListener("input", updateRunSummary);
  $("execution-mode").addEventListener("change", updateRunSummary);
  $("select-all").addEventListener("click", () => {
    filteredModels("generation-model-search", "generation-provider-filter").forEach((model) => state.selectedModels.add(model.id));
    renderModelSelector();
    updateRunSummary();
  });
  $("select-none").addEventListener("click", () => {
    state.selectedModels.clear();
    renderModelSelector();
    updateRunSummary();
  });
  $("open-model-picker").addEventListener("click", openModelPicker);
  $("model-picker-close").addEventListener("click", closeModelPicker);
  $("model-picker-cancel").addEventListener("click", closeModelPicker);
  $("picker-apply").addEventListener("click", () => {
    renderSelectedModels();
    updateRunSummary();
    closeModelPicker();
  });
  $("picker-model-search").addEventListener("input", renderModelPicker);
  $("picker-provider-filter").addEventListener("change", renderModelPicker);
  $("model-picker-overlay").addEventListener("click", (event) => {
    if (event.target === $("model-picker-overlay")) closeModelPicker();
  });
  $("model-picker-select-all").addEventListener("click", () => {
    filteredModels("picker-model-search", "picker-provider-filter").forEach((model) => state.selectedModels.add(model.id));
    renderModelPicker();
    updatePickerSelectionCount();
  });
  $("model-picker-clear-all").addEventListener("click", () => {
    const visible = filteredModels("picker-model-search", "picker-provider-filter");
    for (const model of visible) state.selectedModels.delete(model.id);
    renderModelPicker();
    updatePickerSelectionCount();
  });
  $("generate-form").addEventListener("submit", submitGeneration);
  $("cancel-job").addEventListener("click", async (event) => {
    const jobId = state.job?.job_id || localStorage.getItem("we3.job");
    if (!jobId || event.currentTarget.dataset.action === "done") return;
    setBusy(event.currentTarget, true, event.currentTarget.dataset.action === "retry" ? "Retrying…" : "Cancelling…");
    try {
      if (event.currentTarget.dataset.action === "retry") {
        try {
          const payload = await api(`/api/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" });
          localStorage.setItem("we3.job", payload.job.job_id);
          updateJob(payload.job);
          send("subscribe_job", { job_id: payload.job.job_id });
        } catch (error) {
          if (error.status !== 405) throw error;
          send("retry_job", { job_id: jobId });
        }
      } else {
        try {
          const payload = await api(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
          updateJob(payload.job);
        } catch (error) {
          if (error.status !== 405) throw error;
          send("cancel_job", { job_id: jobId });
        }
      }
    } catch (error) {
      showToast(error.message, true);
    } finally {
      event.currentTarget.disabled = false;
    }
  });
  $("refresh-charts").addEventListener("click", refreshCharts);
  $("generate-demo-charts").addEventListener("click", async (event) => {
    setBusy(event.currentTarget, true, "Generating demo…");
    try {
      const result = await api("/api/charts/demo", { method: "POST" });
      showToast(`Generated ${result.generated || 0} demonstration charts`);
      await refreshCharts();
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(event.currentTarget, false);
    }
  });
  $("delete-all-charts").addEventListener("click", async (event) => {
    if (!confirm("Delete ALL chart images and frames? This cannot be undone.")) return;
    setBusy(event.currentTarget, true, "Deleting all…");
    try {
      await api("/api/charts/runs/all", { method: "DELETE" });
      $("chart-runs").innerHTML = '<div class="empty">All chart images and frames have been removed. Complete a report run or generate the explicit demonstration set.</div>';
      showToast("All chart images and run-window frames have been deleted.");
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(event.currentTarget, false);
    }
  });
  $("refresh-reports").addEventListener("click", refreshReports);
  initializeChartWindow();
  setTab(localStorage.getItem("we3.tab") || "endpoints");
  renderPrompts();
  updateRunSummary();
  connect();
  initializeData();
}

document.addEventListener("DOMContentLoaded", init);
