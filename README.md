# Peatlands Sentinel

Sistem monitoring lahan gambut, deforestasi, dan deteksi dini kebakaran hutan berbasis citra satelit multimodal (Sentinel-1 SAR dan Sentinel-2 MSI).

## Arsitektur Monolith

Aplikasi dibangun sebagai arsitektur Python tunggal (zero `node_modules`):

- **Backend**: FastAPI dan Jinja2.
- **Frontend / GIS**: MapLibre GL JS dan Turf.js via CDN.
- **Data Ingestion**: Planetary Computer STAC API (Sentinel-1, Sentinel-2).
- **Processing**: Rasterio, NumPy, SciPy (NDVI, NDWI, NBR, dNBR, SAR backscatter ratio).
- **AI Analyst**: Ollama structured JSON validation via Pydantic.

## Menjalankan Aplikasi

1. Buat environment Python (3.11 atau 3.12):

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

2. Jalankan server aplikasi:

```bash
uvicorn app.main:app --reload --port 8000
```

3. Buka browser pada `http://localhost:8000`.

## Menjalankan Pengujian

```bash
python -m tests.test_raster
```
