(function startNexus(N) {
  "use strict";

  window.addEventListener("DOMContentLoaded", async function initialize() {
    try {
      const workbench = new N.ui.Workbench();
      N.workbench = workbench;
      await workbench.initialize();
      N.ready = true;
    } catch (error) {
      console.error(error);
      document.documentElement.dataset.nexusStatus = "error";
      const region = document.getElementById("toast-region");
      if (region) {
        const notice = document.createElement("div");
        notice.className = "toast error";
        notice.textContent = `QSOL NEXUS could not start: ${error.message || String(error)}`;
        region.appendChild(notice);
      }
      const status = document.getElementById("execution-status");
      const detail = document.getElementById("execution-detail");
      if (status) status.textContent = "STARTUP ERROR";
      if (detail) detail.textContent = error.message || String(error);
    }
  });
})(window.QSOL_NEXUS);
