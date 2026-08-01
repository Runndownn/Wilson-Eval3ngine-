const state = {
  endpoints: [],
  models: [],
  packages: [],
  runs: [],
  reports: [],
  chartsMeta: {},
  selectedModels: new Set(),
  prompts: [],
  job: null,
  ws: null,
  reconnectTimer: null,
};

const $ = (id) => document.getElementById(id);
const terminalStates = new Set([
  "completed",
  "completed_with_errors",
  "failed",
  "cancelled",
  "interrupted",
]);

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = value ?? "";
  return node.innerHTML;
}

function showToast(message, isError = false) {
  const element = $("toast");
  element.textContent = String(message || "Unknown error");
  element.style.borderColor = isError ? "rgba(251,113,133,.55)" : "";
  element.classList.add("show");
  window.setTimeout(() => element.classList.remove("show"), 4200);
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

  let payload = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    payload = await response.json();
  }

  if (!response.ok) {
    const detail = payload?.detail || payload?.error || `${response.status} ${response.statusText}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload || {};
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

function send(action, payload = {}) {
  if (state.ws?.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({ action, ...payload }));
    return true;
  }
  showToast("Live backend connection is not ready", true);
  return false;
}

function setTab(name) {
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `panel-${name}`);
  });
  localStorage.setItem("we3.tab", name);
  if (name === "charts") refreshCharts();
  if (name === "reports") refreshReports();
}

function setConnectionState(connected, text) {
  $("health-dot").classList.toggle("online", connected);
  $("health-text").textContent = text;
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

function handleSocketMessage(message) {
  if (message.error) {
    showToast(message.error, true);
    return;
  }

  switch (message.action) {
    case "generate_reports":
    case "retry_job": {
      const job = message.job;
      if (!job) return;
      localStorage.setItem("we3.job", job.job_id);
      updateJob(job);
      setTab("generate");
      break;
    }
    case "job_update":
      updateJob(message.job);
      if (message.job && terminalStates.has(message.job.status)) {
        localStorage.removeItem("we3.job");
        refreshReports();
        refreshCharts();
      }
      break;
    case "cancel_job":
      updateJob(message.job);
      break;
    case "hello":
    case "pong":
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
    $("stat-runs").textContent = overview.runs ?? state.runs.length;
    $("stat-reports").textContent = overview.reports ?? state.reports.length;
  } catch (error) {
    console.warn(error);
  }
}

async function refreshEndpoints() {
  try {
    const payload = await api("/api/endpoints");
    state.endpoints = payload.endpoints || [];
    renderEndpoints();
    renderEndpointOptions();
    await refreshOverview();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshModels() {
  try {
    const payload = await api("/api/models");
    state.models = payload.models || [];
    const registered = new Set(state.models.map((model) => model.id));
    for (const selected of [...state.selectedModels]) {
      if (!registered.has(selected)) state.selectedModels.delete(selected);
    }
    renderModels();
    renderModelSelector();
    updateRunSummary();
    await refreshOverview();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshPackages() {
  try {
    const payload = await api("/api/prompts/packages");
    state.packages = payload.packages || [];
    renderPackages();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshReports() {
  try {
    const payload = await api("/api/reports");
    state.reports = payload.reports || [];
    renderReports();
    await refreshOverview();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshCharts() {
  try {
    const [runsPayload, metadataPayload] = await Promise.all([
      api("/api/charts/runs"),
      api("/api/charts/metadata"),
    ]);
    state.runs = runsPayload.runs || [];
    state.chartsMeta = metadataPayload.charts || {};
    renderCharts();
    await refreshOverview();
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderEndpoints() {
  const root = $("endpoint-list");
  if (!state.endpoints.length) {
    root.innerHTML = '<div class="empty">No endpoints configured.</div>';
    return;
  }

  root.innerHTML = state.endpoints
    .map(
      (endpoint) => `
        <div class="item">
          <span class="pill ${endpoint.available === true ? "ok" : endpoint.available === false ? "bad" : "warn"}">
            ${endpoint.available === true ? "online" : endpoint.available === false ? "offline" : "unknown"}
          </span>
          <div class="item-main">
            <div class="item-title">${escapeHtml(endpoint.name || endpoint.id)}</div>
            <div class="item-meta">${escapeHtml(endpoint.provider)} · ${escapeHtml(endpoint.url)}</div>
          </div>
          <button data-test-endpoint="${escapeHtml(endpoint.id)}">Test</button>
          <button class="danger" data-delete-endpoint="${escapeHtml(endpoint.id)}">Remove</button>
        </div>`,
    )
    .join("");

  root.querySelectorAll("[data-test-endpoint]").forEach((button) => {
    button.addEventListener("click", async () => {
      setBusy(button, true, "Testing…");
      try {
        const result = await api(`/api/endpoints/${encodeURIComponent(button.dataset.testEndpoint)}/test`, {
          method: "POST",
        });
        showToast(
          result.ok
            ? `Connection healthy · ${(result.models || []).length} models found`
            : `Connection failed: ${result.error || "Unknown error"}`,
          !result.ok,
        );
        await refreshEndpoints();
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(button, false);
      }
    });
  });

  root.querySelectorAll("[data-delete-endpoint]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!window.confirm("Remove this endpoint and its linked models?")) return;
      setBusy(button, true, "Removing…");
      try {
        const result = await api(`/api/endpoints/${encodeURIComponent(button.dataset.deleteEndpoint)}`, {
          method: "DELETE",
        });
        showToast(`Endpoint removed · ${result.removedModels || 0} linked models removed`);
        await Promise.all([refreshEndpoints(), refreshModels()]);
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(button, false);
      }
    });
  });
}

function renderEndpointOptions() {
  $("model-endpoint").innerHTML = state.endpoints.length
    ? state.endpoints
        .map(
          (endpoint) =>
            `<option value="${escapeHtml(endpoint.id)}">${escapeHtml(endpoint.name || endpoint.id)}</option>`,
        )
        .join("")
    : '<option value="">Configure an endpoint first</option>';
}

function modelProviderLabel(model) {
  return model.provider || state.endpoints.find((endpoint) => endpoint.id === model.endpointId)?.provider || "unknown";
}

function renderModels() {
  const query = ($("model-search")?.value || "").toLowerCase();
  const provider = $("model-provider-filter")?.value || "";
  const items = state.models.filter(
    (model) =>
      (!query ||
        model.id.toLowerCase().includes(query) ||
        String(model.endpointName || "").toLowerCase().includes(query)) &&
      (!provider || modelProviderLabel(model) === provider),
  );
  const root = $("model-grid");

  if (!items.length) {
    root.innerHTML = '<div class="empty">No models match the current filters.</div>';
    return;
  }

  root.innerHTML = items
    .map(
      (model) => `
        <article class="model-card">
          <div class="section-title">
            <span class="pill ${model.endpointAvailable === false ? "bad" : "ok"}">${escapeHtml(modelProviderLabel(model))}</span>
            <button class="danger" data-delete-model="${escapeHtml(model.id)}">Remove</button>
          </div>
          <div class="model-id">${escapeHtml(model.id)}</div>
          <div class="muted">Endpoint: ${escapeHtml(model.endpointName || model.endpointId || "Unlinked")}</div>
          <div class="muted">Endpoint ID: ${escapeHtml(model.endpointId || "—")}</div>
        </article>`,
    )
    .join("");

  root.querySelectorAll("[data-delete-model]").forEach((button) => {
    button.addEventListener("click", async () => {
      const modelId = button.dataset.deleteModel;
      if (!window.confirm(`Remove ${modelId}?`)) return;
      setBusy(button, true, "Removing…");
      try {
        await api(`/api/models/${encodeURIComponent(modelId)}`, { method: "DELETE" });
        state.selectedModels.delete(modelId);
        await refreshModels();
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(button, false);
      }
    });
  });
}

function renderModelSelector() {
  const root = $("model-chips");
  root.innerHTML = state.models.length
    ? state.models
        .map(
          (model) => `
            <button type="button" class="chip ${state.selectedModels.has(model.id) ? "selected" : ""}"
              aria-pressed="${state.selectedModels.has(model.id)}" data-model="${escapeHtml(model.id)}">
              ${escapeHtml(model.id)}
            </button>`,
        )
        .join("")
    : '<div class="empty">Register or discover models first.</div>';

  root.querySelectorAll("[data-model]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.model;
      if (state.selectedModels.has(id)) state.selectedModels.delete(id);
      else state.selectedModels.add(id);
      renderModelSelector();
      $("selection-count").textContent = `${state.selectedModels.size} selected`;
      updateRunSummary();
    });
  });
}

function renderPackages() {
  $("prompt-package").innerHTML =
    '<option value="">Custom prompt set</option>' +
    state.packages
      .map(
        (item) =>
          `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} · ${(item.prompts || []).length}</option>`,
      )
      .join("");
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
    .map(
      (prompt, index) => `
        <div class="prompt-row">
          <span class="pill">${index + 1}</span>
          <textarea data-prompt="${index}" aria-label="Prompt ${index + 1}">${escapeHtml(prompt)}</textarea>
          <button class="danger" type="button" data-remove-prompt="${index}">Remove</button>
        </div>`,
    )
    .join("");

  root.querySelectorAll("[data-prompt]").forEach((textarea) => {
    textarea.addEventListener("input", () => {
      state.prompts[Number(textarea.dataset.prompt)] = textarea.value;
      updateRunSummary();
    });
  });
  root.querySelectorAll("[data-remove-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      state.prompts.splice(Number(button.dataset.removePrompt), 1);
      $("prompt-count").max = Math.max(1, state.prompts.length);
      $("prompt-count").value = Math.min(Number($("prompt-count").value), Math.max(1, state.prompts.length));
      renderPrompts();
      updateRunSummary();
    });
  });
}

function updateRunSummary() {
  const count = Math.min(Number($("prompt-count").value || state.prompts.length), state.prompts.length);
  $("prompt-count-label").textContent = count;
  $("summary-models").textContent = state.selectedModels.size;
  $("summary-prompts").textContent = count;
  $("summary-requests").textContent = state.selectedModels.size * count;
  $("summary-mode").textContent = $("execution-mode").value;
}

function updateJob(job) {
  if (!job) return;
  state.job = { ...(state.job || {}), ...job };
  const status = state.job.status || "queued";
  const total = Number(state.job.total_reports || 0);
  const completed = Number(state.job.completed_reports || 0);
  const failed = Number(state.job.failed_reports || 0);
  const computed = total ? Math.round(((completed + failed) / total) * 100) : 0;
  const percentage = Math.min(100, Number(state.job.overall_percentage ?? computed));

  $("job-progress-bar").dataset.value = percentage;
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

  const rows = Object.entries(state.job.models_state || {})
    .map(
      ([id, item]) => `
        <div class="item">
          <span class="pill ${item.status === "completed" ? "ok" : item.status === "failed" ? "bad" : "warn"}">
            ${escapeHtml(item.status || "queued")}
          </span>
          <div class="item-main">
            <div class="item-title">${escapeHtml(id)}</div>
            <div class="item-meta">${escapeHtml(item.current_step || "")}</div>
          </div>
          <span class="muted">${Number(item.percentage || 0)}%</span>
        </div>`,
    )
    .join("");
  $("job-models").innerHTML = rows || '<div class="muted">Waiting for per-model events…</div>';

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

function renderCharts() {
  const root = $("chart-runs");
  if (!state.runs.length) {
    root.innerHTML = '<div class="empty">No chart runs yet.</div>';
    return;
  }
  root.innerHTML = state.runs
    .map(
      (run) => `
        <section class="card">
          <div class="section-title">
            <div>
              <h3>${escapeHtml(run.runName || run.runId)}</h3>
              <div class="sub">${escapeHtml((run.models || []).join(", "))} · ${escapeHtml(run.finishedAt || run.timestamp || "")}</div>
            </div>
            <button data-run-detail="${escapeHtml(run.runId)}">Inspect run</button>
          </div>
          <div class="chart-grid">
            ${(run.charts || [])
              .map(
                (chart) => `
                  <article class="chart-card">
                    <img loading="lazy" src="${escapeHtml(chart.url)}" alt="${escapeHtml(chart.displayName || chart.name)}">
                    <h4>${escapeHtml(chart.displayName || chart.name)}</h4>
                    <div class="muted">${escapeHtml(chart.category || state.chartsMeta[chart.name]?.category || "Analysis")}</div>
                    <button data-chart-detail="${escapeHtml(run.runId)}::${escapeHtml(chart.name)}">Metadata</button>
                  </article>`,
              )
              .join("") || '<div class="empty">No chart artifacts recorded.</div>'}
          </div>
        </section>`,
    )
    .join("");

  root.querySelectorAll("[data-run-detail]").forEach((button) => {
    button.addEventListener("click", () => openRun(button.dataset.runDetail));
  });
  root.querySelectorAll("[data-chart-detail]").forEach((button) => {
    button.addEventListener("click", () => {
      const [runId, name] = button.dataset.chartDetail.split("::");
      const run = state.runs.find((item) => item.runId === runId);
      openDrawer(name, { ...state.chartsMeta[name], runId, models: run?.models, prompts: run?.prompts });
    });
  });
}

function renderReports() {
  const root = $("report-grid");
  if (!state.reports.length) {
    root.innerHTML = '<div class="empty">No PDF reports generated.</div>';
    return;
  }
  root.innerHTML = state.reports
    .map(
      (report) => `
        <article class="report-card">
          <div class="section-title">
            <span class="pill ${report.status === "completed" ? "ok" : report.status ? "warn" : "ok"}">PDF</span>
            <span class="muted">${report.sizeBytes ? `${Math.ceil(report.sizeBytes / 1024)} KB` : ""}</span>
          </div>
          <h4>${escapeHtml(report.name)}</h4>
          <div class="muted">${escapeHtml(report.runId || report.modified || "Legacy artifact")}</div>
          <div class="muted">${escapeHtml((report.models || []).join(", "))}</div>
          <div class="muted">SHA-256: ${escapeHtml((report.sha256 || "").slice(0, 16))}${report.sha256 ? "…" : ""}</div>
          <div class="actions">
            <a class="btn primary" target="_blank" rel="noopener" href="${escapeHtml(report.url)}">Open report</a>
            ${report.runId ? `<a class="btn" href="/api/telemetry/runs/${encodeURIComponent(report.runId)}/zip">Export run</a>` : ""}
            <button class="danger" data-delete-report="${escapeHtml(report.name)}">Delete</button>
          </div>
        </article>`,
    )
    .join("");

  root.querySelectorAll("[data-delete-report]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!window.confirm(`Delete ${button.dataset.deleteReport}?`)) return;
      setBusy(button, true, "Deleting…");
      try {
        await api(`/api/reports/${encodeURIComponent(button.dataset.deleteReport)}`, { method: "DELETE" });
        await refreshReports();
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(button, false);
      }
    });
  });
}

async function openRun(runId) {
  try {
    const payload = await api(`/api/telemetry/runs/${encodeURIComponent(runId)}`);
    openDrawer(`Run ${runId}`, payload.run || payload);
  } catch (error) {
    showToast(error.message, true);
  }
}

function openDrawer(title, data) {
  $("drawer-title").textContent = title;
  $("drawer-json").textContent = JSON.stringify(data, null, 2);
  $("drawer").classList.add("open");
}

async function initializeData() {
  await Promise.all([
    refreshEndpoints(),
    refreshModels(),
    refreshPackages(),
    refreshReports(),
    refreshCharts(),
  ]);
  const jobId = localStorage.getItem("we3.job");
  if (jobId) {
    try {
      const payload = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      updateJob(payload.job);
      if (terminalStates.has(payload.job.status)) localStorage.removeItem("we3.job");
    } catch (error) {
      localStorage.removeItem("we3.job");
    }
  }
}

function init() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => setTab(button.dataset.tab));
  });
  $("drawer-close").addEventListener("click", () => $("drawer").classList.remove("open"));

  $("endpoint-provider").addEventListener("change", () => {
    const provider = $("endpoint-provider").value;
    if (provider.endsWith("_cli")) {
      $("endpoint-url").value = `cli://${provider.replace("_cli", "")}`;
      $("endpoint-key").value = "";
      $("endpoint-key").disabled = true;
    } else {
      $("endpoint-key").disabled = false;
    }
  });

  $("endpoint-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = event.submitter;
    setBusy(submit, true, "Saving…");
    try {
      await api("/api/endpoints", {
        method: "POST",
        body: JSON.stringify({
          name: $("endpoint-name").value,
          url: $("endpoint-url").value,
          provider: $("endpoint-provider").value,
          apiKey: $("endpoint-key").value || null,
        }),
      });
      event.currentTarget.reset();
      $("endpoint-key").disabled = false;
      showToast("Endpoint saved securely");
      await Promise.all([refreshEndpoints(), refreshModels()]);
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(submit, false);
    }
  });

  $("detect-endpoints").addEventListener("click", async (event) => {
    setBusy(event.currentTarget, true, "Detecting…");
    try {
      const result = await api("/api/endpoints/auto-detect", { method: "POST" });
      showToast(`Endpoint detection complete · ${(result.endpoints || result.all_endpoints || []).length} available`);
      await refreshEndpoints();
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
      await refreshEndpoints();
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
      await api("/api/models", {
        method: "POST",
        body: JSON.stringify({
          id: $("model-id").value.trim(),
          endpointId: $("model-endpoint").value,
        }),
      });
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
      showToast(`Model inventory refreshed · ${(result.added || []).length} added`);
      await refreshModels();
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(event.currentTarget, false);
    }
  });

  $("model-search").addEventListener("input", renderModels);
  $("model-provider-filter").addEventListener("change", renderModels);
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
    state.models.forEach((model) => state.selectedModels.add(model.id));
    renderModelSelector();
    $("selection-count").textContent = `${state.selectedModels.size} selected`;
    updateRunSummary();
  });
  $("select-none").addEventListener("click", () => {
    state.selectedModels.clear();
    renderModelSelector();
    $("selection-count").textContent = "0 selected";
    updateRunSummary();
  });

  $("generate-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const count = Math.min(Number($("prompt-count").value), state.prompts.length);
    const prompts = state.prompts.slice(0, count).map((item) => item.trim()).filter(Boolean);
    if (!state.selectedModels.size) return showToast("Select at least one model", true);
    if (!prompts.length) return showToast("Add at least one prompt", true);

    const submit = event.submitter;
    setBusy(submit, true, "Queuing…");
    try {
      const payload = await api("/api/jobs", {
        method: "POST",
        body: JSON.stringify({
          models: [...state.selectedModels],
          prompts,
          promptPackage: $("prompt-package").value,
          promptCount: prompts.length,
          executionMode: $("execution-mode").value,
          batchSize: 1,
          timeoutSeconds: 600,
          failurePolicy: "continue",
          autoCharts: true,
        }),
      });
      localStorage.setItem("we3.job", payload.job.job_id);
      updateJob(payload.job);
      send("subscribe_job", { job_id: payload.job.job_id });
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(submit, false);
    }
  });

  $("cancel-job").addEventListener("click", async (event) => {
    const jobId = state.job?.job_id || localStorage.getItem("we3.job");
    if (!jobId || event.currentTarget.dataset.action === "done") return;
    setBusy(event.currentTarget, true, event.currentTarget.dataset.action === "retry" ? "Retrying…" : "Cancelling…");
    try {
      if (event.currentTarget.dataset.action === "retry") {
        const payload = await api(`/api/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" });
        localStorage.setItem("we3.job", payload.job.job_id);
        updateJob(payload.job);
        send("subscribe_job", { job_id: payload.job.job_id });
      } else {
        const payload = await api(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
        updateJob(payload.job);
      }
    } catch (error) {
      showToast(error.message, true);
    } finally {
      event.currentTarget.disabled = false;
    }
  });

  $("refresh-charts").addEventListener("click", refreshCharts);
  $("generate-charts").addEventListener("click", async (event) => {
    const runId = state.job?.invocations?.find((item) => item.run_id)?.run_id || state.job?.run_id;
    if (!runId) return showToast("Select or complete a run before generating charts", true);
    setBusy(event.currentTarget, true, "Generating…");
    try {
      const result = await api("/api/charts/generate", {
        method: "POST",
        body: JSON.stringify({ runId }),
      });
      showToast(`Generated ${result.generated || 0} charts`);
      await refreshCharts();
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(event.currentTarget, false);
    }
  });
  $("refresh-reports").addEventListener("click", refreshReports);

  setTab(localStorage.getItem("we3.tab") || "endpoints");
  renderPrompts();
  updateRunSummary();
  connect();
  initializeData();
}

document.addEventListener("DOMContentLoaded", init);
