function createInsightsController(map, getBbox, getRunId, getDateRange) {
  const $ = function (id) {
    return document.getElementById(id);
  };

  const CLASS_COLORS_MAP = {
    1: "#1e7e34",
    2: "#17a2b8",
    3: "#d39e00",
    4: "#28a745",
    5: "#6c757d",
    6: "#007bff",
    7: "#dc3545",
    8: "#8fd19e",
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
    if (!box) return;
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
        '<p class="results-state-desc" style="font-size:0.75rem;">No land class conversion detected.</p>';
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

  function renderTimeSeries(series) {
    const box = $("timeseries-chart");
    if (!box) return;
    if (!series || !series.length) {
      box.innerHTML =
        '<p class="results-state-desc" style="font-size:0.75rem;">No temporal series data available.</p>';
      return;
    }
    const w = 340;
    const h = 120;
    const padL = 26;
    const padR = 10;
    const padT = 12;
    const padB = 22;
    const pw = w - padL - padR;
    const ph = h - padT - padB;

    let vmin = -0.2;
    let vmax = 1.0;
    const xStep = series.length > 1 ? pw / (series.length - 1) : pw;

    function toCoord(val, idx) {
      const x = padL + idx * xStep;
      const y = padT + (1 - (val - vmin) / (vmax - vmin)) * ph;
      return `${x.toFixed(1)},${Math.max(padT, Math.min(padT + ph, y)).toFixed(1)}`;
    }

    const ndviPts = series.map((s, i) => toCoord(s.ndvi, i)).join(" ");
    const ndwiPts = series.map((s, i) => toCoord(s.ndwi, i)).join(" ");
    const ndmiPts = series.map((s, i) => toCoord(s.ndmi, i)).join(" ");

    const dStart = (series[0].period || "").substring(5);
    const dEnd = (series[series.length - 1].period || "").substring(5);

    box.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto;display:block;">
        <rect width="${w}" height="${h}" fill="#0d0d0d" rx="2" />
        <line x1="${padL}" y1="${padT}" x2="${w - padR}" y2="${padT}" stroke="#222" stroke-width="1" />
        <line x1="${padL}" y1="${padT + ph / 2}" x2="${w - padR}" y2="${padT + ph / 2}" stroke="#222" stroke-width="1" />
        <line x1="${padL}" y1="${padT + ph}" x2="${w - padR}" y2="${padT + ph}" stroke="#333" stroke-width="1" />
        <polyline points="${ndviPts}" fill="none" stroke="#7fb069" stroke-width="1.8" />
        <polyline points="${ndwiPts}" fill="none" stroke="#4aa3df" stroke-width="1.5" />
        <polyline points="${ndmiPts}" fill="none" stroke="#e0c341" stroke-width="1.5" stroke-dasharray="3,2" />
        <text x="${padL}" y="${h - 6}" fill="#777" font-size="9">${dStart}</text>
        <text x="${w - padR}" y="${h - 6}" fill="#777" font-size="9" text-anchor="end">${dEnd}</text>
        <circle cx="${w - 110}" cy="8" r="3" fill="#7fb069" />
        <text x="${w - 104}" y="11" fill="#bbb" font-size="8">NDVI</text>
        <circle cx="${w - 70}" cy="8" r="3" fill="#4aa3df" />
        <text x="${w - 64}" y="11" fill="#bbb" font-size="8">NDWI</text>
        <circle cx="${w - 32}" cy="8" r="3" fill="#e0c341" />
        <text x="${w - 26}" y="11" fill="#bbb" font-size="8">NDMI</text>
      </svg>
    `;
  }

  function renderClassScatter(scatter) {
    const box = $("scatter-chart");
    if (!box) return;
    if (!scatter || !scatter.length) {
      box.innerHTML =
        '<p class="results-state-desc" style="font-size:0.75rem;">No feature cluster samples available.</p>';
      return;
    }
    const w = 340;
    const h = 120;
    const padL = 26;
    const padR = 10;
    const padT = 10;
    const padB = 20;
    const pw = w - padL - padR;
    const ph = h - padT - padB;

    const bsiMin = -0.5;
    const bsiMax = 0.4;
    const ndviMin = -0.2;
    const ndviMax = 1.0;

    const circles = scatter
      .map(function (pt) {
        const x = padL + ((pt.bsi - bsiMin) / (bsiMax - bsiMin)) * pw;
        const y = padT + (1 - (pt.ndvi - ndviMin) / (ndviMax - ndviMin)) * ph;
        const clr = CLASS_COLORS_MAP[pt.class_code] || "#999999";
        const cx = Math.max(padL, Math.min(w - padR, x)).toFixed(1);
        const cy = Math.max(padT, Math.min(padT + ph, y)).toFixed(1);
        return `<circle cx="${cx}" cy="${cy}" r="3" fill="${clr}" opacity="0.8" />`;
      })
      .join("");

    box.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto;display:block;">
        <rect width="${w}" height="${h}" fill="#0d0d0d" rx="2" />
        <line x1="${padL}" y1="${padT + ph}" x2="${w - padR}" y2="${padT + ph}" stroke="#333" stroke-width="1" />
        <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + ph}" stroke="#333" stroke-width="1" />
        ${circles}
        <text x="${padL}" y="${h - 6}" fill="#777" font-size="9">BSI: -0.5</text>
        <text x="${w - padR}" y="${h - 6}" fill="#777" font-size="9" text-anchor="end">BSI: +0.4</text>
        <text x="4" y="${padT + 10}" fill="#777" font-size="9">1.0</text>
        <text x="4" y="${padT + ph}" fill="#777" font-size="9">0.0</text>
      </svg>
    `;
  }

  function renderModelAccuracy(accuracy) {
    const elBadge = $("val-accuracy-badge");
    const elOverall = $("val-overall-acc");
    const elKappa = $("val-kappa");
    const elSamples = $("val-samples");
    if (!accuracy) {
      if (elBadge) elBadge.textContent = "OA: -";
      if (elOverall) elOverall.textContent = "-";
      if (elKappa) elKappa.textContent = "-";
      if (elSamples) elSamples.textContent = "-";
      return;
    }
    const oaPct = (accuracy.overall_accuracy * 100).toFixed(1) + "%";
    const kappa = Number(accuracy.kappa || 0).toFixed(3);
    const samples = accuracy.samples || 0;
    if (elBadge)
      elBadge.textContent = `OA ${(accuracy.overall_accuracy * 100).toFixed(0)}% | \u03ba ${Number(accuracy.kappa || 0).toFixed(2)}`;
    if (elOverall) elOverall.textContent = oaPct;
    if (elKappa) elKappa.textContent = kappa;
    if (elSamples) elSamples.textContent = String(samples);
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
    renderTimeSeries: renderTimeSeries,
    renderClassScatter: renderClassScatter,
    renderModelAccuracy: renderModelAccuracy,
    refreshIntervention: updateIntervention,
  };
}
