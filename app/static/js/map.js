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
    "bottom-right",
  );

  (function () {
    let orbiting = false;
    let rafId = null;

    function stopOrbit() {
      orbiting = false;
      if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
      map.easeTo({ pitch: 0, bearing: 0, duration: 800 });
      const btn = document.querySelector(".orbit-toggle-btn");
      if (btn) btn.textContent = "3D";
    }

    function startOrbit() {
      orbiting = true;
      const btn = document.querySelector(".orbit-toggle-btn");
      if (btn) btn.textContent = "2D";
      map.easeTo({ pitch: 60, duration: 800 });
      const tick = function () {
        if (!orbiting) return;
        map.setBearing(map.getBearing() + 0.3);
        rafId = requestAnimationFrame(tick);
      };
      setTimeout(function () {
        if (orbiting) tick();
      }, 850);
    }

    const container = document.createElement("div");
    container.className = "maplibregl-ctrl maplibregl-ctrl-group";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "orbit-toggle-btn";
    btn.textContent = "3D";
    btn.title = "Toggle 3D orbit";
    btn.addEventListener("click", function () {
      if (orbiting) {
        stopOrbit();
      } else {
        startOrbit();
      }
    });
    container.appendChild(btn);

    const ctrl = {
      onAdd: function () {
        return container;
      },
      onRemove: function () {
        if (container.parentNode) {
          container.parentNode.removeChild(container);
        }
      },
    };
    map.addControl(ctrl, "bottom-right");

    map.on("mousedown", function () {
      if (orbiting) stopOrbit();
    });
  })();

  const coordsText = document.getElementById("coords-text");

  const todayIso = new Date().toISOString().slice(0, 10);
  const dateStartInput = document.getElementById("date-start");
  const dateEndInput = document.getElementById("date-end");
  if (dateStartInput) {
    dateStartInput.max = todayIso;
    if (dateStartInput.value > todayIso) dateStartInput.value = todayIso;
  }
  if (dateEndInput) {
    dateEndInput.max = todayIso;
    dateEndInput.value = todayIso;
  }
  const aoiStatusText = document.getElementById("aoi-status-text");
  const analysisTargetSelect = document.getElementById("analysis-target");
  const dockToggleBtn = document.getElementById("dock-toggle-btn");
  const dockBody = document.getElementById("dock-body");

  const resultsCard = document.getElementById("results-card");
  const historyPanel = document.getElementById("history-panel");
  const inspectPanel = document.getElementById("inspect-panel");
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

  function showPanel(name) {
    const panels = [
      "results-empty",
      "results-loading",
      "results-error",
      "results-content",
      "history-panel",
      "inspect-panel",
    ];
    panels.forEach(function (id) {
      const el = document.getElementById(id);
      if (!el) return;
      if (id === name) {
        el.classList.remove("hidden");
      } else {
        el.classList.add("hidden");
      }
    });
  }

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
    const isHigh = threatLevel === "Critical" || threatLevel === "High";
    const isMod = threatLevel === "Moderate";
    const color = isHigh ? "#ffffff" : isMod ? "#b3b3b3" : "#7a7a7a";
    statusBanner.style.backgroundColor =
      isHigh || isMod ? "#1a1a1a" : "#141414";
    statusBanner.style.borderColor = isHigh
      ? "#ffffff"
      : isMod
        ? "#b3b3b3"
        : "#555555";
    statusHeadline.style.color = isHigh
      ? "#ffffff"
      : isMod
        ? "#b3b3b3"
        : "#a0a0a0";
    return color;
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

    const resultsDrawer = document.getElementById("results-card");
    if (resultsDrawer && resultsDrawer.classList.contains("collapsed")) {
      resultsDrawer.classList.remove("collapsed");
      const toggle = document.getElementById("drawer-toggle");
      if (toggle) {
        toggle.style.right = "400px";
        toggle.textContent = "\u00bb";
      }
    }

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
    insightsCtrl.renderTimeSeries(runData.time_series);
    insightsCtrl.renderClassScatter(runData.class_scatter);
    insightsCtrl.renderModelAccuracy(runData.accuracy);
    insightsCtrl.refreshIntervention();
    resultsContent.classList.remove("hidden");
  }

  const drawCtrl = createDrawController(map, function (geom) {
    activeCustomGeometry = geom;
    if (aoiStatusText) {
      if (geom) {
        aoiStatusText.textContent = "AOI: Drawn Custom Polygon";
      } else {
        aoiStatusText.textContent = "AOI: Viewport";
      }
    }
    if (geom) loadFirmsForAoi();
  });

  function getActiveGeometry() {
    return activeCustomGeometry || drawCtrl.getGeometry();
  }

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
    resultsCard.classList.remove("collapsed");
    const drawerToggle = document.getElementById("drawer-toggle");
    if (drawerToggle) {
      drawerToggle.style.right = "400px";
      drawerToggle.textContent = "\u00bb";
    }
    showPanel("results-content");
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
  });
  map.on("load", function () {
    updateCoords();
  });

  if (btnExportZip) {
    btnExportZip.addEventListener("click", function () {
      if (!currentRunId) return;
      window.location.href = `/api/analysis/${currentRunId}/export`;
    });
  }

  const basemapSelect = document.getElementById("basemap-select");
  if (basemapSelect) {
    basemapSelect.addEventListener("change", function () {
      switchBasemap(map, basemapSelect.value);
    });
  }

  btnRunAnalysis.addEventListener("click", async function () {
    const activeGeometry = getActiveGeometry();
    if (!activeGeometry) {
      resultsCard.classList.remove("hidden");
      resultsEmpty.classList.add("hidden");
      resultsContent.classList.add("hidden");
      resultsError.classList.remove("hidden");
      resultsErrorText.textContent =
        "Gambar boundary AOI terlebih dahulu sebelum menjalankan analisis.";
      return;
    }

    resultsCard.classList.remove("hidden");
    resultsCard.classList.remove("collapsed");
    const drawerToggle = document.getElementById("drawer-toggle");
    if (drawerToggle) {
      drawerToggle.style.right = "400px";
      drawerToggle.textContent = "\u00bb";
    }
    showPanel("results-loading");
    const loadingDesc = document.querySelector(
      "#results-loading .results-state-desc",
    );
    if (loadingDesc) {
      const dsSelect = document.getElementById("data-source-select");
      const ds = dsSelect ? dsSelect.value : "planetary_computer";
      loadingDesc.textContent =
        ds === "gee"
          ? "Querying Google Earth Engine assets and computing spectral signatures..."
          : "Querying STAC assets and computing spectral signatures...";
    }

    const selectedTargetKey = "peat_moisture";
    const selectedTargetText = "Peatland Moisture and Extent (S1 + S2)";
    const dateStart =
      document.getElementById("date-start").value || "2024-01-01";
    const dateEnd = document.getElementById("date-end").value || "2024-12-31";
    const dataSourceSelect = document.getElementById("data-source-select");
    const granularitySelect = document.getElementById("granularity-select");

    const splitLabel = selectedTargetText.split(". ")[1];
    resultsTargetLabel.textContent = splitLabel
      ? splitLabel
      : selectedTargetText;
    resultsHeading.textContent = "Telemetry & AI Diagnostic";

    const bbox = getBbox();
    const payloadPolygon = getActiveGeometry();

    try {
      const payload = {
        aoi: payloadPolygon,
        target: selectedTargetKey,
        pre_date_range: "2023-01-01/2023-12-31",
        post_date_range: `${dateStart}/${dateEnd}`,
        data_source: dataSourceSelect
          ? dataSourceSelect.value
          : "planetary_computer",
        granularity: granularitySelect ? granularitySelect.value : "weekly",
      };

      const start = await startAsyncAnalysis(payload);
      const jobId = start.job_id;

      let data = null;
      while (true) {
        const status = await fetchJobStatus(jobId);
        const pct = typeof status.progress === "number" ? status.progress : 0;
        const msg = status.message || "";
        const fill = document.getElementById("analysis-progress-fill");
        const text = document.getElementById("analysis-progress-text");
        if (fill) fill.style.width = `${pct}%`;
        if (text) text.textContent = `${pct}/100${msg ? " - " + msg : ""}`;
        if (status.status === "done") {
          data = status.result;
          break;
        }
        if (status.status === "error") {
          throw new Error(status.error || "Analysis failed");
        }
        await new Promise(function (resolve) {
          setTimeout(resolve, 500);
        });
      }

      showPanel("results-content");
      const runBbox =
        data.geojson && data.geojson.bbox ? data.geojson.bbox : bbox;
      displayAnalysisData(data, runBbox);
      overlayCtrl.setOverlay(data.run_id, runBbox);
    } catch (err) {
      resultsErrorText.textContent =
        "Analysis execution failed: " + err.message;
      showPanel("results-error");
    } finally {
      // keep current panel
    }
  });

  function bboxFromGeometry(geom) {
    if (!geom || !geom.coordinates) return getBbox();
    let minLng = Infinity;
    let minLat = Infinity;
    let maxLng = -Infinity;
    let maxLat = -Infinity;
    function walk(coords) {
      if (Array.isArray(coords) && typeof coords[0] === "number") {
        const lng = coords[0];
        const lat = coords[1];
        if (lng < minLng) minLng = lng;
        if (lat < minLat) minLat = lat;
        if (lng > maxLng) maxLng = lng;
        if (lat > maxLat) maxLat = lat;
      } else if (Array.isArray(coords)) {
        coords.forEach(walk);
      }
    }
    walk(geom.coordinates);
    if (!isFinite(minLng)) return getBbox();
    return [
      Number(minLng.toFixed(4)),
      Number(minLat.toFixed(4)),
      Number(maxLng.toFixed(4)),
      Number(maxLat.toFixed(4)),
    ];
  }

  btnInspectScenes.addEventListener("click", async function () {
    const originalText = btnInspectScenes.textContent;
    btnInspectScenes.textContent = "Scanning STAC...";
    btnInspectScenes.disabled = true;

    const inspectBbox = bboxFromGeometry(getActiveGeometry());

    try {
      const data = await fetchAoiScenes(inspectBbox);
      const s2 = data.optical_scenes || [];
      const s1 = data.sar_scenes || [];
      if (inspectPanel) {
        inspectPanel.innerHTML = "";
        const head = document.createElement("div");
        head.textContent = `Found ${s2.length} Sentinel-2 and ${s1.length} Sentinel-1 passes`;
        head.style.fontWeight = "600";
        inspectPanel.appendChild(head);

        if (s2.length) {
          const sub = document.createElement("div");
          sub.textContent = "Sentinel-2:";
          sub.style.marginTop = "0.35rem";
          inspectPanel.appendChild(sub);
          s2.forEach(function (scene) {
            const line = document.createElement("div");
            line.style.fontSize = "0.75rem";
            line.style.color = "#a0a0a0";
            const dt = scene.datetime ? scene.datetime.substring(0, 10) : "-";
            const cc =
              typeof scene.cloud_cover === "number"
                ? ` (cloud ${scene.cloud_cover.toFixed(1)}%)`
                : "";
            line.textContent = `${scene.id} - ${dt}${cc}`;
            inspectPanel.appendChild(line);
          });
        }

        if (s1.length) {
          const sub = document.createElement("div");
          sub.textContent = "Sentinel-1:";
          sub.style.marginTop = "0.35rem";
          inspectPanel.appendChild(sub);
          s1.forEach(function (scene) {
            const line = document.createElement("div");
            line.style.fontSize = "0.75rem";
            line.style.color = "#a0a0a0";
            const dt = scene.datetime ? scene.datetime.substring(0, 10) : "-";
            line.textContent = `${scene.id} - ${dt}`;
            inspectPanel.appendChild(line);
          });
        }
      }
      showPanel("inspect-panel");
    } catch (err) {
      if (inspectPanel) {
        inspectPanel.textContent = "Pass inspection failed: " + err.message;
      }
      showPanel("inspect-panel");
    } finally {
      btnInspectScenes.textContent = originalText;
      btnInspectScenes.disabled = false;
    }
  });

  const OBJECTIVE_LABELS = {
    peat_moisture: "1. Peatland Moisture and Extent (S1 + S2)",
    topography_slope: "2. Peat Topography and Slope (Copernicus DEM)",
    forest_to_bare: "3. Forest to Bare Land (Deforestation)",
    forest_to_mining: "4. Forest to Mining Excavation",
    forest_to_palm: "5. Forest to Oil Palm Plantation",
    deforest_expansion: "6. Deforestation Expansion Tracking",
    reclamation: "7. Deforestation Reclamation Monitoring",
    bare_to_veg: "8. Bare Land to Vegetation Succession",
    wildfire_dnbr: "9. Wildfire Susceptibility and Burn Severity (dNBR)",
    water_dynamics: "10. Water Dynamics and Peat Canals (MNDWI)",
    peat_drainage_canal: "11. Peatland Drainage & Canal Density",
    carbon_subsidence: "12. Carbon Emission & Subsidence Risk",
    coastal_inundation: "13. Coastal Inundation / Flood Risk",
    landslide_susceptibility: "14. Landslide Susceptibility",
    ground_deformation: "15. Ground Deformation (InSAR proxy)",
    urban_expansion: "16. Built-up / Urban Expansion",
    cropland_expansion: "17. Cropland Expansion",
    peat_restoration: "18. Peatland Restoration Success",
    seasonal_flooding: "19. Seasonal Flooding Dynamics",
    biodiversity_habitat: "20. Biodiversity / Habitat Degradation",
  };

  const layerState = {};

  async function runObjectiveLayer(key) {
    const geom = getActiveGeometry();
    if (!geom) {
      alert("Draw AOI first.");
      return false;
    }
    const bbox = getBbox();
    const dateStart =
      document.getElementById("date-start").value || "2024-01-01";
    const dateEnd = document.getElementById("date-end").value || "2024-12-31";
    const dataSourceSelect = document.getElementById("data-source-select");
    const granularitySelect = document.getElementById("granularity-select");
    const payload = {
      aoi: geom,
      target: key,
      pre_date_range: "2023-01-01/2023-12-31",
      post_date_range: dateStart + "/" + dateEnd,
      data_source: dataSourceSelect
        ? dataSourceSelect.value
        : "planetary_computer",
      granularity: granularitySelect ? granularitySelect.value : "weekly",
    };

    const start = await startAsyncAnalysis(payload);
    const jobId = start.job_id;
    let data = null;
    while (true) {
      const status = await fetchJobStatus(jobId);
      if (status.status === "done") {
        data = status.result;
        break;
      }
      if (status.status === "error") {
        throw new Error(status.error || "Analysis failed");
      }
      await new Promise(function (resolve) {
        setTimeout(resolve, 500);
      });
    }

    const runBbox =
      data.geojson && data.geojson.bbox ? data.geojson.bbox : bbox;
    const sourceId = "layer-src-" + key;
    const layerId = "layer-" + key;
    if (map.getSource(sourceId)) map.removeSource(sourceId);
    if (map.getLayer(layerId)) map.removeLayer(layerId);
    map.addSource(sourceId, {
      type: "image",
      url: "/api/analysis/" + data.run_id + "/overlay.png?period=post",
      coordinates: [
        [runBbox[0], runBbox[3]],
        [runBbox[2], runBbox[3]],
        [runBbox[2], runBbox[1]],
        [runBbox[0], runBbox[1]],
      ],
    });
    map.addLayer({
      id: layerId,
      type: "raster",
      source: sourceId,
      paint: { "raster-opacity": 0.65 },
    });

    layerState[key] = {
      checked: true,
      runId: data.run_id,
      sourceId: sourceId,
      layerId: layerId,
    };
    return true;
  }

  function removeObjectiveLayer(key) {
    const st = layerState[key];
    if (!st) return;
    if (map.getLayer(st.layerId)) map.removeLayer(st.layerId);
    if (map.getSource(st.sourceId)) map.removeSource(st.sourceId);
    st.checked = false;
  }

  function renderLayerList() {
    const container = document.getElementById("layer-list");
    if (!container) return;
    container.innerHTML = "";
    Object.keys(OBJECTIVE_LABELS).forEach(function (key) {
      const row = document.createElement("div");
      row.style.display = "flex";
      row.style.alignItems = "center";
      row.style.gap = "0.4rem";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = key;
      cb.checked = true;

      const label = document.createElement("span");
      label.textContent = OBJECTIVE_LABELS[key];
      label.style.fontSize = "0.8rem";

      const info = document.createElement("div");
      info.style.fontSize = "0.7rem";
      info.style.color = "#7a7a7a";
      info.style.marginLeft = "1.6rem";
      info.textContent = "Overlay layer (NDVI/BSI composite)";

      cb.addEventListener("change", async function () {
        cb.disabled = true;
        try {
          if (cb.checked) {
            const ok = await runObjectiveLayer(key);
            if (!ok) cb.checked = false;
          } else {
            removeObjectiveLayer(key);
          }
        } catch (err) {
          cb.checked = false;
          alert("Layer failed: " + err.message);
        } finally {
          cb.disabled = false;
          if (layerState[key]) layerState[key].checked = cb.checked;
        }
      });

      row.appendChild(cb);
      row.appendChild(label);
      container.appendChild(row);
      container.appendChild(info);
    });
  }

  function loadFirmsForAoi() {
    const geom = getActiveGeometry();
    if (!geom) return;
    const bbox = getBbox();
    const end = new Date().toISOString().substring(0, 10);
    const start = new Date(Date.now() - 30 * 86400000)
      .toISOString()
      .substring(0, 10);
    fetch("/api/insights/fires", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bbox: bbox, start_date: start, end_date: end }),
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        const panel = document.getElementById("firms-panel");
        if (!panel) return;
        if (data.count > 0) {
          panel.innerHTML =
            "<strong>FIRMS: " +
            data.count +
            " active fire hotspots in AOI (last 30 days)</strong>";
          panel.style.color = "#e03e3e";
        } else {
          panel.innerHTML =
            "FIRMS: No active fire hotspots in AOI (last 30 days)";
          panel.style.color = "#4a4a4a";
        }
      })
      .catch(function (err) {
        const panel = document.getElementById("firms-panel");
        if (panel) panel.textContent = "FIRMS: Error - " + err.message;
      });
  }

  async function runAllObjectives() {
    const keys = Object.keys(OBJECTIVE_LABELS);
    for (const key of keys) {
      const cb =
        document.querySelector(
          "#layer-list input[type=checkbox][value=" + key + "]",
        ) || document.querySelector("#layer-list input[type=checkbox]");
      if (cb) cb.checked = true;
      await runObjectiveLayer(key);
    }
  }

  const origAnalyze =
    window.analyzeClick || document.getElementById("btn-run-analysis")?.onclick;
  document
    .getElementById("btn-run-analysis")
    .addEventListener("click", async function () {
      if (origAnalyze) origAnalyze.call(this);
      await runAllObjectives();
      loadFirmsForAoi();
    });

  renderLayerList();
})();
