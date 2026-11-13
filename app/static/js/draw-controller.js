function lineToPolygon(geom) {
  if (!geom) return null;
  if (geom.type === "Polygon" || geom.type === "MultiPolygon") return geom;
  if (geom.type === "LineString") {
    const coords = geom.coordinates.slice();
    if (coords.length < 3) return null;
    const first = coords[0];
    const last = coords[coords.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) {
      coords.push([first[0], first[1]]);
    }
    return { type: "Polygon", coordinates: [coords] };
  }
  return null;
}

function extractGeometryFromInput(value) {
  let data = value;
  if (typeof value === "string") {
    try {
      data = JSON.parse(value);
    } catch {
      return null;
    }
  }
  if (!data || typeof data !== "object") return null;
  if (data.type === "FeatureCollection" && Array.isArray(data.features)) {
    const feature = data.features.find(function (f) {
      return (
        f &&
        f.geometry &&
        (f.geometry.type === "Polygon" ||
          f.geometry.type === "MultiPolygon" ||
          f.geometry.type === "LineString" ||
          f.geometry.type === "MultiLineString")
      );
    });
    data = feature ? feature.geometry : null;
  }
  if (data && data.type === "Feature" && data.geometry) {
    data = data.geometry;
  }
  if (
    data &&
    (data.type === "Polygon" ||
      data.type === "MultiPolygon" ||
      data.type === "LineString" ||
      data.type === "MultiLineString") &&
    Array.isArray(data.coordinates)
  ) {
    return data;
  }
  return null;
}

function geometryBounds(geometry) {
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
  walk(geometry.coordinates);
  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ];
}

function createPointDrawController(map, options) {
  const {
    prefix,
    color,
    hoverColor,
    textareaId,
    onGeometryChange,
    canDrawOutsideFn,
    otherPrefix,
  } = options;

  let points = [];
  let isDrawing = false;
  let clickHandler = null;
  let moveHandler = null;
  let dblClickHandler = null;

  const btnDraw = document.getElementById(`btn-draw-${prefix}`);
  const btnRedraw = document.getElementById(`btn-redraw-${prefix}`);
  const btnClear = document.getElementById(`btn-clear-${prefix}`);

  function importGeometryFromTextarea(fit) {
    if (isDrawing) return;
    if (!map.loaded()) {
      map.once("load", function () {
        importGeometryFromTextarea(fit);
      });
      return;
    }
    const textarea = getGeoJsonTextarea(textareaId);
    if (!textarea) return;
    const geom = extractGeometryFromInput(textarea.value);
    if (!geom) {
      showDrawButton();
      return;
    }

    try {
      if (map.getSource(`${prefix}-final`)) {
        try {
          map.removeLayer(`${prefix}-final-fill`);
          map.removeLayer(`${prefix}-final-stroke`);
          map.removeSource(`${prefix}-final`);
        } catch (err) {}
      }
      points = [];
      clearDrawSources(map, prefix);
      ensureVertexLayer(map, prefix, color);

      if (geom.type === "Polygon") {
        const coords = geom.coordinates[0];
        points = coords.slice(0, -1).map(lngLatToPoint);
        updateDrawSources(map, prefix, points, true);
        renderStaticPolygon(map, geom, color, `${prefix}-final`);
      } else if (geom.type === "LineString") {
        points = [];
        clearDrawSources(map, prefix);
        renderStaticLine(map, geom, color, `${prefix}-final`);
      } else {
        points = [];
        clearDrawSources(map, prefix);
        renderStaticPolygon(map, geom, color, `${prefix}-final`);
      }
      setGeoJsonTextarea(textareaId, geom);
      showClearButton();
      if (onGeometryChange) onGeometryChange(lineToPolygon(geom) || geom);
      if (fit) {
        try {
          map.fitBounds(geometryBounds(geom), { padding: 40, animate: false });
        } catch (err) {}
      }
    } catch (err) {}
  }

  function loadExisting() {
    importGeometryFromTextarea(true);
  }

  function showDrawButton() {
    if (btnDraw) {
      btnDraw.classList.remove("hidden");
      btnDraw.textContent = "Draw";
    }
  }

  function showClearButton() {
    if (btnDraw) {
      btnDraw.classList.remove("hidden");
      btnDraw.textContent = "Clear";
    }
  }

  function startDrawing() {
    if (isDrawing) return;
    clearDrawSources(map, prefix);
    if (map.getSource(`${prefix}-final`)) {
      map.removeLayer(`${prefix}-final-fill`);
      map.removeLayer(`${prefix}-final-stroke`);
      map.removeSource(`${prefix}-final`);
    }
    points = [];
    isDrawing = true;
    ensureVertexLayer(map, prefix, color);
    if (btnDraw) btnDraw.textContent = "Clear";
    attachHandlers();
  }

  function stopDrawing() {
    isDrawing = false;
    detachHandlers();
    if (btnDraw) btnDraw.textContent = points.length >= 3 ? "Re-draw" : "Draw";
  }

  function attachHandlers() {
    clickHandler = (e) => {
      if (!isDrawing) return;
      const lngLat = [e.lngLat.lng, e.lngLat.lat];

      if (canDrawOutsideFn && !canDrawOutsideFn(lngLat)) {
        return;
      }

      let nearestIndex = -1;
      let nearestDistance = Infinity;
      points.forEach(function (pt, idx) {
        const d = distancePx(map, lngLat, pointToLngLat(pt));
        if (d < CLOSE_THRESHOLD_PX && d < nearestDistance) {
          nearestDistance = d;
          nearestIndex = idx;
        }
      });

      if (nearestIndex !== -1) {
        if (nearestIndex === 0 && points.length >= 3) {
          closePolygon();
        } else {
          points = points.slice(0, nearestIndex);
          if (points.length > 0) {
            updateDrawSources(map, prefix, points, false);
          } else {
            clearDrawSources(map, prefix);
          }
        }
        return;
      }

      try {
        points.push(lngLatToPoint(lngLat));
        updateDrawSources(map, prefix, points, false);
      } catch (err) {
        console.error("draw click error:", err);
        stopDrawing();
      }
    };

    moveHandler = (e) => {
      if (!isDrawing || points.length === 0) return;
      try {
        const lngLat = [e.lngLat.lng, e.lngLat.lat];
        const tempPoints = [...points, lngLatToPoint(lngLat)];
        updateDrawSources(map, prefix, tempPoints, false);
      } catch (err) {
        console.error("draw move error:", err);
      }
    };

    dblClickHandler = (e) => {
      if (!isDrawing) return;
      if (points.length >= 3) {
        try {
          closePolygon();
        } catch (err) {
          console.error("dblclick close error:", err);
          stopDrawing();
        }
      }
    };

    map.on("click", clickHandler);
    map.on("mousemove", moveHandler);
    map.on("dblclick", dblClickHandler);
    map.getCanvas().style.cursor = "crosshair";
  }

  function detachHandlers() {
    map.off("click", clickHandler);
    map.off("mousemove", moveHandler);
    map.off("dblclick", dblClickHandler);
    map.getCanvas().style.cursor = "";
  }

  function closePolygon() {
    if (points.length < 3) return;
    const polygon = pointsToPolygon(points);
    if (!polygon) return;

    try {
      updateDrawSources(map, prefix, points, true);
      renderStaticPolygon(map, polygon, color, `${prefix}-final`);
      setGeoJsonTextarea(textareaId, polygon);
      if (onGeometryChange) onGeometryChange(polygon);
    } catch (err) {
      console.error("closePolygon error:", err);
    } finally {
      stopDrawing();
      clearDrawSources(map, prefix);
      showClearButton();
    }
  }

  function clearDrawing() {
    points = [];
    isDrawing = false;
    clearDrawSources(map, prefix);
    if (map.getSource(`${prefix}-final`)) {
      map.removeLayer(`${prefix}-final-fill`);
      map.removeLayer(`${prefix}-final-stroke`);
      map.removeSource(`${prefix}-final`);
    }
    setGeoJsonTextarea(textareaId, "");
    if (onGeometryChange) onGeometryChange(null);
    detachHandlers();
    showDrawButton();
    if (btnDraw) btnDraw.textContent = "Draw";
  }

  function getGeometry() {
    if (points.length >= 3) return pointsToPolygon(points);
    const geom = extractGeometryFromInput(
      getGeoJsonTextarea(textareaId)?.value,
    );
    return lineToPolygon(geom) || geom;
  }

  function handleDrawButtonClick() {
    if (isDrawing || getGeometry()) {
      clearDrawing();
    } else {
      startDrawing();
    }
  }

  if (btnDraw) {
    btnDraw.addEventListener("click", handleDrawButtonClick);
    btnDraw.textContent = getGeometry() ? "Clear" : "Draw";
  }
  if (btnRedraw) btnRedraw.style.display = "none";

  const textarea = getGeoJsonTextarea(textareaId);
  if (textarea) {
    const trigger = function () {
      setTimeout(function () {
        importGeometryFromTextarea(true);
      }, 0);
    };
    textarea.addEventListener("input", trigger);
    textarea.addEventListener("change", trigger);
    textarea.addEventListener("paste", trigger);
    textarea.addEventListener("blur", trigger);
  }

  loadExisting();

  return { getGeometry, clear: clearDrawing, startDrawing };
}

function createAoiDrawController(map, onGeometryChange) {
  return createPointDrawController(map, {
    prefix: "polygon",
    color: AOI_COLOR,
    hoverColor: AOI_HOVER_COLOR,
    textareaId: "aoi-geojson",
    onGeometryChange,
    canDrawOutsideFn: null,
  });
}

function createBoundaryDrawController(map, onGeometryChange, getAoiGeometry) {
  return createPointDrawController(map, {
    prefix: "boundary",
    color: BOUNDARY_COLOR,
    hoverColor: BOUNDARY_HOVER_COLOR,
    textareaId: "boundary-geojson",
    onGeometryChange,
    canDrawOutsideFn: (lngLat) => {
      const aoi = getAoiGeometry();
      if (!aoi) return true;
      const turf = window.turf;
      if (!turf) return true;
      try {
        const pt = turf.point(lngLat);
        const poly = turf.polygon(aoi.coordinates);
        return !turf.booleanPointInPolygon(pt, poly);
      } catch {
        return true;
      }
    },
  });
}

function renderAoiPolygon(map, geometryOrBbox, colorHex) {
  let geometry;
  if (Array.isArray(geometryOrBbox) && geometryOrBbox.length === 4) {
    const [w, s, e, n] = geometryOrBbox;
    geometry = {
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
  } else if (geometryOrBbox && geometryOrBbox.type) {
    geometry = geometryOrBbox;
  } else {
    return;
  }
  renderStaticPolygon(map, geometry, colorHex || "#ffffff", "aoi-viewport");
}

function createDrawController(map, onGeometryChange) {
  const aoiCtrl = createAoiDrawController(map, onGeometryChange);
  const getAoiGeometry = () => aoiCtrl.getGeometry();
  const boundaryCtrl = createBoundaryDrawController(
    map,
    onGeometryChange,
    getAoiGeometry,
  );

  return {
    getGeometry: () => aoiCtrl.getGeometry(),
    getBoundaryGeometry: () => boundaryCtrl.getGeometry(),
    clearAoi: () => aoiCtrl.clear(),
    clearBoundary: () => boundaryCtrl.clear(),
  };
}
