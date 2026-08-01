(() => {
  "use strict";

  const PAGE_SIZE = 8;
  const HEALTH_INTERVAL_MS = 5000;
  const REQUEST_TIMEOUT_MS = 15000;
  let modelPage = 1;
  let lastSocketOpenAt = 0;
  let activeChart = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function endpointCard(endpointId) {
    return document.querySelector(`[data-test-endpoint="${CSS.escape(endpointId)}"]`)?.closest(".endpoint-card");
  }

  function ensureFeedback(card) {
    if (!card) return null;
    let node = card.querySelector(".endpoint-feedback");
    if (!node) {
      node = document.createElement("div");
      node.className = "endpoint-feedback";
      node.setAttribute("role", "status");
      node.setAttribute("aria-live", "polite");
      card.append(node);
    }
    return node;
  }

  function setEndpointFeedback(endpointId, stateName, title, detail) {
    const node = ensureFeedback(endpointCard(endpointId));
    if (!node) return;
    node.className = `endpoint-feedback ${stateName}`;
    node.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail || "")}</span>`;
  }

  async function timedApi(path, options = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(path, {
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...(options.headers || {}),
        },
        ...options,
        signal: controller.signal,
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
    } catch (error) {
      if (error.name === "AbortError") {
        const timeout = new Error(`No response within ${Math.round(timeoutMs / 1000)} seconds`);
        timeout.code = "timeout";
        throw timeout;
      }
      throw error;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function assessConnectionError(error) {
    const message = String(error?.message || "Connection test failed");
    const lowered = message.toLowerCase();
    if (error?.status === 401 || error?.status === 403 || /unauthorized|forbidden|api key|credential/.test(lowered)) {
      return { title: "Authentication rejected", detail: "The provider was reached, but the stored credential was not accepted." };
    }
    if (error?.status === 404 || /not found|unknown model/.test(lowered)) {
      return { title: "Provider route not found", detail: "Check the base URL and provider adapter. The configured API path was not available." };
    }
    if (error?.status === 429 || /rate limit|too many requests/.test(lowered)) {
      return { title: "Provider rate limited the test", detail: "The endpoint is reachable. Retry after the provider limit resets." };
    }
    if (error?.status >= 500) {
      return { title: "Provider service error", detail: `The provider returned ${error.status}. The endpoint was reached but could not complete the test.` };
    }
    if (error?.code === "timeout" || /timed out|timeout|no response/.test(lowered)) {
      return { title: "Connection timed out", detail: "No provider response arrived before the safety timeout. Check network reachability and provider load." };
    }
    if (/certificate|tls|ssl/.test(lowered)) {
      return { title: "TLS validation failed", detail: "The provider certificate or secure transport configuration could not be validated." };
    }
    if (/resolve|dns|name or service|host/.test(lowered)) {
      return { title: "Hostname could not be resolved", detail: "Check the endpoint hostname and DNS/network configuration." };
    }
    if (/connect|refused|network|unreachable/.test(lowered)) {
      return { title: "Provider is unreachable", detail: "The connection could not be established. Check the URL, firewall, local-provider setting, and service state." };
    }
    return { title: "Connection test failed", detail: message };
  }

  async function testEndpoint(endpointId, { reconcile = true, button = null } = {}) {
    setEndpointFeedback(endpointId, "testing", "Testing connection…", "Contacting the provider with a bounded request timeout.");
    setBusy(button, true, "Testing…");
    try {
      const result = await timedApi(`/api/endpoints/${encodeURIComponent(endpointId)}/test`, { method: "POST" });
      if (!result.ok) throw new Error(result.error || "The endpoint adapter reported an unsuccessful test");

      let added = 0;
      if (reconcile) {
        setEndpointFeedback(endpointId, "testing", "Connection successful", "Reconciling the provider model inventory…");
        const discovered = await timedApi("/api/models/auto-detect", { method: "POST" }, 30000);
        added = (discovered.added || []).filter((item) => item.endpointId === endpointId).length;
      }

      await Promise.all([refreshEndpoints(), refreshModels()]);
      const found = Array.isArray(result.models) ? result.models.length : endpointModelCount(endpointId);
      setEndpointFeedback(
        endpointId,
        "success",
        "Connection successful",
        `${found} model${found === 1 ? "" : "s"} reported · ${added} newly registered`,
      );
      showToast(`Connection successful · ${found} model${found === 1 ? "" : "s"} found`);
      return { ok: true, found, added };
    } catch (error) {
      const assessment = assessConnectionError(error);
      setEndpointFeedback(endpointId, "error", assessment.title, assessment.detail);
      showToast(`${assessment.title}: ${assessment.detail}`, true);
      return { ok: false, assessment };
    } finally {
      setBusy(button, false);
    }
  }

  async function checkAllHealth(button) {
    setBusy(button, true, "Checking endpoints…");
    const endpoints = [...state.endpoints];
    if (!endpoints.length) {
      showToast("No endpoints are configured", true);
      setBusy(button, false);
      return;
    }

    const results = [];
    for (let index = 0; index < endpoints.length; index += 3) {
      const batch = endpoints.slice(index, index + 3);
      const batchResults = await Promise.all(batch.map((endpoint) => testEndpoint(endpoint.id, { reconcile: false })));
      results.push(...batchResults);
    }
    await refreshEndpoints();
    const healthy = results.filter((result) => result.ok).length;
    const failed = results.length - healthy;
    showToast(`Health assessment complete · ${healthy} healthy · ${failed} need attention`, failed > 0);
    setBusy(button, false);
  }

  function installEndpointActionInterceptors() {
    document.addEventListener(
      "click",
      (event) => {
        const testButton = event.target.closest("[data-test-endpoint]");
        if (testButton) {
          event.preventDefault();
          event.stopImmediatePropagation();
          testEndpoint(testButton.dataset.testEndpoint, { reconcile: true, button: testButton });
          return;
        }
        const allButton = event.target.closest("#refresh-endpoints");
        if (allButton) {
          event.preventDefault();
          event.stopImmediatePropagation();
          checkAllHealth(allButton);
        }
      },
      true,
    );
  }

  async function pollApplicationHealth() {
    const dot = byId("health-dot");
    const text = byId("health-text");
    if (!dot || !text) return;
    try {
      await timedApi("/api/health", {}, 4000);
      const socketOpen = state.ws?.readyState === WebSocket.OPEN;
      if (socketOpen) lastSocketOpenAt = Date.now();
      dot.classList.add("online");
      dot.classList.toggle("degraded", !socketOpen);
      text.textContent = socketOpen ? "Connected" : "Connected · polling";
      text.title = socketOpen
        ? "API and live WebSocket updates are connected"
        : "The API is healthy; live WebSocket updates are reconnecting and REST polling remains available";
    } catch {
      dot.classList.remove("online", "degraded");
      text.textContent = "Disconnected";
      text.title = "The GUI health endpoint did not respond";
    }
  }

  function installHealthMonitor() {
    const originalSetConnectionState = setConnectionState;
    setConnectionState = function resilientConnectionState(connected, text) {
      if (connected) lastSocketOpenAt = Date.now();
      originalSetConnectionState(connected, connected ? "Connected" : text);
    };
    pollApplicationHealth();
    window.setInterval(pollApplicationHealth, HEALTH_INTERVAL_MS);
  }

  function ensureModelPager() {
    const grid = byId("model-grid");
    if (!grid) return null;
    let pager = byId("model-pager");
    if (!pager) {
      pager = document.createElement("nav");
      pager.id = "model-pager";
      pager.className = "model-pager";
      pager.setAttribute("aria-label", "Model inventory pages");
      grid.insertAdjacentElement("afterend", pager);
    }
    return pager;
  }

  function paginateModels({ reset = false } = {}) {
    const grid = byId("model-grid");
    const pager = ensureModelPager();
    if (!grid || !pager) return;
    const cards = [...grid.querySelectorAll(":scope > .model-card")];
    if (reset) modelPage = 1;
    const pages = Math.max(1, Math.ceil(cards.length / PAGE_SIZE));
    modelPage = Math.min(modelPage, pages);
    cards.forEach((card, index) => {
      card.hidden = Math.floor(index / PAGE_SIZE) + 1 !== modelPage;
      colorizeModelCard(card);
    });
    pager.hidden = cards.length <= PAGE_SIZE;
    pager.innerHTML = `<button type="button" data-model-page="prev" ${modelPage === 1 ? "disabled" : ""}>Previous</button><span>Page <strong>${modelPage}</strong> of ${pages} · ${cards.length} models · ${PAGE_SIZE} per page</span><button type="button" data-model-page="next" ${modelPage === pages ? "disabled" : ""}>Next</button>`;
  }

  function familyColorIndex(label) {
    return [...String(label || "Other")].reduce((total, character) => total + character.charCodeAt(0), 0) % 8;
  }

  function colorizeModelCard(card) {
    const family = card.querySelector(".model-card-pills .pill")?.textContent?.trim() || "Other";
    card.dataset.familyTone = String(familyColorIndex(family));
  }

  function colorizeSelectors() {
    document.querySelectorAll(".model-choice").forEach((choice) => {
      const family = choice.querySelector(".model-choice-meta")?.textContent?.split("·")[0]?.trim() || "Other";
      choice.dataset.familyTone = String(familyColorIndex(family));
    });
  }

  function installModelContainment() {
    const grid = byId("model-grid");
    if (!grid) return;
    const observer = new MutationObserver(() => {
      paginateModels();
      colorizeSelectors();
    });
    observer.observe(grid, { childList: true });
    ["model-search", "model-provider-filter"].forEach((id) => byId(id)?.addEventListener("input", () => paginateModels({ reset: true })));
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-model-page]");
      if (!button) return;
      const cards = [...grid.querySelectorAll(":scope > .model-card")];
      const pages = Math.max(1, Math.ceil(cards.length / PAGE_SIZE));
      modelPage += button.dataset.modelPage === "next" ? 1 : -1;
      modelPage = Math.max(1, Math.min(modelPage, pages));
      paginateModels();
      grid.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    paginateModels();

    const selectorObserver = new MutationObserver(colorizeSelectors);
    [byId("popular-models"), byId("model-families")].filter(Boolean).forEach((node) => selectorObserver.observe(node, { childList: true, subtree: true }));
    colorizeSelectors();
  }

  function promoteRunSummary() {
    const layout = document.querySelector(".generate-layout");
    const summary = document.querySelector(".run-summary-card");
    if (!layout || !summary) return;
    layout.prepend(summary);
    summary.classList.add("run-summary-topbar");
  }

  function installChartWindowDeletion() {
    const actions = document.querySelector("#chart-window .window-actions");
    if (!actions || byId("chart-window-delete")) return;
    const button = document.createElement("button");
    button.id = "chart-window-delete";
    button.type = "button";
    button.className = "danger";
    button.textContent = "Delete chart";
    actions.prepend(button);

    const originalOpenChart = openChart;
    openChart = function trackedOpenChart(runId, name) {
      activeChart = { runId, name };
      originalOpenChart(runId, name);
    };
    const originalCloseChart = closeChart;
    closeChart = function trackedCloseChart() {
      activeChart = null;
      originalCloseChart();
    };

    button.addEventListener("click", async () => {
      if (!activeChart) return;
      setBusy(button, true, "Deleting…");
      try {
        await timedApi(
          `/api/charts/runs/${encodeURIComponent(activeChart.runId)}/${encodeURIComponent(activeChart.name)}`,
          { method: "DELETE" },
        );
        const deletedName = activeChart.name;
        closeChart();
        await refreshCharts();
        showToast(`${deletedName} deleted. Refresh will not restore it.`);
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(button, false);
      }
    });
  }

  function installDemoFeedback() {
    document.addEventListener(
      "click",
      async (event) => {
        const button = event.target.closest("#generate-demo-charts");
        if (!button) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        setBusy(button, true, "Generating full demo…");
        const guidance = byId("chart-guidance");
        if (guidance) guidance.textContent = "Generating the complete synthetic chart catalogue. This may take a moment because each chart is rendered as a real PNG.";
        try {
          const result = await timedApi("/api/charts/demo", { method: "POST" }, 120000);
          await refreshCharts();
          const expected = Object.keys(state.chartMetadata || {}).length;
          const generated = Number(result.generated || 0);
          if (guidance) guidance.textContent = `Demo catalogue ready · ${generated}${expected ? ` of ${expected}` : ""} chart types rendered. Demo data is synthetic and labelled.`;
          showToast(`Generated ${generated} fully rendered demonstration charts`);
        } catch (error) {
          const assessment = assessConnectionError(error);
          if (guidance) guidance.textContent = `${assessment.title}: ${assessment.detail}`;
          showToast(`${assessment.title}: ${assessment.detail}`, true);
        } finally {
          setBusy(button, false);
        }
      },
      true,
    );
  }

  function strengthenReportViewers() {
    const root = byId("report-grid");
    if (!root) return;
    const decorate = () => {
      root.querySelectorAll(".report-viewer").forEach((viewer) => {
        if (viewer.querySelector(".pdf-reader-toolbar")) return;
        const toolbar = document.createElement("div");
        toolbar.className = "pdf-reader-toolbar";
        toolbar.innerHTML = '<span class="pdf-icon" aria-hidden="true">PDF</span><strong>Document preview</strong><span>Use Open full report for browser-native zoom, search, print, and download.</span>';
        viewer.prepend(toolbar);
        viewer.classList.add("pdf-document-frame");
      });
    };
    new MutationObserver(decorate).observe(root, { childList: true, subtree: true });
    decorate();
  }

  function initializeUx4() {
    installEndpointActionInterceptors();
    installHealthMonitor();
    installModelContainment();
    promoteRunSummary();
    installChartWindowDeletion();
    installDemoFeedback();
    strengthenReportViewers();
  }

  document.addEventListener("DOMContentLoaded", () => window.setTimeout(initializeUx4, 0));
})();
