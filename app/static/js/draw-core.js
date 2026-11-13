const AOI_COLOR = "#00ff88";
const AOI_HOVER_COLOR = "#00cc6a";
const BOUNDARY_COLOR = "#ff4444";
const BOUNDARY_HOVER_COLOR = "#cc3333";
const VERTEX_RADIUS = 6;
const CLOSE_THRESHOLD_PX = 15;

function getGeoJsonTextarea(id) {
  return document.getElementById(id);
}

function setGeoJsonTextarea(id, geometry) {
  const ta = getGeoJsonTextarea(id);
  if (!ta) return;
  if (!geometry) {
    ta.value = "";
    return;
  }
  if (geometry.type === "FeatureCollection") {
    ta.value = JSON.stringify(geometry, null, 2);
    return;
  }
  const featureCollection = {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: geometry,
      },
    ],
  };
  ta.value = JSON.stringify(featureCollection, null, 2);
}

function getGeometryFromTextarea(id) {
  const ta = getGeoJsonTextarea(id);
  if (!ta || !ta.value.trim()) return null;
  try {
    const parsed = JSON.parse(ta.value);
    return parsed.geometry || parsed;
  } catch {
    return null;
  }
}

function pointToLngLat(point) {
  return [point.lng, point.lat];
}

function lngLatToPoint(lngLat) {
  return { lng: lngLat[0], lat: lngLat[1] };
}

function distancePx(map, lngLat1, lngLat2) {
  const p1 = map.project(lngLat1);
  const p2 = map.project(lngLat2);
  return Math.hypot(p1.x - p2.x, p1.y - p2.y);
}

function createVertexSourceId(prefix) {
  return `${prefix}-vertices`;
}

function createLineSourceId(prefix) {
  return `${prefix}-line`;
}

function createFillSourceId(prefix) {
  return `${prefix}-fill`;
}

function ensureVertexLayer(map, prefix, color) {
  const vid = createVertexSourceId(prefix);
  const lid = createLineSourceId(prefix);
  const fid = createFillSourceId(prefix);

  if (!map.getSource(vid)) {
    map.addSource(vid, {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
  }
  if (!map.getSource(lid)) {
    map.addSource(lid, {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
  }
  if (!map.getSource(fid)) {
    map.addSource(fid, {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
  }

  if (!map.getLayer(`${prefix}-fill-layer`)) {
    map.addLayer({
      id: `${prefix}-fill-layer`,
      type: "fill",
      source: fid,
      paint: { "fill-color": color, "fill-opacity": 0.1 },
    });
  }
  if (!map.getLayer(`${prefix}-line-layer`)) {
    map.addLayer({
      id: `${prefix}-line-layer`,
      type: "line",
      source: lid,
      paint: { "line-color": color, "line-width": 2, "line-dasharray": [4, 4] },
    });
  }
  if (!map.getLayer(`${prefix}-vertex-layer`)) {
    map.addLayer({
      id: `${prefix}-vertex-layer`,
      type: "circle",
      source: vid,
      paint: {
        "circle-radius": VERTEX_RADIUS,
        "circle-color": color,
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ffffff",
      },
    });
  }
}

function updateDrawSources(map, prefix, points, closed) {
  const vid = createVertexSourceId(prefix);
  const lid = createLineSourceId(prefix);
  const fid = createFillSourceId(prefix);

  const vertexFeatures = points.map((pt, i) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: pointToLngLat(pt) },
    properties: { index: i },
  }));

  const lineCoords = points.map(pointToLngLat);
  const lineFeature =
    lineCoords.length >= 2
      ? {
          type: "Feature",
          geometry: { type: "LineString", coordinates: lineCoords },
          properties: {},
        }
      : null;

  const fillFeature =
    closed && points.length >= 3
      ? {
          type: "Feature",
          geometry: {
            type: "Polygon",
            coordinates: [lineCoords.concat([lineCoords[0]])],
          },
          properties: {},
        }
      : null;

  map
    .getSource(vid)
    .setData({ type: "FeatureCollection", features: vertexFeatures });
  map.getSource(lid).setData({
    type: "FeatureCollection",
    features: lineFeature ? [lineFeature] : [],
  });
  map.getSource(fid).setData({
    type: "FeatureCollection",
    features: fillFeature ? [fillFeature] : [],
  });
}

function clearDrawSources(map, prefix) {
  const empty = { type: "FeatureCollection", features: [] };
  map.getSource(createVertexSourceId(prefix))?.setData(empty);
  map.getSource(createLineSourceId(prefix))?.setData(empty);
  map.getSource(createFillSourceId(prefix))?.setData(empty);
}

function pointsToPolygon(points) {
  if (points.length < 3) return null;
  const coords = points.map(pointToLngLat);
  coords.push(coords[0]);
  return { type: "Polygon", coordinates: [coords] };
}

function renderStaticLine(map, geometry, color, layerId) {
  const geojson = { type: "Feature", geometry: geometry };
  if (map.getSource(layerId)) {
    map.getSource(layerId).setData(geojson);
  } else {
    map.addSource(layerId, { type: "geojson", data: geojson });
    map.addLayer({
      id: `${layerId}-stroke`,
      type: "line",
      source: layerId,
      paint: { "line-color": color, "line-width": 2 },
    });
  }
}

function renderStaticPolygon(map, geometry, color, layerId) {
  const geojson = { type: "Feature", geometry: geometry };
  if (map.getSource(layerId)) {
    map.getSource(layerId).setData(geojson);
  } else {
    map.addSource(layerId, { type: "geojson", data: geojson });
    map.addLayer({
      id: `${layerId}-fill`,
      type: "fill",
      source: layerId,
      paint: { "fill-color": color, "fill-opacity": 0.12 },
    });
    map.addLayer({
      id: `${layerId}-stroke`,
      type: "line",
      source: layerId,
      paint: { "line-color": color, "line-width": 2, "line-dasharray": [2, 2] },
    });
  }
}
