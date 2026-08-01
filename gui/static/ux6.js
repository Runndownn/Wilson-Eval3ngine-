(() => {
  "use strict";

  const MARGIN = 8;

  function clampChartWindow() {
    const windowElement = document.getElementById("chart-window");
    if (!windowElement || windowElement.classList.contains("hidden") || windowElement.classList.contains("fullscreen")) {
      return;
    }

    const viewportWidth = document.documentElement.clientWidth;
    const viewportHeight = document.documentElement.clientHeight;
    const maxWidth = Math.max(320, viewportWidth - MARGIN * 2);
    const maxHeight = Math.max(280, viewportHeight - MARGIN * 2);

    if (windowElement.offsetWidth > maxWidth) {
      windowElement.style.width = `${maxWidth}px`;
    }
    if (windowElement.offsetHeight > maxHeight) {
      windowElement.style.height = `${maxHeight}px`;
    }

    const rect = windowElement.getBoundingClientRect();
    const left = Math.min(
      Math.max(MARGIN, rect.left),
      Math.max(MARGIN, viewportWidth - rect.width - MARGIN),
    );
    const top = Math.min(
      Math.max(MARGIN, rect.top),
      Math.max(MARGIN, viewportHeight - rect.height - MARGIN),
    );

    windowElement.style.left = `${left}px`;
    windowElement.style.top = `${top}px`;
  }

  function installViewportGuard() {
    const windowElement = document.getElementById("chart-window");
    if (!windowElement || windowElement.dataset.viewportGuardInstalled === "true") {
      return;
    }
    windowElement.dataset.viewportGuardInstalled = "true";

    let frame = 0;
    const scheduleClamp = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(clampChartWindow);
    };

    document.addEventListener("pointermove", scheduleClamp, true);
    document.addEventListener("pointerup", scheduleClamp, true);
    window.addEventListener("resize", scheduleClamp, { passive: true });
    window.visualViewport?.addEventListener("resize", scheduleClamp, { passive: true });
    window.visualViewport?.addEventListener("scroll", scheduleClamp, { passive: true });

    new MutationObserver(scheduleClamp).observe(windowElement, {
      attributes: true,
      attributeFilter: ["class", "style"],
    });
    new ResizeObserver(scheduleClamp).observe(windowElement);

    const headerActions = windowElement.querySelector(".window-actions");
    if (headerActions && !document.getElementById("chart-window-reset")) {
      const reset = document.createElement("button");
      reset.id = "chart-window-reset";
      reset.type = "button";
      reset.textContent = "Reset window";
      reset.addEventListener("click", () => {
        windowElement.classList.remove("fullscreen");
        windowElement.style.width = "min(1120px, 80vw)";
        windowElement.style.height = "min(760px, 82vh)";
        windowElement.style.left = "10vw";
        windowElement.style.top = "8vh";
        scheduleClamp();
      });
      headerActions.prepend(reset);
    }

    scheduleClamp();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installViewportGuard, { once: true });
  } else {
    installViewportGuard();
  }
})();
