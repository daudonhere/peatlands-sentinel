// MapLibre GL controller for Peatlands Sentinel
(function () {
  "use strict";

  const mapStyleOsm = {
    version: 8,
    sources: {
      "osm-tiles": {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: "&copy; OpenStreetMap contributors",
      },
    },
    layers: [
      {
        id: "osm-layer",
        type: "raster",
        source: "osm-tiles",
        minzoom: 0,
        maxzoom: 19,
      },
    ],
  };

  const map = new maplibregl.Map({
    container: "map",
    style: mapStyleOsm,
    center: [102.5, 0.5], // Sumatra peatlands default
    zoom: 8,
  });

  map.addControl(new maplibregl.NavigationControl(), "top-right");

  const bboxDisplay = document.getElementById("bbox-display");
  const btnFetchScenes = document.getElementById("btn-fetch-scenes");
  const btnRunAnalyst = document.getElementById("btn-run-analyst");

  function getRoundedBbox() {
    const bounds = map.getBounds();
    return [
      Number(bounds.getWest().toFixed(4)),
      Number(bounds.getSouth().toFixed(4)),
      Number(bounds.getEast().toFixed(4)),
      Number(bounds.getNorth().toFixed(4)),
    ];
  }

  function updateBboxDisplay() {
    const bbox = getRoundedBbox();
    bboxDisplay.textContent = `[${bbox.join(", ")}]`;
  }

  map.on("moveend", updateBboxDisplay);
  map.on("load", updateBboxDisplay);

  // Basemap switcher
  document.querySelectorAll('input[name="basemap"]').forEach(function (radio) {
    radio.addEventListener("change", function (e) {
      const mode = e.target.value;
      if (mode === "satellite") {
        // ESRI World Imagery public tile
        map.setStyle({
          version: 8,
          sources: {
            "esri-sat": {
              type: "raster",
              tiles: [
                "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
              ],
              tileSize: 256,
              attribution: "&copy; Esri, Maxar, Earthstar Geographics",
            },
          },
          layers: [{ id: "sat-layer", type: "raster", source: "esri-sat" }],
        });
      } else {
        map.setStyle(mapStyleOsm);
      }
    });
  });

  // Scene discovery via Planetary Computer STAC
  btnFetchScenes.addEventListener("click", async function () {
    const scenesLoading = document.getElementById("scenes-loading");
    const scenesEmpty = document.getElementById("scenes-empty");
    const scenesList = document.getElementById("scenes-list");

    scenesEmpty.classList.add("hidden");
    scenesList.classList.add("hidden");
    scenesLoading.classList.remove("hidden");

    try {
      const response = await fetch("/api/peatlands/scenes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bbox: getRoundedBbox(),
          datetime_range: "2024-01-01/2024-12-31",
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();
      scenesList.innerHTML = "";

      const optical = data.optical_scenes || [];
      const sar = data.sar_scenes || [];
      const totalScenes = optical.length + sar.length;

      if (totalScenes === 0) {
        scenesEmpty.classList.remove("hidden");
        scenesEmpty.textContent =
          "No recent scenes found for this bounding box.";
        return;
      }

      optical.forEach(function (item) {
        const li = document.createElement("li");
        li.className = "scene-item";
        li.innerHTML = `
          <div class="scene-item-title">S2: ${item.id}</div>
          <div class="scene-item-meta">Date: ${item.datetime ? item.datetime.split("T")[0] : "N/A"} | Cloud: ${item.cloud_cover !== null ? item.cloud_cover.toFixed(1) + "%" : "N/A"}</div>
        `;
        scenesList.appendChild(li);
      });

      sar.forEach(function (item) {
        const li = document.createElement("li");
        li.className = "scene-item";
        li.innerHTML = `
          <div class="scene-item-title">S1: ${item.id}</div>
          <div class="scene-item-meta">Date: ${item.datetime ? item.datetime.split("T")[0] : "N/A"} | Pol: ${(item.polarizations || []).join(", ")}</div>
        `;
        scenesList.appendChild(li);
      });

      scenesList.classList.remove("hidden");
    } catch (err) {
      scenesEmpty.classList.remove("hidden");
      scenesEmpty.textContent = "Failed to fetch scenes: " + err.message;
    } finally {
      scenesLoading.classList.add("hidden");
    }
  });

  // AI Analyst Assessment
  btnRunAnalyst.addEventListener("click", async function () {
    const stateEmpty = document.getElementById("analyst-state-empty");
    const stateLoading = document.getElementById("analyst-state-loading");
    const stateResult = document.getElementById("analyst-state-result");
    const stateError = document.getElementById("analyst-state-error");
    const errorMsg = document.getElementById("analyst-error-msg");

    stateEmpty.classList.add("hidden");
    stateResult.classList.add("hidden");
    stateError.classList.add("hidden");
    stateLoading.classList.remove("hidden");

    try {
      const response = await fetch("/api/peatlands/assess-risk");
      if (!response.ok) {
        throw new Error(`Analyst API returned status ${response.status}`);
      }

      const result = await response.json();

      const threatEl = document.getElementById("metric-threat");
      threatEl.textContent = result.threat_level;
      threatEl.className = "badge badge-" + result.threat_level.toLowerCase();

      document.getElementById("metric-moisture").textContent =
        result.peat_moisture_status;
      document.getElementById("metric-summary").textContent =
        result.fire_risk_summary;

      const actionsList = document.getElementById("metric-actions");
      actionsList.innerHTML = "";
      (result.recommended_actions || []).forEach(function (action) {
        const li = document.createElement("li");
        li.textContent = action;
        actionsList.appendChild(li);
      });

      stateResult.classList.remove("hidden");
    } catch (err) {
      errorMsg.textContent = err.message;
      stateError.classList.remove("hidden");
    } finally {
      stateLoading.classList.add("hidden");
    }
  });
})();
