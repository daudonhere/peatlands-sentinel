(function () {
  "use strict";

  const map = new maplibregl.Map({
    container: "map",
    style: MAP_STYLE_SATELLITE,
    center: [102.5, 0.5],
    zoom: 9,
  });

  map.addControl(
    new maplibregl.NavigationControl({ showCompass: true }),
    "top-right",
  );

  const coordsText = document.getElementById("coords-text");
  const aoiStatusText = document.getElementById("aoi-status-text");
  const aoiPresetSelect = document.getElementById("aoi-preset");
  const analysisTargetSelect = document.getElementById("analysis-target");
  const dockToggleBtn = document.getElementById("dock-toggle-btn");
  const dockBody = document.getElementById("dock-body");

  const resultsCard = document.getElementById("results-card");
  const resultsCloseBtn = document.getElementById("results-close-btn");
  const resultsEmpty = document.getElementById("results-empty");
  const resultsLoading = document.getElementById("results-loading");
  const resultsContent = document.getElementById("results-content");
  const resultsError = document.getElementById("results-error");
  const resultsErrorText = document.getElementById("results-error-text");

  const resultsTargetLabel = document.getElementById("results-target-label");
  const resultsHeading = document.getElementById("results-heading");
  const statusHeadline = document.getElementById("status-headline");
  const statusSubline = document.getElementById("status-subline");
  const statusBanner = document.getElementById("status-banner");

  const valNdvi = document.getElementById("val-ndvi");
  const valNdwi = document.getElementById("val-ndwi");
  const valDnbr = document.getElementById("val-dnbr");
  const valSar = document.getElementById("val-sar");
  const analystSummary = document.getElementById("analyst-summary");
  const analystActions = document.getElementById("analyst-actions");

  const btnRunAnalysis = document.getElementById("btn-run-analysis");
  const btnInspectScenes = document.getElementById("btn-inspect-scenes");
  const btnExportZip = document.getElementById("btn-export-zip");

  let currentRunId = null;

  function getBbox() {
    const b = map.getBounds();
    return [
      Number(b.getWest().toFixed(4)),
      Number(b.getSouth().toFixed(4)),
      Number(b.getEast().toFixed(4)),
      Number(b.getNorth().toFixed(4)),
    ];
  }

  function updateCoords() {
    coordsText.textContent = `[${getBbox().join(", ")}]`;
  }

  function renderAoiPolygon(bbox, colorHex) {
    const [w, s, e, n] = bbox;
    const geojson = {
      type: "Feature",
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [w, s],
            [e, s],
            [e, n],
            [w, n],
            [w, s],
          ],
        ],
      },
    };

    if (map.getSource("aoi-boundary")) {
      map.getSource("aoi-boundary").setData(geojson);
    } else {
      map.addSource("aoi-boundary", { type: "geojson", data: geojson });
      map.addLayer({
        id: "aoi-fill",
        type: "fill",
        source: "aoi-boundary",
        paint: {
          "fill-color": colorHex,
          "fill-opacity": 0.12,
        },
      });
      map.addLayer({
        id: "aoi-stroke",
        type: "line",
        source: "aoi-boundary",
        paint: {
          "line-color": colorHex,
          "line-width": 2,
          "line-dasharray": [2, 2],
        },
      });
    }
  }

  map.on("moveend", updateCoords);
  map.on("load", function () {
    updateCoords();
    renderAoiPolygon(getBbox(), "#10b981");
  });

  dockToggleBtn.addEventListener("click", function () {
    const isCollapsed = dockBody.classList.toggle("collapsed");
    dockToggleBtn.innerHTML = isCollapsed ? "+" : "&minus;";
    dockToggleBtn.setAttribute("aria-expanded", String(!isCollapsed));
  });

  resultsCloseBtn.addEventListener("click", function () {
    resultsCard.classList.add("hidden");
  });

  aoiPresetSelect.addEventListener("change", function (e) {
    const key = e.target.value;
    if (key in MAP_PRESETS) {
      const preset = MAP_PRESETS[key];
      map.flyTo({ center: preset.center, zoom: preset.zoom, essential: true });
      aoiStatusText.textContent = `AOI: ${preset.name}`;
    } else {
      aoiStatusText.textContent = "AOI: Custom Viewport";
    }
  });

  if (btnExportZip) {
    btnExportZip.addEventListener("click", function () {
      if (!currentRunId) return;
      window.location.href = `/api/analysis/${currentRunId}/export`;
    });
  }

  btnRunAnalysis.addEventListener("click", async function () {
    resultsCard.classList.remove("hidden");
    resultsEmpty.classList.add("hidden");
    resultsContent.classList.add("hidden");
    resultsError.classList.add("hidden");
    resultsLoading.classList.remove("hidden");

    const selectedTargetKey = analysisTargetSelect.value;
    const selectedTargetText =
      analysisTargetSelect.options[analysisTargetSelect.selectedIndex].text;
    const dateStart =
      document.getElementById("date-start").value || "2024-01-01";
    const dateEnd = document.getElementById("date-end").value || "2024-12-31";

    resultsTargetLabel.textContent =
      selectedTargetText.split(". ")[1] || selectedTargetText;
    resultsHeading.textContent = "Telemetry & AI Diagnostic";

    const bbox = getBbox();
    const [w, s, e, n] = bbox;
    const geojsonPolygon = {
      type: "Polygon",
      coordinates: [
        [
          [w, s],
          [e, s],
          [e, n],
          [w, n],
          [w, s],
        ],
      ],
    };

    try {
      const data = await fetchPipelineAnalysis({
        aoi: geojsonPolygon,
        target: selectedTargetKey,
        pre_date_range: "2023-01-01/2023-12-31",
        post_date_range: `${dateStart}/${dateEnd}`,
      });
      currentRunId = data.run_id;

      const metrics = data.spectral_metrics || {};
      const aiReport = data.ai_report || {};

      valNdvi.textContent = Number(metrics.mean_ndvi || 0).toFixed(2);
      valNdwi.textContent = Number(metrics.mean_ndwi || 0).toFixed(2);
      valDnbr.textContent = Number(metrics.max_dnbr || 0).toFixed(2);
      valSar.textContent = `${Number(metrics.mean_sar_cross_ratio || 0).toFixed(1)} dB`;

      statusHeadline.textContent = `Threat Status: ${aiReport.threat_level}`;
      statusSubline.textContent = `Moisture Condition: ${aiReport.peat_moisture_status} (${data.area_hectares} Ha)`;

      let boundaryColor = "#10b981";
      if (
        aiReport.threat_level === "Critical" ||
        aiReport.threat_level === "High"
      ) {
        boundaryColor = "#f43f5e";
        statusBanner.style.backgroundColor = "rgba(244, 63, 94, 0.15)";
        statusBanner.style.borderColor = "rgba(244, 63, 94, 0.4)";
        statusHeadline.style.color = "#fca5a5";
      } else if (aiReport.threat_level === "Moderate") {
        boundaryColor = "#f59e0b";
        statusBanner.style.backgroundColor = "rgba(245, 158, 11, 0.15)";
        statusBanner.style.borderColor = "rgba(245, 158, 11, 0.4)";
        statusHeadline.style.color = "#fde68a";
      } else {
        statusBanner.style.backgroundColor = "rgba(16, 185, 129, 0.15)";
        statusBanner.style.borderColor = "rgba(16, 185, 129, 0.4)";
        statusHeadline.style.color = "#6ee7b7";
      }

      renderAoiPolygon(bbox, boundaryColor);

      analystSummary.textContent = `${aiReport.fire_risk_summary} ${aiReport.classification_reasoning}`;
      analystActions.innerHTML = "";
      (aiReport.recommended_actions || []).forEach(function (action) {
        const li = document.createElement("li");
        li.textContent = action;
        analystActions.appendChild(li);
      });

      resultsContent.classList.remove("hidden");
    } catch (err) {
      resultsErrorText.textContent =
        "Analysis execution failed: " + err.message;
      resultsError.classList.remove("hidden");
    } finally {
      resultsLoading.classList.add("hidden");
    }
  });

  btnInspectScenes.addEventListener("click", async function () {
    const originalText = btnInspectScenes.textContent;
    btnInspectScenes.textContent = "Scanning STAC...";
    btnInspectScenes.disabled = true;

    try {
      const data = await fetchAoiScenes(getBbox());
      const countS2 = (data.optical_scenes || []).length;
      const countS1 = (data.sar_scenes || []).length;
      aoiStatusText.textContent = `Found ${countS2} Sentinel-2 and ${countS1} Sentinel-1 passes`;
    } catch (err) {
      aoiStatusText.textContent = "Pass inspection failed: " + err.message;
    } finally {
      btnInspectScenes.textContent = originalText;
      btnInspectScenes.disabled = false;
    }
  });
})();
