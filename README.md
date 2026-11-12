# Peatlands Sentinel

Sistem pemantauan lahan gambut dan perubahan tutupan lahan multi-temporal berbasis citra satelit multimodal (Sentinel-1 SAR, Sentinel-2 Optical, Copernicus DEM) dengan machine learning, estimasi hidrologi gambut, simulasi sekat kanal, dan AI analyst.

## Fitur Utama

- **Multimodal Satellite Ingestion**: Pembacaan langsung Cloud-Optimized GeoTIFF (COG) via Planetary Computer STAC (Sentinel-2 L2A spektral B02-B12 + SCL, Sentinel-1 RTC polarisasi VV/VH, Copernicus DEM GLO-30 30m).
- **Indeks Spektral Standar**: NDVI (kanopi), NDWI/MNDWI (air dan kebasahan), NBR & dNBR (bekas kebakaran), BSI (tanah terbuka), SAR cross-ratio VH/VV (struktur tembus awan).
- **Model Hidrologi & Emisi Karbon Gambut**:
  - Kedalaman muka air tanah (Water Table Depth / WTD) berbasis PP 71/2014 & PP 57/2016 (ambang batas aman -40 cm).
  - Laju amblesan gambut (subsidence) dan emisi karbon tahunan (0.91 tCO2e/ha/th per cm drainase; Hooijer et al., 2012).
- **Simulasi Intervensi Sekat Kanal (Canal Blocking)**: Kalkulasi kenaikan muka air tanah, luas pemulihan hidrologi, dan potensi reduksi emisi karbon (tCO2e/th).
- **Deteksi Titik Panas Kebakaran (Hotspots)**: Integrasi satelit NASA FIRMS VIIRS (SNPP / NOAA-20/21) real-time.
- **Deteksi Perubahan Lahan (Land Cover Transition)**: Klasifikasi Random Forest multi-temporal (Hutan Alami, Lahan Gambut Basah, Lahan Terbuka, Kebun Sawit, Tambang Terbuka, Badan Air) dan matriks konversi hektar.
- **Peta Interaktif Tanpa Build Tools**: Frontend mandiri (zero node_modules) menggunakan MapLibre GL JS, MapboxDraw (custom AOI polygon), dan Turf.js via CDN.
- **Dual Raster Overlay & Blend Slider**: Visualisasi komposit spektral pre vs post periode dengan kontrol opasitas transparan.
- **Ekspor Bundel GIS Lengkap (ZIP)**:
  - GeoTIFF georeferenced EPSG:4326 (`.tif`)
  - Template proyek desktop QGIS XML (`.qgs`) siap buka
  - Batas vektor GeoJSON (`.geojson`)
  - Ringkasan metrik JSON (`.json`)
  - Laporan Excel multi-sheet (`.xlsx`) via OpenPyXL
  - Vektor pratinjau SVG (`.svg`)
- **Penyimpanan Riwayat SQLite**: Database lokal SQLite (`data/peatlands.db`) dengan kompresi raster array `.npz`.

## Arsitektur Sistem

```text
FastAPI Backend (app/)
  ├── services/cog.py          # Concurrent WarpedVRT reader (S2, S1-RTC, DEM)
  ├── services/raster.py       # Canonical spectral indices (NDVI, NDWI, dNBR, BSI)
  ├── services/geospatial.py   # Cloud masking, bounding box, DEM slope
  ├── services/classifier.py   # Random Forest land classification & transitions
  ├── services/hydrology.py    # Peat WTD, subsidence, carbon emissions
  ├── services/intervention.py # Canal blocking hydrological recovery
  ├── services/firms.py        # NASA FIRMS active fire hotspots
  ├── services/ai_analyst.py   # OpenAI-compatible / Ollama / deterministic fallback
  ├── services/storage.py      # SQLite repository with compressed .npz raster blobs
  └── services/exporter.py     # ZIP packager (GeoTIFF, QGIS .qgs, Excel, SVG)

Frontend (static/ & templates/)
  ├── MapLibre GL JS + MapboxDraw (draw polygon atau viewport)
  ├── Dual raster overlay blending slider
  └── Analisis transisi lahan, sekat kanal, dan FIRMS
```

## Konfigurasi Lingkungan (.env)

Buat file `.env` di root repository:

```env
# AI Analyst (Opsional: fallback ke Ollama atau deterministic heuristic jika tidak diisi)
AI_API_KEY=your_api_key_here
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# Ollama Lokal (Opsional)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# NASA FIRMS (Opsional untuk active fire hotspots)
FIRMS_MAP_KEY=your_firms_map_key_here
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
