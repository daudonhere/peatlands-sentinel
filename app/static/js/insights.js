function createInsightsController(
  map,
  getBbox,
  getRunId,
  getDateRange,
  getGeometries,
) {
  const $ = function (id) {
    return document.getElementById(id);
  };

  const INDEX_SERIES = [
    { key: "ndvi", label: "NDVI", color: "#34d399", unit: "", lane: 0 },
    { key: "ndwi", label: "NDWI", color: "#38bdf8", unit: "", lane: 0 },
    { key: "mndwi", label: "MNDWI", color: "#2dd4bf", unit: "", lane: 0 },
    { key: "ndmi", label: "NDMI", color: "#facc15", unit: "", lane: 0 },
    { key: "nbr", label: "NBR", color: "#f87171", unit: "", lane: 0 },
    { key: "bsi", label: "BSI", color: "#cbd5e1", unit: "", lane: 0 },
    { key: "dnbr", label: "dNBR", color: "#fb923c", unit: "", lane: 0 },
    { key: "sar", label: "SAR VH-VV", color: "#a78bfa", unit: "dB", lane: 1 },
    { key: "lst", label: "LST", color: "#f472b6", unit: "\u00b0C", lane: 2 },
  ];

  const LANES = [0, 1, 2];

  function seriesValue(row, key) {
    const raw = row[key];
    if (raw === null || raw === undefined || raw === "") return null;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  }

  function unitSuffix(unit) {
    return unit ? ` ${unit}` : "";
  }

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
    const changed = (transitions || [])
      .filter(function (t) {
        return t.from_class !== t.to_class;
      })
      .sort(function (a, b) {
        return b.area_hectares - a.area_hectares;
      })
      .slice(0, 6);
    const stable = (transitions || []).filter(function (t) {
      return t.from_class === t.to_class;
    });
    const stableHa = stable.reduce(function (s, t) {
      return s + (t.area_hectares || 0);
    }, 0);
    if (!changed.length && !stable.length) {
      box.innerHTML =
        '<p class="results-state-desc" style="font-size:0.75rem;">No land class conversion detected (classification requires GEE training data).</p>';
      return;
    }
    if (stableHa > 0) {
      const line = document.createElement("p");
      line.className = "results-state-desc";
      line.style.fontSize = "0.75rem";
      line.style.marginBottom = "0.35rem";
      line.textContent =
        "Unchanged area: " +
        stableHa.toFixed(1) +
        " ha across " +
        stable.length +
        " class(es).";
      box.appendChild(line);
    }
    if (!changed.length) {
      return;
    }
    // Per-class area summary (pre -> post) derived from transition matrix.
    const preAreas = {};
    const postAreas = {};
    (transitions || []).forEach(function (t) {
      preAreas[t.from_class] = (preAreas[t.from_class] || 0) + (t.area_hectares || 0);
      postAreas[t.to_class] = (postAreas[t.to_class] || 0) + (t.area_hectares || 0);
    });
    const classNames = Object.keys(preAreas).concat(Object.keys(postAreas)).filter(function (v, i, a) { return a.indexOf(v) === i; });
    if (classNames.length) {
      const summary = classNames.map(function (c) {
        return c + ": " + (preAreas[c] || 0).toFixed(0) + " -> " + (postAreas[c] || 0).toFixed(0);
      }).join(" | ");
      const line = document.createElement("p");
      line.className = "results-state-desc";
      line.style.fontSize = "0.7rem";
      line.style.marginTop = "0.35rem";
      line.textContent = "Class areas (ha) pre->post: " + summary;
      box.appendChild(line);
    }
    const max = changed[0].area_hectares || 1;
    changed.forEach(function (t) {
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

  function renderTimeSeries(series, granularity) {
    const box = $("timeseries-chart");
    const badge = $("ts-granularity-badge");
    if (!box) return;
    if (badge) {
      badge.textContent = `${(granularity || "monthly").toUpperCase()} CADENCE`;
    }
    if (!series || !series.length) {
      box.innerHTML =
        '<p class="results-state-desc" style="font-size:0.75rem;">No temporal series data available.</p>';
      return;
    }

    const present = function (k) {
      return series.some(function (row) {
        return seriesValue(row, k.key) !== null;
      });
    };
    const activeLanes = LANES.filter(function (lane) {
      return INDEX_SERIES.filter(function (k) {
        return k.lane === lane;
      }).some(present);
    });
    if (!activeLanes.length) {
      box.innerHTML =
        '<p class="results-state-desc" style="font-size:0.75rem;">No index values returned for this window.</p>';
      return;
    }

    const w = 340;
    const padL = 30;
    const padR = 8;
    const padB = 14;
    const legendRows = Math.ceil(INDEX_SERIES.length / 3);
    const padT = 8 + legendRows * 10 + 4;
    const laneH = 34;
    const gap = 6;
    const plotW = w - padL - padR;
    const plotH =
      activeLanes.length * laneH + Math.max(0, activeLanes.length - 1) * gap;
    const h = padT + plotH + padB;

    const xStep = series.length > 1 ? plotW / (series.length - 1) : 0;
    const toX = function (index) {
      if (series.length === 1) return padL + plotW / 2;
      return padL + index * xStep;
    };

    let grid = "";
    let lines = "";
    let points = "";
    let laneText = "";

    activeLanes.forEach(function (lane, li) {
      const keys = INDEX_SERIES.filter(function (k) {
        return k.lane === lane;
      });
      let min = Infinity;
      let max = -Infinity;
      series.forEach(function (row) {
        keys.forEach(function (k) {
          const v = seriesValue(row, k.key);
          if (v !== null) {
            min = Math.min(min, v);
            max = Math.max(max, v);
          }
        });
      });
      if (!Number.isFinite(min)) return;
      if (max - min < 0.02) {
        const bump = Math.max(0.1, Math.abs(max) * 0.05);
        min -= bump;
        max += bump;
      }
      const lanePad = (max - min) * 0.1;
      min -= lanePad;
      max += lanePad;

      const top = padT + li * (laneH + gap);
      const bottom = top + laneH;
      const toY = function (value) {
        return bottom - ((value - min) / (max - min)) * laneH;
      };

      for (let t = 0; t <= 2; t += 1) {
        const value = max - ((max - min) * t) / 2;
        const y = toY(value);
        grid += `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${w - padR}" y2="${y.toFixed(1)}" stroke="#222" stroke-width="1" />`;
        laneText += `<text x="${padL - 3}" y="${(y + 2.5).toFixed(1)}" fill="#777" font-size="6.5" text-anchor="end">${value.toFixed(value >= 100 || value <= -100 ? 0 : 1)}</text>`;
      }

      keys.forEach(function (k) {
        let segment = [];
        series.forEach(function (row, index) {
          const value = seriesValue(row, k.key);
          if (value === null) {
            if (segment.length > 1) {
              lines += `<polyline points="${segment.join(" ")}" fill="none" stroke="${k.color}" stroke-width="1.5" />`;
            }
            segment = [];
            return;
          }
          const cx = toX(index).toFixed(1);
          const cy = toY(value).toFixed(1);
          segment.push(`${cx},${cy}`);
          points += `<circle cx="${cx}" cy="${cy}" r="1.8" fill="${k.color}"><title>${k.label} ${row.period}: ${value.toFixed(2)}${unitSuffix(k.unit)}</title></circle>`;
        });
        if (segment.length > 1) {
          lines += `<polyline points="${segment.join(" ")}" fill="none" stroke="${k.color}" stroke-width="1.5" />`;
        }
      });
    });

    let legend = "";
    const colW = plotW / 3;
    INDEX_SERIES.forEach(function (k, ki) {
      const lx = padL + (ki % 3) * colW;
      const ly = 9 + Math.floor(ki / 3) * 10;
      const opacity = present(k) ? 1 : 0.28;
      legend += `<g opacity="${opacity}"><rect x="${lx}" y="${ly - 4}" width="4" height="4" fill="${k.color}" />`;
      legend += `<text x="${lx + 7}" y="${ly}" fill="#bbb" font-size="6.5">${k.label}${k.unit ? ` (${k.unit})` : ""}</text></g>`;
    });

    const tickIdx = Array.from(
      new Set([0, Math.round((series.length - 1) / 2), series.length - 1]),
    );
    let axis = "";
    tickIdx.forEach(function (index, pos) {
      const anchor =
        tickIdx.length === 1
          ? "middle"
          : pos === 0
            ? "start"
            : pos === tickIdx.length - 1
              ? "end"
              : "middle";
      axis += `<text x="${toX(index).toFixed(1)}" y="${h - 4}" fill="#777" font-size="7" text-anchor="${anchor}">${series[index].period}</text>`;
    });

    box.innerHTML = `
        <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto;display:block;">
          <rect width="${w}" height="${h}" fill="#0d0d0d" rx="2" />
          ${legend}
          ${grid}
          ${laneText}
          ${lines}
          ${points}
          ${axis}
        </svg>
      `;
  }

  function renderIndexScatter(series, granularity) {
    const box = $("scatter-chart");
    if (!box) return;
    if (!series || !series.length) {
      box.innerHTML =
        '<p class="results-state-desc" style="font-size:0.75rem;">No feature cluster samples available.</p>';
      return;
    }

    const rows = INDEX_SERIES.filter(function (k) {
      return series.some(function (row) {
        return seriesValue(row, k.key) !== null;
      });
    });
    if (!rows.length) {
      box.innerHTML =
        '<p class="results-state-desc" style="font-size:0.75rem;">No index values returned for this window.</p>';
      return;
    }

    const w = 340;
    const labelW = 52;
    const padR = 8;
    const padT = 4;
    const rowH = 15;
    const plotW = w - labelW - padR;
    const h = padT + rows.length * rowH + 13;

    let svg = `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto;display:block;">`;
    svg += `<rect width="${w}" height="${h}" fill="#0d0d0d" rx="2" />`;

    rows.forEach(function (k, ri) {
      const values = series
        .map(function (row) {
          return seriesValue(row, k.key);
        })
        .filter(function (v) {
          return v !== null;
        });
      let min = Math.min(...values);
      let max = Math.max(...values);
      if (max - min < 1e-6) {
        min -= 0.5;
        max += 0.5;
      }
      const y = padT + ri * rowH + rowH / 2;
      svg += `<line x1="${labelW}" y1="${y}" x2="${w - padR}" y2="${y}" stroke="#232323" stroke-width="0.8" />`;
      svg += `<text x="2" y="${(y + 2.4).toFixed(1)}" fill="${k.color}" font-size="6.5">${k.label}${k.unit ? ` ${k.unit}` : ""}</text>`;

      series.forEach(function (row, si) {
        const value = seriesValue(row, k.key);
        if (value === null) return;
        const cx = labelW + ((value - min) / (max - min)) * plotW;
        const age = series.length > 1 ? si / (series.length - 1) : 1;
        const opacity = (0.3 + 0.7 * age).toFixed(2);
        svg += `<circle cx="${cx.toFixed(1)}" cy="${y}" r="2.4" fill="${k.color}" opacity="${opacity}"><title>${k.label} ${row.period}: ${value.toFixed(2)}${unitSuffix(k.unit)}</title></circle>`;
      });
    });

    const cadence = (granularity || "monthly").toUpperCase();
    const countLabel = `${series.length} POINT${series.length === 1 ? "" : "S"}`;
    svg += `<text x="${labelW}" y="${h - 3}" fill="#777" font-size="6.5">${cadence} ${countLabel}</text>`;
    svg += `<text x="${w - padR}" y="${h - 3}" fill="#777" font-size="6.5" text-anchor="end">FAINT OLDER / SOLID NEWER</text>`;
    svg += `</svg>`;
    box.innerHTML = svg;
  }

  function renderModelAccuracy(accuracy, trainingError) {
    const elBadge = $("val-accuracy-badge");
    const elOverall = $("val-overall-acc");
    const elKappa = $("val-kappa");
    const elSamples = $("val-samples");
    const supportBox = $("val-class-support");
    const noteBox = $("model-accuracy-note");
    if (!accuracy || (accuracy.samples || 0) === 0) {
      if (elBadge) elBadge.textContent = "OA: - | \u03ba -";
      if (elOverall) elOverall.textContent = "0.0";
      if (elKappa) elKappa.textContent = "0.0";
      if (elSamples) elSamples.textContent = "0";
      if (supportBox) supportBox.textContent = "";
      if (noteBox)
        noteBox.textContent = trainingError
          ? `Training failed: ${trainingError}`
          : "No training data (GEE unavailable or no scenes). Re-run with GEE engine.";
      return;
    }
    const rows = (accuracy.confusion_matrix || [])
      .map(function (row, i) {
        const n = (row || []).reduce(function (s, v) {
          return s + v;
        }, 0);
        return { name: (accuracy.class_names || [])[i], n: n };
      })
      .filter(function (r) {
        return r.n > 0;
      });
    const distinct = rows.length;
    if (distinct < 3) {
      if (elBadge) elBadge.textContent = "OA: - | \u03ba -";
      if (elOverall) elOverall.textContent = "0.0";
      if (elKappa) elKappa.textContent = "0.0";
      if (elSamples) elSamples.textContent = String(accuracy.samples || 0);
      if (supportBox)
        supportBox.textContent =
          "Class support: " +
          rows
            .map(function (r) {
              return r.name + ": " + r.n;
            })
            .join(" | ");
      if (noteBox)
        noteBox.textContent =
          "Insufficient class diversity (" +
          distinct +
          "/8 classes). Accuracy not representative; use a more heterogeneous AOI.";
      return;
    }
    const oaPct = (accuracy.overall_accuracy * 100).toFixed(1) + "%";
    const kappaPct = (Number(accuracy.kappa || 0) * 100).toFixed(1) + "%";
    const samples = accuracy.samples || 0;
    if (elBadge)
      elBadge.textContent = `OA ${(accuracy.overall_accuracy * 100).toFixed(0)}% | \u03ba ${kappaPct}`;
    if (elOverall) elOverall.textContent = oaPct;
    if (elKappa) elKappa.textContent = kappaPct;
    if (elSamples) elSamples.textContent = String(samples);
    if (supportBox)
      supportBox.textContent =
        "Class support: " +
        rows
          .map(function (r) {
            return r.name + ": " + r.n;
          })
          .join(" | ");
    if (noteBox) noteBox.textContent = "";
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

  const btnFires = $("btn-fires");
  if (btnFires)
    btnFires.addEventListener("click", function () {
      const status = $("insight-status");
      const confFilter = $("firms-confidence");
      const conf = confFilter ? confFilter.value : "all";
      const archiveEl = $("firms-archive");
      const archive = archiveEl ? archiveEl.checked : false;
      withBusy(btnFires, "Querying FIRMS...", async function () {
        try {
          const data = await fetchActiveFires(getBbox(), 5, archive);
          let fires = data.fires || [];
          if (conf !== "all") {
            fires = fires.filter(function (f) {
              return f.confidence === conf || f.confidence === "h";
            });
          }
          const geoms =
            typeof getGeometries === "function" ? getGeometries() : [];
          const polygons = (geoms || []).filter(Boolean);
          if (polygons.length) {
            fires = fires.filter(function (f) {
              const pt = turf.point([f.longitude, f.latitude]);
              return polygons.some(function (g) {
                try {
                  const geom = g && g.type === "Feature" ? g.geometry : g;
                  if (
                    !geom ||
                    (geom.type !== "Polygon" && geom.type !== "MultiPolygon")
                  ) {
                    return true;
                  }
                  return turf.booleanPointInPolygon(pt, geom);
                } catch (e) {
                  return true;
                }
              });
            });
          }
          showFires(fires);
          status.textContent = `${fires.length} hotspots (conf: ${conf}, ${archive ? "archive" : "NRT"})`;
        } catch (err) {
          status.textContent = err.message;
        }
      });
    });

  const btnLiveNdvi = $("btn-live-ndvi");
  if (btnLiveNdvi)
    btnLiveNdvi.addEventListener("click", function () {
      const status = $("insight-status");
      withBusy(btnLiveNdvi, "Reading COG...", async function () {
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

  async function loadFires(conf, archive) {
    const status = $("insight-status");
    try {
      const data = await fetchActiveFires(getBbox(), 5, !!archive);
      let fires = data.fires || [];
      if (conf && conf !== "all") {
        fires = fires.filter(function (f) {
          return f.confidence === conf || f.confidence === "h";
        });
      }
      const geoms = typeof getGeometries === "function" ? getGeometries() : [];
      const polygons = (geoms || []).filter(Boolean);
      if (polygons.length) {
        fires = fires.filter(function (f) {
          const pt = turf.point([f.longitude, f.latitude]);
          return polygons.some(function (g) {
            try {
              const geom = g && g.type === "Feature" ? g.geometry : g;
              if (!geom || (geom.type !== "Polygon" && geom.type !== "MultiPolygon")) return true;
              return turf.booleanPointInPolygon(pt, geom);
            } catch (e) {
              return true;
            }
          });
        });
      }
      showFires(fires);
      if (status) status.textContent = `${fires.length} hotspots (conf: ${conf || "all"}, ${archive ? "archive" : "NRT"})`;
    } catch (err) {
      if (status) status.textContent = err.message;
    }
  }

  return {
    renderTransitions: renderTransitions,
    renderTimeSeries: renderTimeSeries,
    renderIndexScatter: renderIndexScatter,
    renderModelAccuracy: renderModelAccuracy,
    loadFires: loadFires,
    refreshIntervention: updateIntervention,
    showFires: showFires,
  };
}
