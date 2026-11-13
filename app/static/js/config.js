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

const BASEMAP_PROVIDERS = {
  esri: {
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ],
    attribution: "&copy; Esri, Maxar, Earthstar Geographics",
  },
  osm: {
    tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    attribution: "&copy; OpenStreetMap contributors",
  },
  esri_topo: {
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    ],
    attribution: "&copy; Esri, HERE, Garmin, FAO, NOAA, USGS",
  },
  esri_terrain: {
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}",
    ],
    attribution: "&copy; Esri, USGS, NOAA",
  },
  esri_street: {
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    ],
    attribution: "&copy; Esri, HERE, Garmin, USGS",
  },
  esri_shaded_relief: {
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}",
    ],
    attribution: "&copy; Esri, USGS",
  },
  esri_physical: {
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Physical_Map/MapServer/tile/{z}/{y}/{x}",
    ],
    attribution: "&copy; Esri, USGS, NOAA",
  },
  opentopomap: {
    tiles: ["https://tile.opentopomap.org/{z}/{x}/{y}.png"],
    attribution: "&copy; OpenTopoMap, OpenStreetMap contributors",
  },
  esri_natgeo: {
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}",
    ],
    attribution: "&copy; Esri, National Geographic, Garmin",
  },
  esri_ocean: {
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}",
    ],
    attribution: "&copy; Esri, GEBCO, NOAA, Garmin",
  },
  esri_light_gray: {
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    ],
    attribution: "&copy; Esri, HERE, Garmin",
  },
  esri_dark_gray: {
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    ],
    attribution: "&copy; Esri, HERE, Garmin",
  },
  cyclosm: {
    tiles: [
      "https://a.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png",
      "https://b.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png",
      "https://c.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png",
    ],
    attribution: "&copy; CyclOSM, OpenStreetMap contributors",
  },
  thunderforest_landscape: {
    tiles: ["https://tile.thunderforest.com/landscape/{z}/{x}/{y}.png?apikey="],
    attribution: "&copy; Thunderforest, OpenStreetMap contributors",
    requiresKey: true,
  },
  jawg_sunny: {
    tiles: ["https://tile.jawg.io/jawg-sunny/{z}/{x}/{y}.png?apikey="],
    attribution: "&copy; Jawg Maps, OpenStreetMap contributors",
    requiresKey: true,
  },
};

const FREE_BASEMAPS = [
  "esri",
  "esri_topo",
  "esri_terrain",
  "esri_street",
  "esri_shaded_relief",
  "esri_physical",
  "esri_natgeo",
  "esri_ocean",
  "esri_light_gray",
  "esri_dark_gray",
  "osm",
  "opentopomap",
  "cyclosm",
];

const MAP_STYLE_SATELLITE = {
  version: 8,
  sources: {
    "basemap-source": {
      type: "raster",
      tiles: BASEMAP_PROVIDERS.esri.tiles,
      tileSize: 256,
      attribution: BASEMAP_PROVIDERS.esri.attribution,
    },
  },
  layers: [
    {
      id: "basemap-layer",
      type: "raster",
      source: "basemap-source",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

function switchBasemap(map, providerKey) {
  const provider = BASEMAP_PROVIDERS[providerKey] || BASEMAP_PROVIDERS.esri;
  if (provider.requiresKey) {
    console.warn("Basemap requires API key, falling back to ESRI");
    providerKey = "esri";
    provider = BASEMAP_PROVIDERS.esri;
  }
  if (!map.isStyleLoaded()) return;
  if (map.getLayer("basemap-layer")) {
    map.removeLayer("basemap-layer");
  }
  if (map.getSource("basemap-source")) {
    map.removeSource("basemap-source");
  }
  map.addSource("basemap-source", {
    type: "raster",
    tiles: provider.tiles,
    tileSize: 256,
    attribution: provider.attribution,
  });
  const layers = map.getStyle().layers || [];
  const beforeId = layers.length > 0 ? layers[0].id : undefined;
  map.addLayer(
    {
      id: "basemap-layer",
      type: "raster",
      source: "basemap-source",
      minzoom: 0,
      maxzoom: 19,
    },
    beforeId,
  );
}
