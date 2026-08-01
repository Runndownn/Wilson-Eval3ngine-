(() => {
  "use strict";

  const AUTO_OPEN_REPORTS = 4;
  let familyDialog = null;
  let familyDialogRestoreFocus = null;

  const byId = (id) => document.getElementById(id);

  function familySummary(models) {
    const providers = [...new Set(models.map((model) => modelProvider(model)))].sort();
    const endpoints = [...new Set(models.map((model) => model.endpointName || model.endpointId || "Unlinked"))].sort();
    const ready = models.filter((model) => model.endpointAvailable !== false).length;
    return { providers, endpoints, ready };
  }

  function rankedModels(models, limit = 4) {
    return [...models]
      .sort((a, b) => popularScore(b) - popularScore(a) || String(a.id).localeCompare(String(b.id)))
      .slice(0, limit);
  }

  function ensureFamilyDialog() {
    if (familyDialog) return familyDialog;
    familyDialog = document.createElement("dialog");
    familyDialog.id = "model-family-dialog";
    familyDialog.className = "model-family-dialog";
    familyDialog.setAttribute("aria-labelledby", "model-family-dialog-title");
    familyDialog.innerHTML = `
      <div class="family-dialog-shell">
        <header class="family-dialog-header">
          <div><span class="step-badge">Model family</span><h2 id="model-family-dialog-title">Models</h2><p id="model-family-dialog-summary"></p></div>
          <button type="button" class="family-dialog-close" aria-label="Close model family">Close</button>
        </header>
        <div id="model-family-dialog-popular" class="family-dialog-popular"></div>
        <div id="model-family-dialog-list" class="family-dialog-list"></div>
      </div>`;
    document.body.append(familyDialog);
    familyDialog.querySelector(".family-dialog-close").addEventListener("click", closeFamilyDialog);
    familyDialog.addEventListener("click", (event) => {
      if (event.target === familyDialog) closeFamilyDialog();
    });
    familyDialog.addEventListener("close", () => {
      familyDialogRestoreFocus?.focus();
      familyDialogRestoreFocus = null;
    });
    return familyDialog;
  }

  function closeFamilyDialog() {
    if (familyDialog?.open) familyDialog.close();
  }

  function modelDetailRow(model) {
    const endpoint = model.endpointName || model.endpointId || "Unlinked";
    const available = model.endpointAvailable !== false;
    return `<article class="family-model-row">
      <div class="family-model-main">
        <div class="family-model-heading"><strong>${escapeHtml(model.id)}</strong><span class="pill ${available ? "ok" : "bad"}">${available ? "ready" : "offline"}</span></div>
        <p>${escapeHtml(modelRole(model))}</p>
        <div class="family-model-meta"><span>${escapeHtml(modelProvider(model))}</span><span>${escapeHtml(endpoint)}</span></div>
      </div>
      <div class="family-model-actions">
        <button type="button" data-family-select="${escapeAttr(model.id)}">${state.selectedModels.has(model.id) ? "Selected" : "Select"}</button>
        <button type="button" class="danger" data-family-delete="${escapeAttr(model.id)}">Remove</button>
      </div>
    </article>`;
  }

  function wireFamilyDialogActions(dialog) {
    dialog.querySelectorAll("[data-family-select]").forEach((button) => {
      button.addEventListener("click", () => {
        const id = button.dataset.familySelect;
        if (state.selectedModels.has(id)) state.selectedModels.delete(id);
        else state.selectedModels.add(id);
        renderModelSelector();
        updateRunSummary();
        button.textContent = state.selectedModels.has(id) ? "Selected" : "Select";
      });
    });
    dialog.querySelectorAll("[data-family-delete]").forEach((button) => {
      button.addEventListener("click", async () => {
        const id = button.dataset.familyDelete;
        setBusy(button, true, "Removing…");
        try {
          await api(`/api/models/${encodeURIComponent(id)}`, { method: "DELETE" });
          state.selectedModels.delete(id);
          await refreshModels();
          closeFamilyDialog();
          showToast(`${id} removed`);
        } catch (error) {
          showToast(error.message, true);
          setBusy(button, false);
        }
      });
    });
  }

  function openFamilyDialog(family, models, trigger) {
    const dialog = ensureFamilyDialog();
    const summary = familySummary(models);
    familyDialogRestoreFocus = trigger;
    dialog.querySelector("#model-family-dialog-title").textContent = family;
    dialog.querySelector("#model-family-dialog-summary").textContent = `${models.length} registered model${models.length === 1 ? "" : "s"} across ${summary.providers.length} provider${summary.providers.length === 1 ? "" : "s"} and ${summary.endpoints.length} endpoint${summary.endpoints.length === 1 ? "" : "s"}. ${summary.ready} currently report ready.`;
    dialog.querySelector("#model-family-dialog-popular").innerHTML = `<div><span class="step-badge">Popular in this family</span><p>${rankedModels(models).map((model) => escapeHtml(model.id)).join(" · ")}</p></div>`;
    dialog.querySelector("#model-family-dialog-list").innerHTML = models.map(modelDetailRow).join("");
    wireFamilyDialogActions(dialog);
    dialog.showModal();
  }

  function familyCard(family, models) {
    const summary = familySummary(models);
    const popular = rankedModels(models, 3);
    return `<article class="model-family-card" data-family-tone="${typeof familyColorIndex === "function" ? familyColorIndex(family) : 0}">
      <div class="family-card-top"><span class="pill">${escapeHtml(family)}</span><span class="pill ${summary.ready === models.length ? "ok" : "warn"}">${summary.ready}/${models.length} ready</span></div>
      <h3>${escapeHtml(family)} family</h3>
      <p>${escapeHtml(modelRole(popular[0] || models[0]))}</p>
      <dl><dt>Models</dt><dd>${models.length}</dd><dt>Providers</dt><dd>${escapeHtml(summary.providers.join(", "))}</dd><dt>Endpoints</dt><dd>${escapeHtml(summary.endpoints.slice(0, 2).join(", "))}${summary.endpoints.length > 2 ? ` +${summary.endpoints.length - 2}` : ""}</dd></dl>
      <div class="family-card-popular"><strong>Popular</strong>${popular.map((model) => `<span>${escapeHtml(model.id)}</span>`).join("")}</div>
      <button type="button" class="primary family-card-open" data-open-family="${escapeAttr(family)}">Explore ${models.length} model${models.length === 1 ? "" : "s"}</button>
    </article>`;
  }

  function renderFamilyInventory() {
    const items = filteredModels("model-search", "model-provider-filter");
    byId("model-result-count").textContent = `${items.length} model${items.length === 1 ? "" : "s"}`;
    const root = byId("model-grid");
    if (!root) return;
    if (!items.length) {
      root.innerHTML = '<div class="empty">No models match the current filters.</div>';
      return;
    }
    const groups = new Map();
    items.forEach((model) => {
      const family = modelFamily(model);
      if (!groups.has(family)) groups.set(family, []);
      groups.get(family).push(model);
    });
    root.innerHTML = [...groups.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([family, models]) => familyCard(family, models))
      .join("");
    root.querySelectorAll("[data-open-family]").forEach((button) => {
      button.addEventListener("click", () => openFamilyDialog(button.dataset.openFamily, groups.get(button.dataset.openFamily), button));
    });
  }

  function installFamilyInventory() {
    if (typeof renderModels !== "function") return;
    renderModels = renderFamilyInventory;
    ["model-search", "model-provider-filter"].forEach((id) => {
      const control = byId(id);
      control?.addEventListener("input", renderFamilyInventory);
      control?.addEventListener("change", renderFamilyInventory);
    });
    renderFamilyInventory();
  }

  function openInitialReportViewers() {
    const root = byId("report-grid");
    if (!root || root.dataset.autoViewersApplied === "true") return;
    const cards = [...root.querySelectorAll(".report-card")];
    if (!cards.length) return;
    cards.forEach((card, index) => {
      const viewer = card.querySelector(".report-viewer");
      const iframe = viewer?.querySelector("iframe");
      const toggle = card.querySelector("[data-toggle-report]");
      if (!viewer || !iframe || !toggle) return;
      const opening = index < AUTO_OPEN_REPORTS;
      viewer.hidden = !opening;
      if (opening && !iframe.src) iframe.src = iframe.dataset.src;
      toggle.textContent = opening ? "Hide card viewer" : "View report in card";
      card.classList.toggle("report-default-open", opening);
    });
    root.dataset.autoViewersApplied = "true";
  }

  function installDefaultReportViewers() {
    const root = byId("report-grid");
    if (!root) return;
    new MutationObserver(() => {
      root.dataset.autoViewersApplied = "false";
      window.requestAnimationFrame(openInitialReportViewers);
    }).observe(root, { childList: true });
    openInitialReportViewers();
  }

  const chartWhy = [
    [/radar/i, "Why it matters: the shared radial scale makes trade-offs visible at a glance, but the underlying metadata should still be used for precise comparisons."],
    [/response time|latency|timeline|histogram|box plot/i, "Why it matters: latency shape and variance expose operational risk that a single average can hide, including slow tails and unstable providers."],
    [/token/i, "Why it matters: token volume connects model behavior to cost, verbosity, and throughput, helping operators balance depth against efficiency."],
    [/confidence|wilson/i, "Why it matters: confidence intervals prevent small samples from appearing more certain than the evidence supports."],
    [/correlation|scatter/i, "Why it matters: relationships between metrics can reveal trade-offs and outliers, but correlation alone should not be treated as causation."],
    [/outcome|success|pass|fail/i, "Why it matters: outcome composition shows how a model succeeds or fails instead of reducing evaluation quality to one headline score."],
    [/security|code/i, "Why it matters: capability without safety context can create operational risk, so code generation and security awareness are reviewed together."],
    [/sophistication|heatmap/i, "Why it matters: the matrix communicates implementation breadth and progression while making missing dimensions immediately visible."],
  ];

  function enrichChartExplanations() {
    document.querySelectorAll(".chart-card").forEach((card) => {
      if (card.querySelector(".chart-why")) return;
      const title = card.querySelector("h4")?.textContent || "";
      const description = card.querySelector(".chart-card-description");
      const why = chartWhy.find(([pattern]) => pattern.test(title))?.[1] || "Why it matters: this visual translates run evidence into an interpretable comparison while preserving the source run and metadata for verification.";
      const paragraph = document.createElement("p");
      paragraph.className = "chart-why";
      paragraph.textContent = why;
      description?.insertAdjacentElement("afterend", paragraph);
    });
  }

  function installChartExplanations() {
    const root = byId("chart-runs");
    if (!root) return;
    new MutationObserver(enrichChartExplanations).observe(root, { childList: true, subtree: true });
    enrichChartExplanations();
  }

  function stabilizeGenerateLayout() {
    const layout = document.querySelector(".generate-layout");
    const summary = document.querySelector(".run-summary-card");
    if (!layout || !summary) return;
    layout.prepend(summary);
    summary.classList.add("run-summary-topbar", "run-summary-full-row");
  }

  function initializeUx5() {
    installFamilyInventory();
    stabilizeGenerateLayout();
    installDefaultReportViewers();
    installChartExplanations();
  }

  document.addEventListener("DOMContentLoaded", () => window.setTimeout(initializeUx5, 20));
})();
