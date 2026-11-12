// Peatlands Sentinel - MapLibre Single-Page Interactive Controller
(function () {
  "use strict";

  // Location Presets
  const PRESETS = {
    riau: {
      center: [102.5, 0.5],
      zoom: 9,
      name: "Riau Peat Dome (Sumatra)",
      indices: { ndvi: 0.68, ndwi: 0.22, dnbr: 0.03, sar: "-6.2 dB" },
    },
    pulang_pisau: {
      center: [114.25, -2.75],
      zoom: 9.5,
      name: "Pulang Pisau Ex-PLG (Central Kalimantan)",
      indices: { ndvi: 0.35, ndwi: -0.15, dnbr: 0.42, sar: "-11.8 dB" },
    },
    musirawas: {
      center: [103.8, -2.4],
      zoom: 9,
      name: "Musi Banyuasin (South Sumatra)",
      indices: { ndvi: 0.48, ndwi: 0.05, dnbr: 0.12, sar: "-8.4 dB" },
    },
  };

  const styleDark = {
    version: 8,
    sources: {
      "carto-dark": {
        type: "raster",
        tiles: [
          "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
          "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
          "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        ],
        tileSize: 256,
        attribution: "&copy; OpenStreetMap contributors, &copy; CARTO",
      },
    },
    layers: [
      {
        id: "carto-dark-layer",
        type: "raster",
        source: "carto-dark",
        minzoom: 0,
        maxzoom: 20,
      },
    ],
  };

  const styleSatellite = {
    version: 8,
    sources: {
      "esri-imagery": {
        type: "raster",
        tiles: [
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        ],
        tileSize: 256,
        attribution: "&copy; Esri, Maxar, Earthstar Geographics",
      },
    },
    layers: [
      {
        id: "esri-imagery-layer",
        type: "raster",
        source: "esri-imagery",
        minzoom: 0,
        maxzoom: 19,
      },
    ],
  };

  // Map Initialization
  const map = new maplibregl.Map({
    container: "map",
    style: styleDark,
    center: [102.5, 0.5],
    zoom: 9,
  });

  map.addControl(
    new maplibregl.NavigationControl({ showCompass: true }),
    "top-right",
  );

  // DOM Elements
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
    const bbox = getBbox();
    coordsText.textContent = `[${bbox.join(", ")}]`;
  }

  map.on("moveend", updateCoords);
  map.on("load", function () {
    updateCoords();
    renderAoiPolygon(getBbox(), "#10b981");
  });

  // Dock Collapse Toggle
  dockToggleBtn.addEventListener("click", function () {
    const isCollapsed = dockBody.classList.toggle("collapsed");
    dockToggleBtn.innerHTML = isCollapsed ? "+" : "&minus;";
    dockToggleBtn.setAttribute("aria-expanded", String(!isCollapsed));
  });

  // Results Panel Close
  resultsCloseBtn.addEventListener("click", function () {
    resultsCard.classList.add("hidden");
  });

  // Basemap Switcher
  document
    .querySelectorAll('input[name="basemap-choice"]')
    .forEach(function (radio) {
      radio.addEventListener("change", function (e) {
        if (e.target.value === "satellite") {
          map.setStyle(styleSatellite);
        } else {
          map.setStyle(styleDark);
        }
      });
    });

  // Preset Location Selector
  aoiPresetSelect.addEventListener("change", function (e) {
    const key = e.target.value;
    if (key in PRESETS) {
      const preset = PRESETS[key];
      map.flyTo({ center: preset.center, zoom: preset.zoom, essential: true });
      aoiStatusText.textContent = `AOI: ${preset.name}`;
    } else {
      aoiStatusText.textContent = "AOI: Custom Viewport";
    }
  });

  // AOI Layer Overlay
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

  // Run Satellite Analysis
  btnRunAnalysis.addEventListener("click", async function () {
    resultsCard.classList.remove("hidden");
    resultsEmpty.classList.add("hidden");
    resultsContent.classList.add("hidden");
    resultsError.classList.add("hidden");
    resultsLoading.classList.remove("hidden");

    const selectedTargetKey = analysisTargetSelect.value;
    const selectedTargetText =
      analysisTargetSelect.options[analysisTargetSelect.selectedIndex].text;
    const presetKey = aoiPresetSelect.value;
    const defaultIndices = (PRESETS[presetKey] &&
      PRESETS[presetKey].indices) || {
      ndvi: 0.52,
      ndwi: 0.08,
      dnbr: 0.15,
      sar: "-7.8 dB",
    };

    resultsTargetLabel.textContent =
      selectedTargetText.split(". ")[1] || selectedTargetText;
    resultsHeading.textContent = "Telemetry & AI Diagnostic";

    try {
      const url = `/api/peatlands/assess-risk?ndvi=${defaultIndices.ndvi}&ndwi=${defaultIndices.ndwi}&dnbr=${defaultIndices.dnbr}`;
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`API returned HTTP ${response.status}`);
      }
      const data = await response.json();

      valNdvi.textContent = defaultIndices.ndvi.toFixed(2);
      valNdwi.textContent = defaultIndices.ndwi.toFixed(2);
      valDnbr.textContent = defaultIndices.dnbr.toFixed(2);
      valSar.textContent = defaultIndices.sar;

      statusHeadline.textContent = `Threat Status: ${data.threat_level}`;
      statusSubline.textContent = `Moisture Condition: ${data.peat_moisture_status}`;

      let boundaryColor = "#10b981";
      if (data.threat_level === "Critical" || data.threat_level === "High") {
        boundaryColor = "#f43f5e";
        statusBanner.style.backgroundColor = "rgba(244, 63, 94, 0.15)";
        statusBanner.style.borderColor = "rgba(244, 63, 94, 0.4)";
        statusHeadline.style.color = "#fca5a5";
      } else if (data.threat_level === "Moderate") {
        boundaryColor = "#f59e0b";
        statusBanner.style.backgroundColor = "rgba(245, 158, 11, 0.15)";
        statusBanner.style.borderColor = "rgba(245, 158, 11, 0.4)";
        statusHeadline.style.color = "#fde68a";
      } else {
        statusBanner.style.backgroundColor = "rgba(16, 185, 129, 0.15)";
        statusBanner.style.borderColor = "rgba(16, 185, 129, 0.4)";
        statusHeadline.style.color = "#6ee7b7";
      }

      renderAoiPolygon(getBbox(), boundaryColor);

      analystSummary.textContent = data.fire_risk_summary;
      analystActions.innerHTML = "";
      (data.recommended_actions || []).forEach(function (action) {
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

  // Inspect Scenes Button
  btnInspectScenes.addEventListener("click", async function () {
    const originalText = btnInspectScenes.textContent;
    btnInspectScenes.textContent = "Scanning STAC...";
    btnInspectScenes.disabled = true;

    try {
      const response = await fetch("/api/peatlands/scenes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bbox: getBbox(),
          datetime_range: "2024-01-01/2024-12-31",
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
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
