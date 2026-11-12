# Peatlands Sentinel

Multimodal satellite monitoring system for peatlands conservation, deforestation alerts, and wildfire detection using Sentinel-1 SAR and Sentinel-2 optical imagery.

## Architecture

Monolithic Python application (zero `node_modules`):

- **Backend**: FastAPI and Jinja2 templates.
- **Frontend / GIS**: MapLibre GL JS and Turf.js loaded via CDN.
- **Data Ingestion**: Planetary Computer STAC API (Sentinel-1 GRD, Sentinel-2 L2A).
- **Processing**: Rasterio, NumPy, SciPy (NDVI, NDWI, NBR, dNBR, SAR backscatter ratio).
- **AI Analyst**: Ollama structured JSON validation via Pydantic.

## Prerequisites

- Python 3.11 or 3.12
- [uv](https://github.com/astral-sh/uv) (recommended) or standard venv

## Quick Start

1. Create and activate a virtual environment:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
uv pip install -e .
```

3. Launch the application:

```bash
uvicorn app.main:app --reload --port 8000
```

4. Open `http://localhost:8000` in your browser.

## Running Tests

Execute self-check unit tests for raster computations:

```bash
python -m tests.test_raster
```
