function createInsightsController(map, getBbox, getRunId, getDateRange) {
  const $ = function (id) {
    return document.getElementById(id);
  };

  const CLASS_COLORS_MAP = {
    0: "#1a5f2a",
    1: "#3f7f5f",
    2: "#b08968",
    3: "#7fb069",
    4: "#6b6b6b",
    5: "#1f5f8b",
    6: "#d62728",
    7: "#e0c341",
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
    const h = 132;
    const padL = 26;
    const padR = 10;
    const padT = 28;
    const padB = 22;
    const pw = w - padL - padR;
    const ph = h - padT - padB;

    const KEYS = [
      { key: "ndvi", color: "#7fb069", label: "NDVI", dash: "" },
      { key: "ndwi", color: "#4aa3df", label: "NDWI", dash: "" },
      { key: "ndmi", color: "#e0c341", label: "NDMI", dash: "3,2" },
      { key: "mndwi", color: "#17a2b8", label: "MNDWI", dash: "2,2" },
      { key: "nbr", color: "#dc3545", label: "NBR", dash: "" },
      { key: "bsi", color: "#8fd19e", label: "BSI", dash: "4,2" },
    ];

    const allValues = [];
    series.forEach(function (s) {
      KEYS.forEach(function (k) {
        const v = Number(s[k.key]);
        if (Number.isFinite(v)) allValues.push(v);
      });
    });
    let vmin = Math.min(-0.2, ...allValues);
    let vmax = Math.max(0.2, ...allValues);
    if (vmax - vmin < 0.2) {
      vmin -= 0.1;
      vmax += 0.1;
    }
    const padSpan = (vmax - vmin) * 0.08;
    vmin -= padSpan;
    vmax += padSpan;
    const xStep = series.length > 1 ? pw / (series.length - 1) : pw;

    function toX(idx) {
      return padL + idx * xStep;
    }
    function toY(val) {
      return padT + (1 - (val - vmin) / (vmax - vmin)) * ph;
    }
    function toCoord(val, idx) {
      return `${toX(idx).toFixed(1)},${toY(val).toFixed(1)}`;
    }

    let grid = "";
    let ticks = "";
    const tickCount = 4;
    for (let i = 0; i <= tickCount; i += 1) {
      const value = vmax - ((vmax - vmin) * i) / tickCount;
      const y = toY(value);
      grid += `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${w - padR}" y2="${y.toFixed(1)}" stroke="#222" stroke-width="1" />`;
      ticks += `<text x="${padL - 3}" y="${(y + 3).toFixed(1)}" fill="#777" font-size="7" text-anchor="end">${value.toFixed(2)}</text>`;
    }

    let lines = "";
    let points = "";
    let legend = "";
    KEYS.forEach(function (k, ki) {
      const coords = series.map(function (s, i) {
        return toCoord(Number(s[k.key] || 0), i);
      });
      lines += `<polyline points="${coords.join(" ")}" fill="none" stroke="${k.color}" stroke-width="1.6"${
        k.dash ? ` stroke-dasharray="${k.dash}"` : ""
      } />`;
      series.forEach(function (s, i) {
        const value = Number(s[k.key] || 0);
        points += `<circle cx="${toX(i).toFixed(1)}" cy="${toY(value).toFixed(1)}" r="1.8" fill="${k.color}"><title>${k.label} ${s.period}: ${value.toFixed(3)}</title></circle>`;
      });
      const col = ki % 3;
      const row = Math.floor(ki / 3);
      const lx = padL + col * 58;
      const ly = 8 + row * 10;
      legend += `<rect x="${lx}" y="${ly - 4}" width="3" height="3" fill="${k.color}" />`;
      legend += `<text x="${lx + 6}" y="${ly}" fill="#bbb" font-size="7">${k.label}</text>`;
    });

    const dStart = (series[0].period || "").substring(5);
    const dEnd = (series[series.length - 1].period || "").substring(5);

    box.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto;display:block;">
        <rect width="${w}" height="${h}" fill="#0d0d0d" rx="2" />
        ${legend}
        ${grid}
        ${ticks}
        ${lines}
        ${points}
        <text x="${padL}" y="${h - 6}" fill="#777" font-size="9">${dStart}</text>
        <text x="${w - padR}" y="${h - 6}" fill="#777" font-size="9" text-anchor="end">${dEnd}</text>
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
    const totalW = cw * pairs.length;
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
        const preXVal = Number(pt["pre_" + pair.xKey] || 0);
        const preYVal = Number(pt["pre_" + pair.yKey] || 0);
        const postXVal = Number(pt["post_" + pair.xKey] || 0);
        const postYVal = Number(pt["post_" + pair.yKey] || 0);
        // Pre point (hollow)
        const preX = toX(preXVal, xRange[0], xRange[1]);
        const preY = toY(preYVal, yRange[0], yRange[1]);
        svg += `<circle cx="${(ox + preX).toFixed(1)}" cy="${preY.toFixed(1)}" r="3" fill="none" stroke="${clr}" stroke-width="1.5" opacity="0.6"><title>${pt.land_class} pre: ${pair.xLabel} ${preXVal.toFixed(2)}, ${pair.yLabel} ${preYVal.toFixed(2)}</title></circle>`;
        // Post point (filled)
        const postX = toX(postXVal, xRange[0], xRange[1]);
        const postY = toY(postYVal, yRange[0], yRange[1]);
        svg += `<circle cx="${(ox + postX).toFixed(1)}" cy="${postY.toFixed(1)}" r="3" fill="${clr}" opacity="0.9"><title>${pt.land_class} post: ${pair.xLabel} ${postXVal.toFixed(2)}, ${pair.yLabel} ${postYVal.toFixed(2)}</title></circle>`;
        // Arrow from pre to post
        svg += `<line x1="${(ox + preX).toFixed(1)}" y1="${preY.toFixed(1)}" x2="${(ox + postX).toFixed(1)}" y2="${postY.toFixed(1)}" stroke="${clr}" stroke-width="0.5" opacity="0.4" />`;
        // Post value label
        svg += `<text x="${(ox + postX + 4).toFixed(1)}" y="${(postY - 3).toFixed(1)}" fill="${clr}" font-size="5.5">${postYVal.toFixed(2)}</text>`;
      });
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
