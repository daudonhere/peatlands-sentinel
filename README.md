# Peatlands Sentinel

Multi-temporal peatland monitoring and land cover change detection system using multimodal satellite imagery (Sentinel-1 SAR, Sentinel-2 Optical, Copernicus DEM, Landsat 8/9, ESA WorldCover) with machine learning, peat hydrology estimation, canal blocking simulation, multi-hazard assessment, and AI analyst.

## Key Features

- **Multimodal Satellite Ingestion**: Direct Cloud-Optimized GeoTIFF (COG) reading via Planetary Computer STAC (Sentinel-2 L2A spectral B02-B12 + SCL, Sentinel-1 RTC VV/VH polarization, Copernicus DEM GLO-30 30m, Landsat 8/9 SR, ESA WorldCover v200).
- **Google Earth Engine Support**: Alternative data source via GEE (S2_SR_HARMONIZED, S1_GRD, LC08/LC09, WorldCover) with native RF classifier (`smileRandomForest`).
- **Complete Spectral Indices**: NDVI, NDWI/MNDWI, NBR & dNBR, BSI, SAR cross-ratio VH/VV, **NDMI** (Normalized Difference Moisture Index).
- **Time Series & Seasonal Composite**: NDVI/NDWI/NDMI weekly/monthly/yearly aggregation, seasonal window (Aug 01 – Nov 01).
- **Peat Hydrology & Carbon Emissions Model**: WTD based on PP 71/2014 & PP 57/2016 (safe threshold -40 cm), subsidence rate, carbon emissions (0.91 tCO2e/ha/yr per cm drainage; Hooijer et al., 2012), drainage intensity, canal density, water retention capacity.
- **Multi-Hazard Assessment**: Landslide (slope + SAR anomaly + NDVI drop), ground deformation (InSAR proxy via S1 coherence), coastal inundation (MNDWI + DEM < 2m).
- **Canal Blocking Intervention Simulation**: Water table rise, hydrological recovery area, potential carbon emission reduction (tCO2e/yr).
- **Active Fire Hotspot Detection**: NASA FIRMS VIIRS (SNPP / NOAA-20/21) real-time integration.
- **8-Class Land Cover Classification**: Natural Forest, Wet Peatland, Bare Land, Oil Palm Plantation, Open Mining, Water Bodies, **Built-up Area, Cropland/Agriculture**.
- **Model Validation**: Stratified cross-validation, confusion matrix, overall accuracy, Cohen's kappa, per-class spectral scatter (NDVI vs BSI).
- **AI Analyst**: Multi-provider (OpenAI-compatible, Ollama Cloud, OpenRouter) via HTTPX + Pydantic, deterministic heuristic fallback.
- **Interactive Map Without Build Tools**: Standalone frontend (zero node_modules) using MapLibre GL JS, custom point-based AOI drawing, Turf.js via CDN.
- **Point-Based AOI Drawing**: Click vertices, live line preview, double-click/click near first point to close polygon. Boundaries restricted outside AOI, distinct colors (AOI: green, Boundaries: red).
- **11 Free Basemaps**: ESRI World Imagery/Topo/Terrain, OSM Standard/HOT/Humanitarian, Stamen Terrain/Toner/Watercolor, CartoDB Voyager/Positron — **no API key required**.
- **Dual Raster Overlay & Blend Slider**: Pre vs post spectral composite visualization with opacity control, per-index overlay (NDVI/NDWI/NDMI/BSI/dNBR).
- **Inline Charts**: Time series line chart (NDVI/NDWI/NDMI), spectral scatter (NDVI vs BSI per class), model accuracy badge (OA, Kappa, samples).
- **Complete GIS Export Bundle (ZIP)**:
  - GeoTIFF georeferenced EPSG:4326 (`.tif`)
  - **OGC GeoPackage** (`.gpkg`) — SQLite-based, valid EPSG:4326 metadata
  - QGIS desktop project XML (`.qgs`) ready-to-open
  - Vector boundary GeoJSON (`.geojson`)
  - Metrics summary JSON (`.json`)
  - Multi-sheet Excel report (`.xlsx`) via OpenPyXL (includes **Model Accuracy** sheet)
  - **Markdown report** (`.md`)
  - **CSV**: land transitions, time series
  - **SVG**: time series chart, transition bar chart, accuracy chart
  - **PNG**: colorized spectral indices per band (NDVI, NDWI, NDMI, BSI, dNBR)
  - Preview vector SVG (`.svg`)
- **SQLite History Storage**: Local SQLite database (`data/peatlands.db`) with compressed raster arrays (`.npz`).

## System Architecture

```text
FastAPI Backend (app/)
  ├── services/cog.py              # Concurrent WarpedVRT reader (S2, S1-RTC, DEM, Landsat)
  ├── services/gee.py              # GEE auth & collection catalog
  ├── services/gee_analysis.py     # GEE indices, RF classifier, stratified sampling
  ├── services/raster.py           # Canonical spectral indices (NDVI, NDWI, NDMI, dNBR, BSI)
  ├── services/geospatial.py       # Cloud masking, bounding box, DEM slope & topography
  ├── services/classifier.py       # RF land classification & transition matrix (8 classes)
  ├── services/hydrology.py        # Peat WTD, subsidence, carbon, drainage, canal density
  ├── services/hazard.py           # Multi-hazard: landslide, deformation, coastal inundation
  ├── services/temporal.py         # Time series aggregation (weekly/monthly/yearly), seasonal
  ├── services/model_metrics.py    # Cross-validation, accuracy, kappa, class scatter
  ├── services/validation.py       # StratifiedKFold, confusion matrix, per-class accuracy
  ├── services/intervention.py     # Canal blocking hydrological recovery
  ├── services/firms.py            # NASA FIRMS active fire hotspots
  ├── services/ai_analyst.py       # Multi-provider LLM + deterministic fallback
  ├── services/storage.py          # SQLite repository with compressed .npz raster blobs
  ├── services/exporter.py         # XLSX, SVG preview, GeoTIFF, QGIS .qgs
  ├── services/bundle.py           # ZIP packager (GeoJSON, GPKG, CSV, MD, XLSX, SVG, PNG, QGS)
  ├── services/charts.py           # Pure-SVG renderers (time series, transitions, accuracy)
  ├── services/gpkg.py             # OGC GeoPackage generator (pure SQLite/WKB)
  └── services/renderer.py         # PNG colorizer for spectral indices

Frontend (static/ & templates/)
  ├── MapLibre GL JS + custom point-based draw (AOI & Boundaries)
  ├── Dual raster overlay blending slider + per-index overlay
  ├── Time series line chart, spectral scatter, accuracy badge
  ├── 11 free basemap selector (no API key)
  └── Analysis: transitions, canal blocking, FIRMS, live NDVI
```

## Environment Configuration (.env)

Create a `.env` file in the repository root:

```env
# NASA FIRMS (for active fire hotspots)
FIRMS_MAP_KEY=your_firms_map_key_here

# Data Source (planetary_computer | gee)
DATA_SOURCE=planetary_computer

# STAC API endpoints
STAC_API_URL=https://planetarycomputer.microsoft.com/api/stac/v1
COPERNICUS_STAC_URL=https://catalogue.dataspace.copernicus.eu/stac

# Google Earth Engine (optional - requires project + service account)
# GEE_PROJECT=your-gee-project-id
# GEE_SERVICE_ACCOUNT=your-service-account@project.iam.gserviceaccount.com
# GEE_PRIVATE_KEY_FILE=/path/to/key.json

# AI Analyst Configuration
AI_PROVIDER=openai
AI_API_KEY=
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# Ollama Cloud / OpenRouter (alternative AI provider)
# OLLAMA_API_KEY=
# OLLAMA_URL=https://ollama.com/api/chat
# OLLAMA_MODEL=beam:cloud

# App Settings
DEBUG=false
HOST=0.0.0.0
PORT=8000
```

## Running the Application

1. Set up Python virtual environment (3.11 or 3.12):

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e .
```

2. Start FastAPI server:

```bash
uvicorn app.main:app --reload --port 8000
```

3. Access the monitoring interface at: `http://localhost:8000`

## Running Tests

Run spectral indices self-checks and end-to-end integration tests:

```bash
.venv/bin/python -m tests.test_raster && .venv/bin/python -m tests.test_pipeline
```

## Project Structure (summary)

```
peatlands-sentinel/
├── app/
│   ├── config.py                 # Pydantic Settings (.env)
│   ├── main.py                   # FastAPI entrypoint + lifespan
│   ├── schemas/analysis.py       # DTOs: GeoJSON, pipeline request/response
│   ├── services/                 # 20+ modules (cog, gee, raster, geospatial, classifier,
│   │                               hydrology, hazard, temporal, model_metrics, validation,
│   │                               ai_analyst, storage, exporter, bundle, charts, gpkg, renderer, ...)
│   ├── routes/api/               # REST endpoints: /analysis/run, /{id}/overlay, /export, /history
│   ├── static/
│   │   ├── css/                  # base.css, layout.css, results.css (monochrome dark)
│   │   └── js/                   # config, api, draw-core, draw-controller, overlay, insights, map, history
│   └── templates/index.html      # Single-page dashboard (sidebar + drawer)
├── data/                         # SQLite DB (gitignored)
├── tests/
│   ├── test_raster.py            # Spectral indices self-checks
│   └── test_pipeline.py          # E2E integration (run, storage, ZIP, QGIS, GPKG, accuracy)
├── pyproject.toml                # Dependencies & metadata
├── .env                          # Environment config (gitignored)
└── README.md                     # This file
```

## Limitations & Notes

- **Python ≥ 3.11** (typing features: `Self`, `TypeAliasType`).
- **GDAL/PROJ** via `rasterio` wheels; Linux binary wheels available via PyPI.
- **Frontend**: MapLibre GL JS 4.x, MapboxDraw 1.4, Turf.js 6.x via CDN — **no npm/build required**.
- **Database**: SQLite (`data/peatlands.db`) — single file, portable.
- **Export GPKG**: Pure Python `sqlite3` (WKB geometry), OGC GeoPackage 1.3 compliant.
- **AI Analyst**: Requires `AI_API_KEY` + OpenAI-compatible provider, or `OLLAMA_API_KEY` for Ollama Cloud. Deterministic heuristic fallback active when offline.
- **GEE**: Optional. Requires Google Cloud project + Earth Engine API enabled + service account JSON.
- **FIRMS**: Requires `FIRMS_MAP_KEY` from https://firms.modaps.eosdis.nasa.gov/api/.

## License

MIT License — free to use, modify, distribute.
