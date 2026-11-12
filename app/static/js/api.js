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
