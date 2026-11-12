function createRasterOverlayController(map) {
  const toggleCheckbox = document.getElementById("toggle-raster-layer");
  const opacitySlider = document.getElementById("raster-opacity-slider");
  const compareSlider = document.getElementById("compare-slider");
  const compareLabel = document.getElementById("compare-ratio-label");

  function getBaseOpacity() {
    return opacitySlider ? Number(opacitySlider.value) / 100.0 : 0.75;
  }

  function applyOpacities() {
    const base = getBaseOpacity();
    const ratio = compareSlider ? Number(compareSlider.value) / 100.0 : 1.0;

    const preOpacity = (1.0 - ratio) * base;
    const postOpacity = ratio * base;

    if (map.getLayer("analysis-raster-pre")) {
      map.setPaintProperty("analysis-raster-pre", "raster-opacity", preOpacity);
    }
    if (map.getLayer("analysis-raster-post")) {
      map.setPaintProperty(
        "analysis-raster-post",
        "raster-opacity",
        postOpacity,
      );
    }

    if (compareLabel) {
      if (ratio === 1.0) {
        compareLabel.textContent = "Post (100%)";
      } else if (ratio === 0.0) {
        compareLabel.textContent = "Pre (100%)";
      } else {
        compareLabel.textContent = `Blend (${Math.round(ratio * 100)}% Post)`;
      }
    }
  }

  function setOverlay(runId, bbox) {
    const [w, s, e, n] = bbox;
    const coordinates = [
      [w, n],
      [e, n],
      [e, s],
      [w, s],
    ];

    removeOverlay();

    map.addSource("analysis-raster-pre-source", {
      type: "image",
      url: `/api/analysis/${runId}/overlay.png?period=pre`,
      coordinates: coordinates,
    });
    map.addSource("analysis-raster-post-source", {
      type: "image",
      url: `/api/analysis/${runId}/overlay.png?period=post`,
      coordinates: coordinates,
    });

    map.addLayer({
      id: "analysis-raster-pre",
      type: "raster",
      source: "analysis-raster-pre-source",
      paint: { "raster-opacity": 0.0, "raster-fade-duration": 150 },
    });

    map.addLayer({
      id: "analysis-raster-post",
      type: "raster",
      source: "analysis-raster-post-source",
      paint: {
        "raster-opacity": getBaseOpacity(),
        "raster-fade-duration": 150,
      },
    });

    if (compareSlider) compareSlider.value = 100;
    applyOpacities();

    if (toggleCheckbox) toggleCheckbox.checked = true;
  }

  function removeOverlay() {
    ["analysis-raster-post", "analysis-raster-pre"].forEach(function (id) {
      if (map.getLayer(id)) map.removeLayer(id);
    });
    ["analysis-raster-post-source", "analysis-raster-pre-source"].forEach(
      function (id) {
        if (map.getSource(id)) map.removeSource(id);
      },
    );
  }

  if (toggleCheckbox) {
    toggleCheckbox.addEventListener("change", function () {
      const vis = toggleCheckbox.checked ? "visible" : "none";
      if (map.getLayer("analysis-raster-pre")) {
        map.setLayoutProperty("analysis-raster-pre", "visibility", vis);
      }
      if (map.getLayer("analysis-raster-post")) {
        map.setLayoutProperty("analysis-raster-post", "visibility", vis);
      }
    });
  }

  if (opacitySlider) opacitySlider.addEventListener("input", applyOpacities);
  if (compareSlider) compareSlider.addEventListener("input", applyOpacities);

  return {
    setOverlay: setOverlay,
    removeOverlay: removeOverlay,
  };
}
