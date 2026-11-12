function createRasterOverlayController(map) {
  const toggleCheckbox = document.getElementById("toggle-raster-layer");
  const opacitySlider = document.getElementById("raster-opacity-slider");

  function setOverlay(runId, bbox) {
    const [w, s, e, n] = bbox;
    const coordinates = [
      [w, n],
      [e, n],
      [e, s],
      [w, s],
    ];

    if (map.getLayer("analysis-raster-layer")) {
      map.removeLayer("analysis-raster-layer");
    }
    if (map.getSource("analysis-raster-source")) {
      map.removeSource("analysis-raster-source");
    }

    map.addSource("analysis-raster-source", {
      type: "image",
      url: `/api/analysis/${runId}/overlay.png`,
      coordinates: coordinates,
    });

    const opacity = opacitySlider ? Number(opacitySlider.value) / 100.0 : 0.75;
    map.addLayer({
      id: "analysis-raster-layer",
      type: "raster",
      source: "analysis-raster-source",
      paint: {
        "raster-opacity": opacity,
        "raster-fade-duration": 300,
      },
    });

    if (toggleCheckbox) {
      toggleCheckbox.checked = true;
    }
  }

  function removeOverlay() {
    if (map.getLayer("analysis-raster-layer")) {
      map.removeLayer("analysis-raster-layer");
    }
    if (map.getSource("analysis-raster-source")) {
      map.removeSource("analysis-raster-source");
    }
  }

  if (toggleCheckbox) {
    toggleCheckbox.addEventListener("change", function () {
      if (map.getLayer("analysis-raster-layer")) {
        map.setLayoutProperty(
          "analysis-raster-layer",
          "visibility",
          toggleCheckbox.checked ? "visible" : "none",
        );
      }
    });
  }

  if (opacitySlider) {
    opacitySlider.addEventListener("input", function () {
      if (map.getLayer("analysis-raster-layer")) {
        map.setPaintProperty(
          "analysis-raster-layer",
          "raster-opacity",
          Number(opacitySlider.value) / 100.0,
        );
      }
    });
  }

  return {
    setOverlay: setOverlay,
    removeOverlay: removeOverlay,
  };
}
