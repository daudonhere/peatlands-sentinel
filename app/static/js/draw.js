function renderAoiPolygon(map, bbox, colorHex) {
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

function createDrawController(map, onGeometryChange) {
  const draw = new MapboxDraw({
    displayControlsDefault: false,
    controls: { polygon: false, trash: false },
    defaultMode: "simple_select",
  });

  map.addControl(draw);

  const btnDraw = document.getElementById("btn-draw-polygon");
  const btnClear = document.getElementById("btn-clear-polygon");

  let customGeometry = null;

  function updateDrawnFeature() {
    const data = draw.getAll();
    if (data.features && data.features.length > 0) {
      customGeometry = data.features[0].geometry;
      if (btnClear) btnClear.classList.remove("hidden");
      if (btnDraw) btnDraw.textContent = "Re-draw AOI";
    } else {
      customGeometry = null;
      if (btnClear) btnClear.classList.add("hidden");
      if (btnDraw) btnDraw.textContent = "Draw Custom AOI";
    }
    if (onGeometryChange) onGeometryChange(customGeometry);
  }

  map.on("draw.create", updateDrawnFeature);
  map.on("draw.update", updateDrawnFeature);
  map.on("draw.delete", updateDrawnFeature);

  if (btnDraw) {
    btnDraw.addEventListener("click", function () {
      draw.deleteAll();
      draw.changeMode("draw_polygon");
      if (btnDraw) btnDraw.textContent = "Click map to draw...";
    });
  }

  if (btnClear) {
    btnClear.addEventListener("click", function () {
      draw.deleteAll();
      updateDrawnFeature();
    });
  }

  return {
    getGeometry: function () {
      return customGeometry;
    },
    clear: function () {
      draw.deleteAll();
      updateDrawnFeature();
    },
  };
}
