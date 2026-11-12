const MAP_PRESETS = {
  riau: {
    center: [102.5, 0.5],
    zoom: 9,
    name: "Riau Peat Dome (Sumatra)",
    indices: { ndvi: 0.68, ndwi: 0.22, dnbr: 0.03, sar: "-6.2 dB" },
  },
  pulang_pisau: {
    center: [114.25, -2.75],
    zoom: 9.5,
    name: "Pulang Pisau Ex-PLG (Central Kalimantan)",
    indices: { ndvi: 0.35, ndwi: -0.15, dnbr: 0.42, sar: "-11.8 dB" },
  },
  musirawas: {
    center: [103.8, -2.4],
    zoom: 9,
    name: "Musi Banyuasin (South Sumatra)",
    indices: { ndvi: 0.48, ndwi: 0.05, dnbr: 0.12, sar: "-8.4 dB" },
  },
};

const MAP_STYLE_SATELLITE = {
  version: 8,
  sources: {
    "esri-imagery": {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      attribution: "&copy; Esri, Maxar, Earthstar Geographics",
    },
  },
  layers: [
    {
      id: "esri-imagery-layer",
      type: "raster",
      source: "esri-imagery",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};
