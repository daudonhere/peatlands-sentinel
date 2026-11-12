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

  function loadExisting() {
    const geom = getGeometryFromTextarea(textareaId);
    if (geom && geom.type === "Polygon") {
      const coords = geom.coordinates[0];
      points = coords.slice(0, -1).map(lngLatToPoint);
      isDrawing = false;
      ensureVertexLayer(map, prefix, color);
      updateDrawSources(map, prefix, points, true);
      renderStaticPolygon(map, geom, color, `${prefix}-final`);
      if (btnClear) btnClear.classList.remove("hidden");
      if (btnDraw) btnDraw.textContent = "Re-draw";
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
    if (btnDraw) btnDraw.textContent = "Click to add points...";
    if (btnClear) btnClear.classList.remove("hidden");
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

      if (
        points.length > 0 &&
        distancePx(map, lngLat, pointToLngLat(points[0])) < CLOSE_THRESHOLD_PX
      ) {
        if (points.length >= 3) {
          closePolygon();
        }
        return;
      }

      points.push(lngLatToPoint(lngLat));
      updateDrawSources(map, prefix, points, false);
    };

    moveHandler = (e) => {
      if (!isDrawing || points.length === 0) return;
      const lngLat = [e.lngLat.lng, e.lngLat.lat];
      const tempPoints = [...points, lngLatToPoint(lngLat)];
      updateDrawSources(map, prefix, tempPoints, false);
    };

    dblClickHandler = (e) => {
      if (!isDrawing) return;
      if (points.length >= 3) {
        closePolygon();
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

    updateDrawSources(map, prefix, points, true);
    renderStaticPolygon(map, polygon, color, `${prefix}-final`);
    setGeoJsonTextarea(textareaId, polygon);
    if (onGeometryChange) onGeometryChange(polygon);
    stopDrawing();
    clearDrawSources(map, prefix);
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
    if (btnClear) btnClear.classList.add("hidden");
    if (btnDraw) btnDraw.textContent = "Draw";
  }

  function getGeometry() {
    if (points.length >= 3) return pointsToPolygon(points);
    const geom = getGeometryFromTextarea(textareaId);
    return geom && geom.type === "Polygon" ? geom : null;
  }

  if (btnDraw) btnDraw.addEventListener("click", startDrawing);
  if (btnRedraw) btnRedraw.addEventListener("click", startDrawing);
  if (btnClear) btnClear.addEventListener("click", clearDrawing);

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
