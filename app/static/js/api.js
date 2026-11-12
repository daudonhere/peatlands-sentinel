async function fetchPipelineAnalysis(payload) {
  const response = await fetch("/api/analysis/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`API returned HTTP ${response.status}`);
  }
  return response.json();
}

async function fetchAoiScenes(bbox) {
  const response = await fetch("/api/peatlands/scenes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      bbox: bbox,
      datetime_range: "2024-01-01/2024-12-31",
    }),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function fetchHistoryList() {
  const response = await fetch("/api/analysis/history/list");
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function fetchRunDetails(runId) {
  const response = await fetch(`/api/analysis/${runId}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return data;
}

function fetchActiveFires(bbox, days) {
  return postJson("/api/insights/fires", { bbox: bbox, days: days });
}

function fetchLiveNdvi(bbox, datetimeRange) {
  return postJson("/api/insights/live-ndvi", { bbox: bbox, datetime_range: datetimeRange });
}

async function fetchIntervention(runId, damsPer100ha) {
  const response = await fetch(`/api/insights/${runId}/intervention?dams_per_100ha=${damsPer100ha}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}
