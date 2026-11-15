# Peatlands Sentinel

Multi-temporal peatland monitoring and land cover change detection system using multimodal satellite imagery (Sentinel-1 SAR, Sentinel-2 Optical, Copernicus DEM, Landsat 8/9, ESA WorldCover) with machine learning, peat hydrology estimation, canal blocking simulation, multi-hazard assessment, and AI analyst.

## Key Features

- **Multimodal Satellite Ingestion**: Planetary Computer STAC (Sentinel-2 L2A, Sentinel-1 RTC, Copernicus DEM GLO-30, Landsat 8/9, ESA WorldCover v200) + Google Earth Engine (optional).
- **Google Earth Engine Support**: Alternative data source via GEE (S2_SR_HARMONIZED, S1_GRD, LC08/LC09, WorldCover) with native RF classifier. GEE monthly time series, live NDVI snapshot.
- **Complete Spectral Indices**: NDVI, NDWI/MNDWI, NBR and dNBR, BSI, SAR cross-ratio VH/VV, NDMI (Normalized Difference Moisture Index).
- **Time Series and Seasonal Composite**: GEE monthly composites (NDVI/NDWI/NDMI/NBR/BSI), weekly/monthly/yearly aggregation, seasonal window.
- **Peat Hydrology and Carbon Emissions Model**: WTD based on PP 71/2014 and PP 57/2016 (safe threshold -40 cm), subsidence rate, carbon emissions (0.91 tCO2e/ha/yr per cm drainage), drainage intensity, canal density, water retention capacity.
- **Multi-Hazard Assessment**: Landslide (slope + SAR anomaly + NDVI drop), ground deformation (InSAR proxy via S1 coherence), coastal inundation (MNDWI + DEM < 2m).
- **Canal Blocking Intervention Simulation**: Water table rise, hydrological recovery area, potential carbon emission reduction (tCO2e/yr). Calibratable with field data.
- **Active Fire Hotspot Detection**: NASA FIRMS multi-sensor (VIIRS SNPP / NOAA-20 + MODIS) real-time integration with deduplication, confidence filter, map markers, archive support.
- **8-Class Land Cover Classification**: Natural Forest, Wet Peatland, Bare Land, Oil Palm Plantation, Open Mining, Water Bodies, Built-up Area, Cropland/Agriculture. WorldCover v200 training labels.
- **Model Validation**: Stratified cross-validation, confusion matrix, overall accuracy, Cohen's kappa, per-class spectral scatter (all metrics).
- **AI Analyst**: Multi-provider (OpenAI-compatible, Ollama Cloud, OpenRouter) via HTTPX + Pydantic, deterministic heuristic fallback (multi-metric scoring).
- **Interactive Map Without Build Tools**: Standalone frontend (zero node_modules) using MapLibre GL JS, custom point-based AOI drawing, Turf.js via CDN.
- **Point-Based AOI Drawing**: Click vertices, live line preview, double-click/click near first point to close polygon. Draw/Clear toggle.
- **13 Free Basemaps**: ESRI (10 variants), OpenStreetMap, OpenTopoMap, CyclOSM - no API key required.
- **Dual Raster Overlay and Blend Slider**: Pre vs post spectral composite visualization with opacity control, per-index overlay.
- **Inline Charts**: Time series line chart (NDVI/NDWI/NDMI/NBR/BSI), spectral feature clusters (all metrics per class), model accuracy badge.
- **Complete GIS Export Bundle (ZIP)**: GeoTIFF, GeoPackage, QGIS .qgs, GeoJSON, XLSX, SVG, CSV, MD, PNG.
- **SQLite History Storage**: Local SQLite database with compressed raster arrays (.npz).
- **Multi-Source Fallback**: GEE to Landsat to Planetary Computer with user notification.
- **Bulk Layer Toggle**: Check/uncheck all 20 analysis layers at once.
- **Fire Hotspot Markers**: Appear after analysis (not on draw).
- **Back Navigation**: Back button on history and inspect panels.

## System Architecture

```text
FastAPI Backend (app/)
  ├── services/cog.py              # Concurrent WarpedVRT reader (S2, S1-RTC, DEM, Landsat)
  ├── services/gee.py              # GEE auth, collections, pipeline_metrics, landsat, monthly TS, live NDVI
  ├── services/gee_analysis.py     # WorldCover training, fractions, mask, validation, target modulators
  ├── services/raster.py           # Canonical spectral indices (NDVI, NDWI, NDMI, dNBR, BSI, SAR)
  ├── services/geospatial.py       # Cloud masking, bounding box, DEM slope and topography
  ├── services/classifier.py       # RF land classification and transition matrix (8 classes, WorldCover)
  ├── services/hydrology.py        # Peat WTD, subsidence, carbon, drainage, canal density
  ├── services/hazard.py           # Multi-hazard: landslide, deformation, coastal inundation
  ├── services/temporal.py         # Time series aggregation, GEE monthly composites
  ├── services/model_metrics.py    # Cross-validation, accuracy, kappa, class scatter
  ├── services/validation.py       # StratifiedKFold, confusion matrix, per-class accuracy
  ├── services/intervention.py     # Canal blocking hydrological recovery (calibratable)
  ├── services/firms.py            # NASA FIRMS active fire hotspots (multi-sensor)
  ├── services/ai_analyst.py       # Multi-provider LLM + deterministic fallback
  ├── services/storage.py          # SQLite repository with compressed .npz raster blobs
  ├── services/exporter.py         # XLSX, SVG preview, GeoTIFF, QGIS .qgs
  ├── services/bundle.py           # ZIP packager (GPKG, CSV, MD, PNG, SVG)
  ├── services/charts.py           # Pure-SVG renderers (time series, transitions, accuracy)
  ├── services/gpkg.py             # OGC GeoPackage generator (pure SQLite/WKB)
  ├── services/renderer.py         # PNG colorizer for spectral indices
  ├── services/observations.py     # STAC scene observations for time series
  └── services/reference_data.py   # Target modulators, class names, colors

Frontend (static/ and templates/)
  ├── MapLibre GL JS + custom point-based draw (AOI and Boundaries)
  ├── Dual raster overlay blending slider + per-index overlay
  ├── Time series line chart (5 metrics), spectral clusters (all metrics), accuracy badge
  ├── 13 free basemap selector (no API key)
  ├── 20 objective layers with bulk toggle
  ├── FIRMS confidence filter, map markers, archive support
  └── Analysis: transitions, canal blocking, FIRMS, live NDVI (GEE fallback)
```

## Environment Configuration (.env)

```env
# NASA FIRMS (for active fire hotspots)
FIRMS_MAP_KEY=your_firms_map_key_here

# Data Source (planetary_computer | gee | landsat)
DATA_SOURCE=planetary_computer

# STAC API endpoints
STAC_API_URL=https://planetarycomputer.microsoft.com/api/stac/v1

# Google Earth Engine (optional)
GEE_PROJECT=your-gee-project-id

# AI Analyst Configuration
AI_PROVIDER=openai
AI_API_KEY=
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# App Settings
DEBUG=false
HOST=0.0.0.0
PORT=8000
```

## Software Requirements

### Required

| Software | Version                      | Description                             |
| -------- | ---------------------------- | --------------------------------------- |
| Python   | 3.11 or 3.12 (>=3.11, <3.13) | Main runtime                            |
| pip      | >=23.0                       | Package installer (bundled with Python) |
| uv       | >=0.4.0 (optional)           | Fast package manager (recommended)      |

### Optional (for development)

| Software | Version         | Description                                                    |
| -------- | --------------- | -------------------------------------------------------------- |
| Node.js  | >=18 (optional) | Only for frontend development; not required (frontend via CDN) |
| npm      | >=9 (optional)  | Package manager for Node.js                                    |
| Git      | >=2.30          | Version control                                                |

### System Libraries (Linux)

| Library   | Description                                                           |
| --------- | --------------------------------------------------------------------- |
| GDAL/PROJ | Via rasterio binary wheels (PyPI). No manual install needed on Linux. |
| SQLite    | Bundled with Python (stdlib).                                         |

### Python Dependencies (auto-installed via pyproject.toml)

```
fastapi, uvicorn, jinja2, pydantic, pydantic-settings, httpx,
numpy, rasterio, shapely, pystac-client, planetary-computer,
scipy, scikit-image, scikit-learn, openpyxl
```

### Dev Dependencies (optional)

```
pytest, ruff
```

## Running the Application

```bash
# 1. Create virtual environment
uv venv --python 3.12 .venv
# or: python3 -m venv .venv

# 2. Activate
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
uv pip install -e .
# or: pip install -e .

# 4. Run server
uvicorn app.main:app --reload --port 8000
```

Access: `http://localhost:8000`

## Running Tests

```bash
.venv/bin/python -m tests.test_raster && .venv/bin/python -m tests.test_pipeline && .venv/bin/python -m tests.test_unit
```

## Project Structure (summary)

```
peatlands-sentinel/
├── app/
│   ├── config.py, main.py
│   ├── schemas/analysis.py
│   ├── services/ (24 modules)
│   ├── routes/api/ (analysis, insights, peatlands)
│   ├── static/ (css, js)
│   └── templates/index.html
├── data/ (SQLite DB, gitignored)
├── tests/ (test_raster, test_pipeline, test_unit)
├── pyproject.toml
└── README.md
```

## Limitations and Notes

- **Python 3.11+** (typing features).
- **GDAL/PROJ** via rasterio wheels.
- **Frontend**: MapLibre GL JS 4.x, MapboxDraw 1.4, Turf.js 6.x via CDN - no npm/build required.
- **Database**: SQLite (`data/peatlands.db`) - single file, portable.
- **Export GPKG**: Pure Python sqlite3 (WKB geometry), OGC GeoPackage 1.3 compliant.
- **AI Analyst**: Requires AI_API_KEY + OpenAI-compatible provider. Deterministic heuristic fallback active when offline.
- **GEE**: Optional. Requires Google Cloud project + Earth Engine API enabled.
- **FIRMS**: Requires FIRMS_MAP_KEY from https://firms.modaps.eosdis.nasa.gov/api/.
- **DEM**: Planetary Computer COG reads may be unreliable; fallback dome model used.
- **Live NDVI (COG)**: Uses GEE fallback when Planetary Computer COG unavailable.

## License

MIT License - free to use, modify, distribute.
