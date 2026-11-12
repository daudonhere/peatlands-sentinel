function createHistoryController(onSelectRun) {
  const modal = document.getElementById("history-modal");
  const btnOpen = document.getElementById("btn-open-history");
  const btnClose = document.getElementById("history-close-btn");
  const listContainer = document.getElementById("history-list");

  async function loadHistory() {
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
          </div>
        `;

        item
          .querySelector(".btn-load")
          .addEventListener("click", async function () {
            const runDetails = await fetchRunDetails(run.id);
            if (onSelectRun) onSelectRun(runDetails);
            modal.classList.add("hidden");
          });

        listContainer.appendChild(item);
      });
    } catch (err) {
      listContainer.innerHTML = `<p class="error-text">Failed to load history: ${err.message}</p>`;
    }
  }

  if (btnOpen) {
    btnOpen.addEventListener("click", function () {
      modal.classList.remove("hidden");
      loadHistory();
    });
  }

  if (btnClose) {
    btnClose.addEventListener("click", function () {
      modal.classList.add("hidden");
    });
  }

  return {
    reload: loadHistory,
  };
}
