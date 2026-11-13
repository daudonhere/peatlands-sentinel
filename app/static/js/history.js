function createHistoryController(onSelectRun) {
  const listContainer = document.getElementById("history-list");
  const btnOpen = document.getElementById("btn-open-history");
  const btnOpenDrawer = document.getElementById("btn-open-history-drawer");

  async function loadHistory() {
    if (!listContainer) return;
    listContainer.innerHTML =
      '<p class="results-state-desc">Loading stored analysis records...</p>';
    try {
      const runs = await fetchHistoryList();
      if (!runs || runs.length === 0) {
        listContainer.innerHTML =
          '<p class="results-state-desc">No analysis history recorded yet.</p>';
        return;
      }

      listContainer.innerHTML = "";
      runs.forEach(function (run) {
        const item = document.createElement("div");
        item.className = "history-card";

        const dateStr = run.created_at
          ? run.created_at.substring(0, 16).replace("T", " ")
          : "";
        item.innerHTML = `
          <div class="history-top">
            <span class="history-id">${run.id}</span>
            <span class="history-date">${dateStr}</span>
          </div>
          <div class="history-body">
            <span><strong>Target:</strong> ${run.target}</span>
            <span>${run.area_hectares} Ha</span>
          </div>
          <div class="history-actions">
            <button type="button" class="btn btn-primary btn-sm btn-load" data-id="${run.id}">Load Map</button>
            <a href="/api/analysis/${run.id}/export" class="btn btn-outline btn-sm">ZIP</a>
            <button type="button" class="btn btn-outline btn-sm btn-delete" data-id="${run.id}" aria-label="Delete history" style="color:#ef4444;border-color:#ef4444;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path></svg>
            </button>
          </div>
        `;

        item
          .querySelector(".btn-load")
          .addEventListener("click", async function () {
            const runDetails = await fetchRunDetails(run.id);
            if (onSelectRun) onSelectRun(runDetails);
          });

        const deleteBtn = item.querySelector(".btn-delete");
        if (deleteBtn) {
          deleteBtn.addEventListener("click", async function () {
            try {
              await deleteAnalysisRun(run.id);
              loadHistory();
            } catch (err) {
              alert("Failed to delete history: " + err.message);
            }
          });
        }

        listContainer.appendChild(item);
      });
    } catch (err) {
      listContainer.innerHTML = `<p class="error-text">Failed to load history: ${err.message}</p>`;
    }
  }

  function openHistory() {
    loadHistory();
    if (listContainer) listContainer.scrollIntoView({ behavior: "smooth" });
  }

  if (btnOpen) {
    btnOpen.addEventListener("click", openHistory);
  }
  if (btnOpenDrawer) {
    btnOpenDrawer.addEventListener("click", openHistory);
  }

  return {
    reload: loadHistory,
  };
}
