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
  osm_hot: {
    tiles: ["https://tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"],
    attribution: "&copy; OpenStreetMap contributors, Tiles style by HOT",
  },
  osm_humanitarian: {
    tiles: [
      "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
      "https://b.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
      "https://c.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
    ],
    attribution: "&copy; OpenStreetMap contributors, Humanitarian style",
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
  stamen_terrain: {
    tiles: [
      "https://stamen-tiles.a.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg",
      "https://stamen-tiles.b.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg",
      "https://stamen-tiles.c.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg",
    ],
    attribution: "&copy; Stamen Design, OpenStreetMap contributors",
  },
  stamen_toner: {
    tiles: [
      "https://stamen-tiles.a.ssl.fastly.net/toner/{z}/{x}/{y}.png",
      "https://stamen-tiles.b.ssl.fastly.net/toner/{z}/{x}/{y}.png",
      "https://stamen-tiles.c.ssl.fastly.net/toner/{z}/{x}/{y}.png",
    ],
    attribution: "&copy; Stamen Design, OpenStreetMap contributors",
  },
  stamen_watercolor: {
    tiles: [
      "https://stamen-tiles.a.ssl.fastly.net/watercolor/{z}/{x}/{y}.jpg",
      "https://stamen-tiles.b.ssl.fastly.net/watercolor/{z}/{x}/{y}.jpg",
      "https://stamen-tiles.c.ssl.fastly.net/watercolor/{z}/{x}/{y}.jpg",
    ],
    attribution: "&copy; Stamen Design, OpenStreetMap contributors",
  },
  cartodb_voyager: {
    tiles: [
      "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
      "https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
      "https://c.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
    ],
    attribution: "&copy; CARTO, OpenStreetMap contributors",
  },
  cartodb_positron: {
    tiles: [
      "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
      "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
      "https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    ],
    attribution: "&copy; CARTO, OpenStreetMap contributors",
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
  "osm",
  "osm_hot",
  "osm_humanitarian",
  "esri_topo",
  "esri_terrain",
  "stamen_terrain",
  "stamen_toner",
  "stamen_watercolor",
  "cartodb_voyager",
  "cartodb_positron",
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
