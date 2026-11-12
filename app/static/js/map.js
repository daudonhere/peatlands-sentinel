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
  const valWtd = document.getElementById("val-wtd");
  const valSubsidence = document.getElementById("val-subsidence");
  const valCo2 = document.getElementById("val-co2");
  const valSource = document.getElementById("val-source");
  const analystSummary = document.getElementById("analyst-summary");
  const analystActions = document.getElementById("analyst-actions");

  const btnRunAnalysis = document.getElementById("btn-run-analysis");
  const btnInspectScenes = document.getElementById("btn-inspect-scenes");
  const btnExportZip = document.getElementById("btn-export-zip");

  let currentRunId = null;
  let activeCustomGeometry = null;

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

  function applyThreatStyles(threatLevel) {
    let boundaryColor = "#7a7a7a";
    if (threatLevel === "Critical" || threatLevel === "High") {
      boundaryColor = "#ffffff";
      statusBanner.style.backgroundColor = "#1a1a1a";
      statusBanner.style.borderColor = "#ffffff";
      statusHeadline.style.color = "#ffffff";
    } else if (threatLevel === "Moderate") {
      boundaryColor = "#b3b3b3";
      statusBanner.style.backgroundColor = "#1a1a1a";
      statusBanner.style.borderColor = "#b3b3b3";
      statusHeadline.style.color = "#b3b3b3";
    } else {
      statusBanner.style.backgroundColor = "#141414";
      statusBanner.style.borderColor = "#555555";
      statusHeadline.style.color = "#a0a0a0";
    }
    return boundaryColor;
  }

  function displayAnalysisData(runData, bbox) {
    currentRunId = runData.run_id || runData.id;
    const metrics = runData.spectral_metrics || runData.metrics || {};
    const aiReport = runData.ai_report || {};

    valNdvi.textContent = Number(metrics.mean_ndvi || 0).toFixed(2);
    valNdwi.textContent = Number(metrics.mean_ndwi || 0).toFixed(2);
    valDnbr.textContent = Number(metrics.max_dnbr || 0).toFixed(2);
    valSar.textContent = `${Number(metrics.mean_sar_cross_ratio || 0).toFixed(1)} dB`;
    if (valWtd) {
      valWtd.textContent = `${Number(metrics.water_table_depth_cm || -35).toFixed(0)} cm`;
    }
    if (valSubsidence) {
      valSubsidence.textContent = `${Number(metrics.subsidence_rate_cm_year || 1.9).toFixed(1)} cm/yr`;
    }
    if (valCo2) {
      valCo2.textContent = `${Number(metrics.co2_emission_tco2e_ha_year || 0).toFixed(1)} tCO2e/ha`;
    }
    if (valSource) {
      const src = metrics.source === "live_cog" ? "Live COG" : "Simulation";
      const dt = metrics.post_datetime ? ` (${metrics.post_datetime})` : "";
      valSource.textContent = `${src}${dt}`;
      valSource.style.color =
        metrics.source === "live_cog"
          ? "var(--status-emerald)"
          : "var(--status-amber)";
    }

    statusHeadline.textContent = `Threat Status: ${aiReport.threat_level || "Unknown"}`;
    statusSubline.textContent = `Moisture Condition: ${aiReport.peat_moisture_status || "-"} (${runData.area_hectares} Ha)`;

    const boundaryColor = applyThreatStyles(aiReport.threat_level);
    const geometry =
      runData.geojson && runData.geojson.geometry
        ? runData.geojson.geometry
        : bbox;
    renderAoiPolygon(map, geometry, boundaryColor);

    analystSummary.textContent = `${aiReport.fire_risk_summary || ""} ${aiReport.classification_reasoning || ""}`;
    analystActions.innerHTML = "";
    (aiReport.recommended_actions || []).forEach(function (action) {
      const li = document.createElement("li");
      li.textContent = action;
      analystActions.appendChild(li);
    });

    insightsCtrl.renderTransitions(
      runData.land_transitions || runData.transitions,
    );
    insightsCtrl.refreshIntervention();
    resultsContent.classList.remove("hidden");
  }

  const drawCtrl = createDrawController(map, function (geom) {
    activeCustomGeometry = geom;
    if (geom) {
      aoiStatusText.textContent = "AOI: Drawn Custom Polygon";
    } else {
      aoiStatusText.textContent = "AOI: Viewport";
    }
  });

  const overlayCtrl = createRasterOverlayController(map);

  const insightsCtrl = createInsightsController(
    map,
    getBbox,
    function () {
      return currentRunId;
    },
    function () {
      return `${document.getElementById("date-start").value || "2024-01-01"}/${document.getElementById("date-end").value || "2024-12-31"}`;
    },
  );

  const historyCtrl = createHistoryController(function (runDetails) {
    resultsCard.classList.remove("hidden");
    resultsEmpty.classList.add("hidden");
    resultsLoading.classList.add("hidden");
    resultsError.classList.add("hidden");

    const bbox =
      runDetails.geojson && runDetails.geojson.bbox
        ? runDetails.geojson.bbox
        : getBbox();
    const [w, s, e, n] = bbox;
    map.fitBounds(
      [
        [w, s],
        [e, n],
      ],
      { padding: 40 },
    );

    displayAnalysisData(runDetails, bbox);
    overlayCtrl.setOverlay(runDetails.id, bbox);
  });

  map.on("moveend", function () {
    updateCoords();
    if (!activeCustomGeometry && !currentRunId) {
      renderAoiPolygon(map, getBbox(), "#ffffff");
    }
  });
  map.on("load", function () {
    updateCoords();
    renderAoiPolygon(map, getBbox(), "#ffffff");
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
    drawCtrl.clear();
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

    const splitLabel = selectedTargetText.split(". ")[1];
    resultsTargetLabel.textContent = splitLabel
      ? splitLabel
      : selectedTargetText;
    resultsHeading.textContent = "Telemetry & AI Diagnostic";

    const bbox = getBbox();
    const [w, s, e, n] = bbox;
    const payloadPolygon = activeCustomGeometry || {
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
        aoi: payloadPolygon,
        target: selectedTargetKey,
        pre_date_range: "2023-01-01/2023-12-31",
        post_date_range: `${dateStart}/${dateEnd}`,
      });

      displayAnalysisData(data, bbox);
      overlayCtrl.setOverlay(data.run_id, bbox);
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
