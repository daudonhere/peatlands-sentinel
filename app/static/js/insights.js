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
    const nbrPts = series.map((s, i) => toCoord(s.nbr || 0, i)).join(" ");
    const bsiPts = series.map((s, i) => toCoord(s.bsi || 0, i)).join(" ");

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
        <polyline points="${nbrPts}" fill="none" stroke="#dc3545" stroke-width="1.5" />
        <polyline points="${bsiPts}" fill="none" stroke="#8fd19e" stroke-width="1.5" stroke-dasharray="4,2" />
        <text x="${padL}" y="${h - 6}" fill="#777" font-size="9">${dStart}</text>
        <text x="${w - padR}" y="${h - 6}" fill="#777" font-size="9" text-anchor="end">${dEnd}</text>
        <circle cx="${w - 110}" cy="8" r="3" fill="#7fb069" />
        <text x="${w - 104}" y="11" fill="#bbb" font-size="8">NDVI</text>
        <circle cx="${w - 70}" cy="8" r="3" fill="#4aa3df" />
        <text x="${w - 64}" y="11" fill="#bbb" font-size="8">NDWI</text>
        <circle cx="${w - 32}" cy="8" r="3" fill="#e0c341" />
        <text x="${w - 26}" y="11" fill="#bbb" font-size="8">NDMI</text>
        <circle cx="${w - 110}" cy="18" r="3" fill="#dc3545" />
        <text x="${w - 104}" y="21" fill="#bbb" font-size="8">NBR</text>
        <circle cx="${w - 70}" cy="18" r="3" fill="#8fd19e" />
        <text x="${w - 64}" y="21" fill="#bbb" font-size="8">BSI</text>
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
    // Multi-scatter: NDVI vs BSI, NDWI vs NBR, NDMI vs SAR (pre + post per class)
    const pairs = [
      { xKey: "bsi", yKey: "ndvi", xLabel: "BSI", yLabel: "NDVI" },
      { xKey: "nbr", yKey: "ndwi", xLabel: "NBR", yLabel: "NDWI" },
      { xKey: "bsi", yKey: "ndmi", xLabel: "BSI", yLabel: "NDMI" },
    ];
    const pw = 100;
    const ph = 90;
    const pad = 18;
    const cw = pw + pad * 2;
    const ch = ph + pad * 2;
    const cols = 3;
    const totalW = cw * cols;
    const totalH = ch;

    function toX(val, min, max) {
      return pad + ((val - min) / (max - min)) * pw;
    }
    function toY(val, min, max) {
      return pad + (1 - (val - min) / (max - min)) * ph;
    }

    const ranges = {
      ndvi: [-0.3, 1.0],
      ndwi: [-0.8, 0.5],
      ndmi: [-0.2, 0.6],
      bsi: [-0.6, 0.5],
      nbr: [-0.3, 0.8],
      sar: [-25, -5],
    };

    let svg = `<svg viewBox="0 0 ${totalW} ${totalH}" style="width:100%;height:auto;display:block;">`;
    svg += `<rect width="${totalW}" height="${totalH}" fill="#0d0d0d" rx="2" />`;

    pairs.forEach(function (pair, pi) {
      const ox = pi * cw;
      const xRange = ranges[pair.xKey];
      const yRange = ranges[pair.yKey];

      // Axes
      svg += `<line x1="${ox + pad}" y1="${pad + ph}" x2="${ox + pad + pw}" y2="${pad + ph}" stroke="#333" stroke-width="1" />`;
      svg += `<line x1="${ox + pad}" y1="${pad}" x2="${ox + pad}" y2="${pad + ph}" stroke="#333" stroke-width="1" />`;
      svg += `<text x="${ox + pad + pw / 2}" y="${pad + ph + 12}" fill="#777" font-size="7" text-anchor="middle">${pair.xLabel}</text>`;
      svg += `<text x="${ox + 4}" y="${pad + ph / 2}" fill="#777" font-size="7" text-anchor="middle" transform="rotate(-90, ${ox + 4}, ${pad + ph / 2})">${pair.yLabel}</text>`;

      scatter.forEach(function (pt) {
        const clr = CLASS_COLORS_MAP[pt.class_code] || "#999999";
        // Pre point (hollow)
        const preX = toX(pt["pre_" + pair.xKey] || 0, xRange[0], xRange[1]);
        const preY = toY(pt["pre_" + pair.yKey] || 0, yRange[0], yRange[1]);
        svg += `<circle cx="${(ox + preX).toFixed(1)}" cy="${preY.toFixed(1)}" r="3" fill="none" stroke="${clr}" stroke-width="1.5" opacity="0.6" />`;
        // Post point (filled)
        const postX = toX(pt["post_" + pair.xKey] || 0, xRange[0], xRange[1]);
        const postY = toY(pt["post_" + pair.yKey] || 0, yRange[0], yRange[1]);
        svg += `<circle cx="${(ox + postX).toFixed(1)}" cy="${postY.toFixed(1)}" r="3" fill="${clr}" opacity="0.9" />`;
        // Arrow from pre to post
        svg += `<line x1="${(ox + preX).toFixed(1)}" y1="${preY.toFixed(1)}" x2="${(ox + postX).toFixed(1)}" y2="${postY.toFixed(1)}" stroke="${clr}" stroke-width="0.5" opacity="0.4" />`;
      });
    });

    // Legend
    let ly = totalH - 4;
    scatter.forEach(function (pt) {
      const clr = CLASS_COLORS_MAP[pt.class_code] || "#999999";
      // handled below
    });
    // Class legend
    let lx = 4;
    scatter.forEach(function (pt) {
      const clr = CLASS_COLORS_MAP[pt.class_code] || "#999999";
      svg += `<circle cx="${lx + 3}" cy="${totalH - 6}" r="3" fill="${clr}" />`;
      svg += `<text x="${lx + 8}" y="${totalH - 3}" fill="#999" font-size="6">${pt.land_class.substring(0, 6)}</text>`;
      lx += 55;
    });

    svg += `</svg>`;
    box.innerHTML = svg;
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
    // Move fire layer to top
    try {
      map.moveLayer("fires-layer");
    } catch (e) {}
  }

  $("btn-fires").addEventListener("click", function () {
    const status = $("insight-status");
    const confFilter = $("firms-confidence");
    const conf = confFilter ? confFilter.value : "all";
    const archiveEl = $("firms-archive");
    const archive = archiveEl ? archiveEl.checked : false;
    withBusy($("btn-fires"), "Querying FIRMS...", async function () {
      try {
        const data = await fetchActiveFires(getBbox(), 5, archive);
        let fires = data.fires || [];
        if (conf !== "all") {
          fires = fires.filter(function (f) {
            return f.confidence === conf || f.confidence === "h";
          });
        }
        showFires(fires);
        status.textContent = `${fires.length} hotspots (conf: ${conf}, ${archive ? "archive" : "NRT"})`;
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
    showFires: showFires,
  };
}
