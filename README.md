# Peatlands Sentinel

Sistem pemantauan lahan gambut dan perubahan tutupan lahan multi-temporal berbasis citra satelit multimodal (Sentinel-1 SAR, Sentinel-2 Optical, Copernicus DEM, Landsat 8/9, ESA WorldCover) dengan machine learning, estimasi hidrologi gambut, simulasi sekat kanal, multi-hazard assessment, dan AI analyst.

## Fitur Utama

- **Multimodal Satellite Ingestion**: Pembacaan langsung Cloud-Optimized GeoTIFF (COG) via Planetary Computer STAC (Sentinel-2 L2A spektral B02-B12 + SCL, Sentinel-1 RTC polarisasi VV/VH, Copernicus DEM GLO-30 30m, Landsat 8/9 SR, ESA WorldCover v200).
- **Google Earth Engine Support**: Alternatif sumber data via GEE (S2_SR_HARMONIZED, S1_GRD, LC08/LC09, WorldCover) dengan RF classifier native (`smileRandomForest`).
- **Indeks Spektral Lengkap**: NDVI, NDWI/MNDWI, NBR & dNBR, BSI, SAR cross-ratio VH/VV, **NDMI** (Normalized Difference Moisture Index).
- **Time Series & Seasonal Composite**: NDVI/NDWI/NDMI weekly/monthly/yearly aggregation, seasonal window (Aug 01 – Nov 01).
- **Model Hidrologi & Emisi Karbon Gambut**: WTD berbasis PP 71/2014 & PP 57/2016 (ambang aman -40 cm), laju amblesan, emisi karbon (0.91 tCO2e/ha/th per cm drainase), drainase intensity, kanal density, water retention capacity.
- **Multi-Hazard Assessment**: Longsor (slope + SAR anomaly + NDVI drop), deformasi tanah (InSAR proxy via S1 coherence), inundasi pesisir (MNDWI + DEM < 2m).
- **Simulasi Intervensi Sekat Kanal**: Kalkulasi kenaikan muka air, luas pemulihan, potensi reduksi emisi (tCO2e/th).
- **Deteksi Titik Panas Kebakaran (Hotspots)**: Integrasi NASA FIRMS VIIRS real-time.
- **Klasifikasi Tutupan Lahan 8 Kelas**: Hutan Alami, Lahan Gambut Basah, Lahan Terbuka, Kebun Sawit, Tambang Terbuka, Badan Air, **Built-up Area, Cropland/Agriculture**.
- **Model Validation**: Stratified cross-validation, confusion matrix, overall accuracy, Cohen's kappa, per-class scatter (NDVI vs BSI).
- **AI Analyst**: Multi-provider (OpenAI-compatible, Ollama Cloud, OpenRouter) via HTTPX + Pydantic, deterministic heuristic fallback.
- **Peta Interaktif Tanpa Build Tools**: Frontend mandiri (zero node_modules) menggunakan MapLibre GL JS, custom point-based AOI drawing, Turf.js via CDN.
- **Point-Based AOI Drawing**: Klik-titik (vertex), garis preview live, double-click/klik dekat titik awal untuk close polygon. Boundaries dibatasi di luar AOI, warna berbeda (AOI: hijau, Boundaries: merah).
- **Basemap Gratis 11 Pilihan**: ESRI World Imagery/Topo/Terrain, OSM Standard/HOT/Humanitarian, Stamen Terrain/Toner/Watercolor, CartoDB Voyager/Positron — **tanpa API key**.
- **Dual Raster Overlay & Blend Slider**: Visualisasi komposit spektral pre vs post dengan kontrol opasitas, overlay per indeks (NDVI/NDWI/NDMI/BSI/dNBR).
- **Charts Inline**: Time series line chart (NDVI/NDWI/NDMI), spectral scatter (NDVI vs BSI per kelas), model accuracy badge (OA, Kappa, samples).
- **Ekspor Bundel GIS Lengkap (ZIP)**:
  - GeoTIFF georeferenced EPSG:4326 (`.tif`)
  - **OGC GeoPackage** (`.gpkg`) — SQLite-based, valid EPSG:4326 metadata
  - Template proyek desktop QGIS XML (`.qgs`) siap buka
  - Batas vektor GeoJSON (`.geojson`)
  - Ringkasan metrik JSON (`.json`)
  - Laporan Excel multi-sheet (`.xlsx`) via OpenPyXL (termasuk sheet **Model Accuracy**)
  - **Markdown report** (`.md`)
  - **CSV**: land transitions, time series
  - **SVG**: time series chart, transition bar chart, accuracy chart
  - **PNG**: indeks berwarna per band (NDVI, NDWI, NDMI, BSI, dNBR)
  - Vektor pratinjau SVG (`.svg`)
- **Penyimpanan Riwayat SQLite**: Database lokal SQLite (`data/peatlands.db`) dengan kompresi raster array `.npz`.

## Arsitektur Sistem

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

## Konfigurasi Lingkungan (.env)

Buat file `.env` di root repository:

```env
# NASA FIRMS (untuk active fire hotspots)
FIRMS_MAP_KEY=your_firms_map_key_here

# Data Source (planetary_computer | gee)
DATA_SOURCE=planetary_computer

# STAC API endpoints
STAC_API_URL=https://planetarycomputer.microsoft.com/api/stac/v1
COPERNICUS_STAC_URL=https://catalogue.dataspace.copernicus.eu/stac

# Google Earth Engine (opsional - butuh project + service account)
# GEE_PROJECT=your-gee-project-id
# GEE_SERVICE_ACCOUNT=your-service-account@project.iam.gserviceaccount.com
# GEE_PRIVATE_KEY_FILE=/path/to/key.json

# AI Analyst Configuration
AI_PROVIDER=openai
AI_API_KEY=
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# Ollama Cloud / OpenRouter (alternatif AI provider)
# OLLAMA_API_KEY=
# OLLAMA_URL=https://ollama.com/api/chat
# OLLAMA_MODEL=beam:cloud

# App Settings
DEBUG=false
HOST=0.0.0.0
PORT=8000
```

## Menjalankan Aplikasi

1. Siapkan virtual environment Python (3.11 atau 3.12):

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e .
```

2. Jalankan server FastAPI:

```bash
uvicorn app.main:app --reload --port 8000
```

3. Akses antarmuka pemantauan di peramban: `http://localhost:8000`

## Menjalankan Pengujian

Menjalankan pengujian kalkulasi indeks spektral dan end-to-end integrasi:

```bash
.venv/bin/python -m tests.test_raster && .venv/bin/python -m tests.test_pipeline
```

## Struktur Proyek (ringkas)

```
peatlands-sentinel/
├── app/
│   ├── config.py                 # Pydantic Settings (.env)
│   ├── main.py                   # FastAPI entrypoint + lifespan
│   ├── schemas/analysis.py       # DTOs: GeoJSON, pipeline request/response
│   ├── services/                 # 20+ modul (cog, gee, raster, geospatial, classifier,
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

## Keterbatasan & Catatan

- **Python ≥ 3.11** (typing features: `Self`, `TypeAliasType`).
- **GDAL/PROJ** via `rasterio` wheels; Linux binary wheels tersedia via PyPI.
- **Frontend**: MapLibre GL JS 4.x, MapboxDraw 1.4, Turf.js 6.x via CDN — **tanpa npm/build**.
- **Database**: SQLite (`data/peatlands.db`) — file tunggal, portable.
- **Export GPKG**: Pure Python `sqlite3` (WKB geometry), OGC GeoPackage 1.3 compliant.
- **AI Analyst**: Memerlukan `AI_API_KEY` + provider kompatibel OpenAI, atau `OLLAMA_API_KEY` untuk Ollama Cloud. Fallback deterministic heuristic aktif jika offline.
- **GEE**: Opsional. Butuh Google Cloud project + Earth Engine API enabled + service account JSON.
- **FIRMS**: Butuh `FIRMS_MAP_KEY` dari https://firms.modaps.eosdis.nasa.gov/api/.

## Lisensi

MIT License — gunakan, modifikasi, distribusikan bebas.
