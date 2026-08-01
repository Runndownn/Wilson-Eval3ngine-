/* Wilson Eval3ngine GUI - TypeScript source */

interface Endpoint {
  id: string;
  name: string;
  url: string;
  apiKey?: string;
  provider: "ollama" | "openai" | "kilo" | "claude_cli" | "kilo_cli" | "codex_cli";
}

interface Model {
  id: string;
  endpointId: string;
  provider: Endpoint["provider"];
}

interface ReportItem {
  name: string;
  url: string;
  sizeBytes?: number;
}

interface ChatMessage {
  action: string;
  [key: string]: unknown;
}

interface RunChartInfo {
  runId: string;
  runName: string;
  timestamp: string;
  models: string[];
  prompts: string[];
  type: string;
  returncode: number;
  duration: string;
  charts: Array<{
    name: string;
    displayName: string;
    category: string;
    url: string;
    sizeBytes: number;
  }>;
}

interface ChartMetadata {
  name: string;
  displayName: string;
  category: string;
  description: string;
}

declare global {
  interface Window { __CHART_METADATA: ChartMetadata[]; }
}

const endpoints: Endpoint[] = [];
const models: Model[] = [];
let selectedModelIds = new Set<string>();
let currentPdfPage = 1;
let currentPdfFile = "";
let pdfDoc: any = null;
let ws: WebSocket | null = null;

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  const statusEl = document.getElementById("connection-status") as HTMLSpanElement | null;
  ws.onopen = () => {
    statusEl?.classList.replace("badge-offline", "badge-online");
    if (statusEl) statusEl.textContent = "Online";
    sendWs({ action: "list_reports" });
    sendWs({ action: "list_chart_runs" });
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
  ws.onmessage = (event: MessageEvent) => {
    const data = JSON.parse(event.data) as ChatMessage;
    handleMessage(data);
  };
}

function handleMessage(message: ChatMessage) {
  const output = document.getElementById("report-output");
  const gameOutput = document.getElementById("game-day-output");
  if (message.action === "list_reports") {
    renderReports((message.reports as ReportItem[]) || []);
  }
  if (message.action === "generate_reports") {
    if (output && message.status === "complete") {
      output.textContent = JSON.stringify(message, null, 2);
    }
    if (message.status === "started" && output) {
      output.textContent = "Generating reports...";
    }
    if (message.status === "error" && output) {
      output.textContent = `Error: ${message.error || "Unknown"}`;
    }
  }
  if (message.action === "run_game_day") {
    if (gameOutput) {
      gameOutput.textContent = message.status === "complete"
        ? JSON.stringify(message.report, null, 2)
        : message.status === "started"
          ? "Running game day..."
          : `Error: ${message.error || "Unknown"}`;
    }
  }
  if (message.action === "list_chart_runs") {
    renderChartsGallery((message.runs as RunChartInfo[]) || []);
  }
  if (message.action === "charts_generated") {
    if (message.run_id) {
      sendWs({ action: "list_chart_runs" });
    }
  }
  if (message.action === "chart_metadata") {
    const meta = message.metadata as ChartMetadata[] | undefined;
    if (meta) window.__CHART_METADATA = meta;
  }
}

function renderReports(reports: ReportItem[]) {
  const grid = document.getElementById("reports-grid");
  if (!grid) return;
  grid.innerHTML = reports.map((r) => `
    <div class="report-card">
      <div class="name">${escapeHtml(r.name)}</div>
      <div class="meta">${formatBytes(r.sizeBytes)}</div>
      <a href="${escapeHtml(r.url)}" target="_blank">Open</a>
      <button data-open="${escapeHtml(r.url)}">View PDF</button>
    </div>
  `).join("");

  grid.querySelectorAll("button[data-open]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const url = (btn as HTMLButtonElement).dataset.open || "";
      openPdf(url);
    });
  });
}

async function openPdf(url: string) {
  const canvas = document.getElementById("pdf-canvas") as HTMLCanvasElement | null;
  const pageLabel = document.getElementById("pdf-page") as HTMLSpanElement | null;
  const openLink = document.getElementById("pdf-open") as HTMLAnchorElement | null;
  if (!canvas) return;
  currentPdfFile = url;
  if (openLink) openLink.href = url;

  const task = (window as any).pdfjsLib.getDocument(url);
  pdfDoc = await task.promise;
  currentPdfPage = 1;
  await renderPdfPage(canvas, pageLabel);
}

async function renderPdfPage(canvas: HTMLCanvasElement, pageLabel: HTMLSpanElement | null) {
  if (!pdfDoc) return;
  const page = await pdfDoc.getPage(currentPdfPage);
  const scale = 1.6;
  const viewport = page.getViewport({ scale });
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  await page.render({ canvasContext: ctx, viewport }).promise;
  if (pageLabel) pageLabel.textContent = `Page ${currentPdfPage} / ${pdfDoc.numPages}`;
}

let currentModalRunId = "";
let currentModalChartName = "";
let currentChartZoom = 100;

function renderChartsGallery(runs: RunChartInfo[]) {
  const gallery = document.getElementById("charts-gallery");
  if (!gallery) return;

  if (!runs.length) {
    gallery.innerHTML = `<div class="empty-items">No charts available yet. Generate reports to see charts here.</div>`;
    return;
  }

  gallery.innerHTML = runs.map((run) => {
    const runDate = new Date(run.timestamp).toLocaleString();
    const modelStr = (run.models || []).join(", ");
    const promptStr = (run.prompts || []).slice(0, 2).join(", ");
    const morePrompts = (run.prompts || []).length > 2 ? ` +${(run.prompts || []).length - 2} more` : "";
    const statusClass = run.returncode === 0 ? "badge-online" : "badge-offline";
    const statusText = run.returncode === 0 ? "Success" : `Exit ${run.returncode}`;

    const chartsHtml = (run.charts || []).map((chart) => {
      const sizeStr = formatBytes(chart.sizeBytes);
      return `
        <div class="chart-card" data-run-id="${escapeHtml(run.runId)}" data-chart-name="${escapeHtml(chart.name)}">
          <button class="chart-close-btn" data-delete-run="${escapeHtml(run.runId)}" data-delete-chart="${escapeHtml(chart.name)}" title="Delete chart">×</button>
          <img src="${escapeHtml(chart.url)}" alt="${escapeHtml(chart.displayName)}" loading="lazy">
          <div class="chart-card-body">
            <div class="chart-card-title">${escapeHtml(chart.displayName)}</div>
            <div class="chart-card-category">${escapeHtml(chart.category)}</div>
            <div class="chart-card-meta">
              <span>${sizeStr}</span>
              <span>${escapeHtml(chart.name)}</span>
            </div>
          </div>
        </div>
      `;
    }).join("");

    return `
      <div class="chart-run-section" data-run-id="${escapeHtml(run.runId)}">
        <div class="chart-run-header">
          <div class="chart-run-title">${escapeHtml(run.runName || run.runId)}</div>
          <div class="chart-run-meta">
            <span class="badge ${statusClass}">${statusText}</span>
            <span>${escapeHtml(runDate)}</span>
            <span class="chart-run-count">${(run.charts || []).length} charts</span>
          </div>
        </div>
        <div class="chart-run-models">
          <span class="chart-run-model">${escapeHtml(modelStr || "N/A")}</span>
          <span class="chart-run-prompt">${escapeHtml(promptStr || "")}${morePrompts}</span>
          <span class="chart-run-type">${escapeHtml(run.type || "")}</span>
          <span class="chart-run-duration">${escapeHtml(run.duration || "")}</span>
        </div>
        <div class="chart-run-charts">${chartsHtml}</div>
      </div>
    `;
  }).join("");

  // Wire up chart card click to open modal
  gallery.querySelectorAll(".chart-card").forEach((card) => {
    card.addEventListener("click", (e) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains("chart-close-btn")) return;
      const runId = (card as HTMLElement).dataset.runId || "";
      const chartName = (card as HTMLElement).dataset.chartName || "";
      openChartModal(runId, chartName);
    });
  });

  // Wire up delete buttons
  gallery.querySelectorAll("[data-delete-run]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const runId = (btn as HTMLElement).dataset.deleteRun || "";
      const chartName = (btn as HTMLElement).dataset.deleteChart || "";
      deleteChartFromChartsTab(runId, chartName);
    });
  });
}

function openChartModal(runId: string, chartName: string) {
  currentModalRunId = runId;
  currentModalChartName = chartName;
  currentChartZoom = 100;
  const modal = document.getElementById("chart-modal");
  const content = document.getElementById("chart-modal-content");
  const img = modal?.querySelector(".chart-modal-img") as HTMLImageElement | null;
  const zoomLevel = document.getElementById("chart-modal-zoom-level");
  if (!modal) return;
  if (img) {
    img.src = `/static/charts/${runId}/${chartName}.png`;
    img.style.width = "auto";
    img.style.height = "auto";
    img.style.maxWidth = "90vw";
    img.style.maxHeight = "80vh";
  }
  if (zoomLevel) zoomLevel.textContent = "100%";
  modal.classList.add("show");
  // Reset to centered position on open
  if (content) {
    content.style.transform = "none";
    content.style.left = "auto";
    content.style.top = "auto";
  }
}

function closeChartModal() {
  const modal = document.getElementById("chart-modal");
  if (modal) modal.classList.remove("show");
  currentModalRunId = "";
  currentModalChartName = "";
}

function deleteChartFromChartsTab(runId: string, chartName: string) {
  fetch(`/api/charts/runs/${runId}/${chartName}`, { method: "DELETE" })
    .then(() => {
      const card = document.querySelector(`.chart-card[data-run-id="${runId}"][data-chart-name="${chartName}"]`);
      if (card) (card as HTMLElement).remove();
      // If no charts remain in the run section, remove the entire frame
      const runSection = document.querySelector(`.chart-run-section[data-run-id="${runId}"]`);
      if (runSection) {
        const remaining = runSection.querySelectorAll(".chart-card").length;
        const countBadge = runSection.querySelector(".chart-run-count");
        if (countBadge) {
          countBadge.textContent = `${remaining} chart${remaining !== 1 ? "s" : ""}`;
        }
        if (remaining === 0) {
          runSection.remove();
        }
      }
      sendWs({ action: "list_chart_runs" });
    })
    .catch((err) => console.error("Delete failed:", err));
}

function escapeHtml(text: string) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function formatBytes(bytes?: number) {
  if (!bytes && bytes !== 0) return "";
  const value = bytes as number;
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function sendWs(message: ChatMessage) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
  }
}

function saveLocalStorage(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
}
function loadLocalStorage<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function init() {
  const savedEndpoints = loadLocalStorage<Endpoint[]>("we3.endpoints", []);
  endpoints.push(...savedEndpoints);

  const endpointSelect = document.getElementById("model-endpoint") as HTMLSelectElement | null;
  const endpointForm = document.getElementById("endpoint-form") as HTMLFormElement | null;
  const modelForm = document.getElementById("model-form") as HTMLFormElement | null;
  const reportForm = document.getElementById("report-form") as HTMLFormElement | null;
  const gameDayForm = document.getElementById("game-day-form") as HTMLFormElement | null;
  const refreshButton = document.getElementById("refresh-reports") as HTMLButtonElement | null;
  const pdfPrev = document.getElementById("pdf-prev") as HTMLButtonElement | null;
  const pdfNext = document.getElementById("pdf-next") as HTMLButtonElement | null;
  const tabs = document.querySelectorAll(".tab-link");

  function refreshEndpointOptions() {
    if (!endpointSelect) return;
    endpointSelect.innerHTML = endpoints.map((ep) => `<option value="${escapeHtml(ep.id)}">${escapeHtml(ep.name)}</option>`).join("");
  }
  function renderEndpoints() {
    const list = document.getElementById("endpoints-list");
    if (!list) return;
    list.innerHTML = endpoint.map((ep, idx) => `
      <div class="list-item">
        <div>
          <div class="name">${escapeHtml(ep.name)}</div>
          <div class="meta">${escapeHtml(ep.url)}</div>
        </div>
        <div>
          <button data-endpoint-test="${idx}" class="secondary">Test</button>
          <button data-endpoint-delete="${idx}" class="danger">Delete</button>
        </div>
      </div>
    `).join("");

    list.querySelectorAll("[data-endpoint-test]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const ep = endpoints[parseInt((btn as HTMLButtonElement).dataset.endpointTest || "0", 10)];
        if (!ep) return;
        try {
          const res = await fetch("/api/health");
          const json = await res.json();
          alert(`Endpoint test placeholder: ${ep.name} | API status: ${json.status}`);
        } catch (exc) {
          alert(`Endpoint test failed: ${exc}`);
        }
      });
    });
    list.querySelectorAll("[data-endpoint-delete]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = parseInt((btn as HTMLButtonElement).dataset.endpointDelete || "0", 10);
        endpoints.splice(idx, 1);
        saveLocalStorage("we3.endpoints", endpoints);
        renderEndpoints();
        refreshEndpointOptions();
      });
    });
  }
  function renderModels() {
    const list = document.getElementById("models-list");
    if (!list) return;
    list.innerHTML = models.map((m, idx) => {
      const endpoint = endpoints.find((ep) => ep.id === m.endpointId);
      return `
        <div class="list-item">
          <div>
            <div class="name">${escapeHtml(m.id)}</div>
            <div class="meta">${escapeHtml(m.provider)} - ${endpoint ? escapeHtml(endpoint.name) : "unknown"}</div>
          </div>
          <button data-model-delete="${idx}" class="danger">Delete</button>
        </div>
      `;
    }).join("");

    list.querySelectorAll("[data-model-delete]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = parseInt((btn as HTMLButtonElement).dataset.modelDelete || "0", 10);
        models.splice(idx, 1);
        saveLocalStorage("we3.models", models);
        renderModels();
      });
    });
  }
  function updateSelectedModels() {
    const container = document.getElementById("selected-models");
    if (!container) return;
    container.innerHTML = Array.from(selectedModelIds)
      .map((id) => `<span class="chip">${escapeHtml(id)} <button data-remove-model="${escapeHtml(id)}">x</button></span>`)
      .join("");

    container.querySelectorAll("[data-remove-model]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = (btn as HTMLButtonElement).dataset.removeModel || "";
        selectedModelIds.delete(id);
        updateSelectedModels();
      });
    });
  }

  endpointForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const nameInput = document.getElementById("endpoint-name") as HTMLInputElement | null;
    const urlInput = document.getElementById("endpoint-url") as HTMLInputElement | null;
    const apiKeyInput = document.getElementById("endpoint-api-key") as HTMLInputElement | null;
    const providerInput = document.getElementById("endpoint-provider") as HTMLSelectElement | null;
    const endpoint: Endpoint = {
      id: `ep_${Date.now()}`,
      name: nameInput?.value || "Unnamed",
      url: urlInput?.value || "",
      apiKey: apiKeyInput?.value || undefined,
      provider: (providerInput?.value as Endpoint["provider"]) || "ollama",
    };
    endpoints.push(endpoint);
    saveLocalStorage("we3.endpoints", endpoints);
    renderEndpoints();
    refreshEndpointOptions();
    endpointForm.reset();
  });

  modelForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const nameInput = document.getElementById("model-name") as HTMLInputElement | null;
    const endpointSelectEl = document.getElementById("model-endpoint") as HTMLSelectElement | null;
    const model: Model = {
      id: nameInput?.value || "unknown",
      endpointId: endpointSelectEl?.value || "",
      provider: "ollama",
    };
    models.push(model);
    saveLocalStorage("we3.models", models);
    selectedModelIds.add(model.id);
    updateSelectedModels();
    renderModels();
    modelForm.reset();
  });

  reportForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const promptsTextarea = document.getElementById("report-prompts") as HTMLTextAreaElement | null;
    const promptPackageSelect = document.getElementById("report-prompt-package") as HTMLSelectElement | null;
    const prompts = promptsTextarea?.value.split(",").map((p) => p.trim()).filter(Boolean) || [];
    const modelIds = Array.from(selectedModelIds);
    if (!modelIds.length) {
      alert("Please add models first.");
      return;
    }
    const promptPackage = promptPackageSelect?.value || "";
    sendWs({
      action: "generate_reports",
      models: modelIds,
      prompts,
      promptPackage,
    });
  });

  gameDayForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const authInput = document.getElementById("game-day-auth") as HTMLInputElement | null;
    sendWs({
      action: "run_game_day",
      authorization: authInput?.value || "",
    });
  });

  refreshButton?.addEventListener("click", () => {
    sendWs({ action: "list_reports" });
  });

  document.getElementById("stop-reports")?.addEventListener("click", () => {
    sendWs({ action: "stop_reports" });
    const output = document.getElementById("report-output");
    if (output) output.textContent = "Stopping...";
  });

  const panels = document.querySelectorAll(".tab-panel");
  const savedTab = localStorage.getItem("we3.activeTab");
  const defaultTab = savedTab || (tabs[0] && (tabs[0] as HTMLButtonElement).dataset.tab) || "tab-endpoints";
  tabs.forEach((tab) => {
    const target = (tab as HTMLButtonElement).dataset.tab || "";
    const isActive = target === defaultTab;
    if (isActive) {
      tab.classList.add("active");
      const panel = document.getElementById(target);
      if (panel) panel.classList.add("active");
    }
    tab.addEventListener("click", () => {
      const target = (tab as HTMLButtonElement).dataset.tab || "";
      tabs.forEach((t) => t.classList.remove("active"));
      panels.forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      const panel = document.getElementById(target);
      if (panel) panel.classList.add("active");
      localStorage.setItem("we3.activeTab", target);
    });
  });

  pdfPrev?.addEventListener("click", async () => {
    if (!pdfDoc || currentPdfPage <= 1) return;
    currentPdfPage -= 1;
    const canvas = document.getElementById("pdf-canvas") as HTMLCanvasElement | null;
    const pageLabel = document.getElementById("pdf-page") as HTMLSpanElement | null;
    await renderPdfPage(canvas as HTMLCanvasElement, pageLabel);
  });

  pdfNext?.addEventListener("click", async () => {
    if (!pdfDoc || currentPdfPage >= pdfDoc.numPages) return;
    currentPdfPage += 1;
    const canvas = document.getElementById("pdf-canvas") as HTMLCanvasElement | null;
    const pageLabel = document.getElementById("pdf-page") as HTMLSpanElement | null;
    await renderPdfPage(canvas as HTMLCanvasElement, pageLabel);
  });

   renderEndpoints();
  refreshEndpointOptions();
  renderModels();
  updateSelectedModels();
  sendWs({ action: "list_reports" });
  sendWs({ action: "list_chart_runs" });
  connectWebSocket();

  // Wire up chart modal close
  const chartModalClose = document.getElementById("chart-modal-close");
  chartModalClose?.addEventListener("click", closeChartModal);
  const chartModalBackdrop = document.getElementById("chart-modal-backdrop");
  chartModalBackdrop?.addEventListener("click", closeChartModal);

  // Wire up PDF modal close on backdrop click
  const pdfModalClose = document.getElementById("pdf-modal-close");
  const pdfModalBackdrop = document.getElementById("pdf-modal-backdrop");
  pdfModalClose?.addEventListener("click", () => {
    const modal = document.getElementById("pdf-modal");
    if (modal) modal.classList.remove("show");
  });
  pdfModalBackdrop?.addEventListener("click", () => {
    const modal = document.getElementById("pdf-modal");
    if (modal) modal.classList.remove("show");
  });

  // Wire up raw-data modal close on backdrop click
  const rawDataModalClose = document.getElementById("raw-data-modal-close");
  const rawDataModalBackdrop = document.getElementById("raw-data-modal-backdrop");
  rawDataModalClose?.addEventListener("click", () => {
    const modal = document.getElementById("raw-data-modal");
    if (modal) modal.classList.remove("show");
  });
  rawDataModalBackdrop?.addEventListener("click", () => {
    const modal = document.getElementById("raw-data-modal");
    if (modal) modal.classList.remove("show");
  });

  // Init chart modal drag
  initChartModalDrag();
}

function initChartModalDrag() {
  const modal = document.getElementById("chart-modal");
  const header = document.getElementById("chart-modal-header");
  const content = document.getElementById("chart-modal-content");
  const img = modal?.querySelector(".chart-modal-img") as HTMLImageElement | null;
  if (!modal || !header || !content) return;

  let isDragging = false;
  let offsetX = 0;
  let offsetY = 0;

  header.addEventListener("mousedown", (e) => {
    if ((e.target as HTMLElement).closest("button")) return;
    e.preventDefault();
    isDragging = true;
    const rect = content.getBoundingClientRect();
    offsetX = e.clientX - rect.left;
    offsetY = e.clientY - rect.top;
    header.style.cursor = "grabbing";
    content.style.transition = "none";
  });

  document.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    e.preventDefault();
    const modalRect = modal.getBoundingClientRect();
    const contentRect = content.getBoundingClientRect();
    let newX = e.clientX - offsetX;
    let newY = e.clientY - offsetY;
    const maxX = modalRect.width - contentRect.width;
    const maxY = modalRect.height - contentRect.height;
    if (maxX > 0) newX = Math.max(0, Math.min(newX, maxX));
    if (maxY > 0) newY = Math.max(0, Math.min(newY, maxY));
    content.style.left = `${newX}px`;
    content.style.top = `${newY}px`;
    content.style.transform = "none";
  });

  document.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      header.style.cursor = "grab";
      content.style.transition = "";
    }
  });

  // Zoom controls
  const zoomInBtn = document.getElementById("chart-modal-zoom-in");
  const zoomOutBtn = document.getElementById("chart-modal-zoom-out");
  const zoomResetBtn = document.getElementById("chart-modal-zoom-reset");
  const zoomLevelEl = document.getElementById("chart-modal-zoom-level");

  function updateZoom() {
    if (zoomLevelEl) zoomLevelEl.textContent = `${currentChartZoom}%`;
    if (img) {
      img.style.width = "auto";
      img.style.height = "auto";
      img.style.maxWidth = `${currentChartZoom}vw`;
      img.style.maxHeight = `${85 * (100 / currentChartZoom)}vh`;
    }
  }

  zoomInBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (currentChartZoom < 300) {
      currentChartZoom = Math.min(currentChartZoom + 10, 300);
      updateZoom();
    }
  });

  zoomOutBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (currentChartZoom > 50) {
      currentChartZoom = Math.max(currentChartZoom - 10, 50);
      updateZoom();
    }
  });

  zoomResetBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    currentChartZoom = 100;
    updateZoom();
    content.style.left = "auto";
    content.style.top = "auto";
    content.style.transform = "none";
  });

  // Mouse wheel zoom on the image
  if (img) {
    img.addEventListener("wheel", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.deltaY < 0) {
        if (currentChartZoom < 300) currentChartZoom = Math.min(currentChartZoom + 10, 300);
      } else {
        if (currentChartZoom > 50) currentChartZoom = Math.max(currentChartZoom - 10, 50);
      }
      updateZoom();
    }, { passive: false });
  }
}

(document.getElementById("tab-charts") as HTMLElement | null)?.addEventListener("click", () => {
  sendWs({ action: "list_chart_runs" });
});

document.addEventListener("DOMContentLoaded", init);