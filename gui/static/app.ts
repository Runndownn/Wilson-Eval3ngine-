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
  connectWebSocket();
}

document.addEventListener("DOMContentLoaded", init);