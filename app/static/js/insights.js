function createInsightsController(map, getBbox, getRunId, getDateRange) {
  const $ = function (id) {
    return document.getElementById(id);
  };

  function withBusy(btn, label, task) {
    const original = btn.textContent;
    btn.textContent = label;
    btn.disabled = true;
    return task().finally(function () {
      btn.textContent = original;
      btn.disabled = false;
    });
  }

  function renderTransitions(transitions) {
    const box = $("transition-chart");
    box.innerHTML = "";
    const top = (transitions || [])
      .filter(function (t) {
        return t.from_class !== t.to_class;
      })
      .sort(function (a, b) {
        return b.area_hectares - a.area_hectares;
      })
      .slice(0, 6);
    if (!top.length) {
      box.innerHTML =
        '<p class="results-state-desc">No land class conversion detected.</p>';
      return;
    }
    const max = top[0].area_hectares || 1;
    top.forEach(function (t) {
      const row = document.createElement("div");
      row.className = "bar-row";
      const label = document.createElement("span");
      label.className = "bar-label";
      label.textContent = `${t.from_class} to ${t.to_class}`;
      const track = document.createElement("div");
      track.className = "bar-track";
      const fill = document.createElement("div");
      fill.className = "bar-fill";
      fill.style.width = `${Math.max(4, (t.area_hectares / max) * 100)}%`;
      const value = document.createElement("span");
      value.className = "bar-value";
      value.textContent = `${t.area_hectares.toFixed(1)} Ha`;
      track.appendChild(fill);
      row.append(label, track, value);
      box.appendChild(row);
    });
  }

  function showFires(fires) {
    const geojson = {
      type: "FeatureCollection",
      features: fires.map(function (f) {
        return {
          type: "Feature",
          properties: { frp: f.frp },
          geometry: { type: "Point", coordinates: [f.longitude, f.latitude] },
        };
      }),
    };
    if (map.getSource("fires")) {
      map.getSource("fires").setData(geojson);
      return;
    }
    map.addSource("fires", { type: "geojson", data: geojson });
    map.addLayer({
      id: "fires-layer",
      type: "circle",
      source: "fires",
      paint: {
        "circle-radius": 6,
        "circle-color": "#f43f5e",
        "circle-stroke-color": "#fff",
        "circle-stroke-width": 1.5,
      },
    });
  }

  $("btn-fires").addEventListener("click", function () {
    const status = $("insight-status");
    withBusy($("btn-fires"), "Querying FIRMS...", async function () {
      try {
        const data = await fetchActiveFires(getBbox(), 3);
        showFires(data.fires);
        status.textContent = `${data.count} VIIRS hotspots in last 3 days`;
      } catch (err) {
        status.textContent = err.message;
      }
    });
  });

  $("btn-live-ndvi").addEventListener("click", function () {
    const status = $("insight-status");
    withBusy($("btn-live-ndvi"), "Reading COG...", async function () {
      try {
        const d = await fetchLiveNdvi(getBbox(), getDateRange());
        const dt = d.datetime ? d.datetime.substring(0, 10) : "-";
        const clear = Math.round((d.valid_pixel_ratio || 0) * 100);
        status.textContent = `Live NDVI ${d.mean_ndvi} (${dt}, ${clear}% clear)`;
      } catch (err) {
        status.textContent = err.message;
      }
    });
  });

  const slider = $("dams-slider");
  async function updateIntervention() {
    const runId = getRunId();
    $("dams-label").textContent = `${slider.value} dams / 100 Ha`;
    if (!runId) {
      $("intervention-result").textContent =
        "Run analysis first to simulate canal blocking.";
      return;
    }
    try {
      const r = await fetchIntervention(runId, slider.value);
      $("intervention-result").textContent =
        `WTD ${(r.wtd_before_m * 100).toFixed(0)} to ${(r.wtd_after_m * 100).toFixed(0)} cm | ` +
        `${r.emission_reduction_tco2e_year} tCO2e/yr | ${r.total_dams} dams | ` +
        (r.meets_safe_threshold ? "meets -40 cm" : "below -40 cm");
    } catch (err) {
      $("intervention-result").textContent = err.message;
    }
  }
  slider.addEventListener("input", updateIntervention);
  slider.addEventListener("change", updateIntervention);

  return {
    renderTransitions: renderTransitions,
    refreshIntervention: updateIntervention,
  };
}
