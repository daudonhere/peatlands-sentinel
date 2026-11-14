# Peatlands Sentinel - TODO

## Sidebar Display (semua metrik telemetry harus ditampilkan)

### Spectral Indices (saat ini hanya 4 dari 7)

- [ ] Tampilkan NDMI (Normalized Difference Moisture Index)
- [ ] Tampilkan NBR (Normalized Burn Ratio)
- [ ] Tampilkan BSI (Bare Soil Index)
- [ ] Tampilkan MNDWI (Modified NDWI)

### Topography (belum ditampilkan)

- [ ] Tampilkan Elevasi (mean/max/min/relief)
- [ ] Tampilkan Slope/Kelerengan (mean/max)

### Hydrology (saat ini hanya 3 dari 10+)

- [ ] Tampilkan Water Retention Capacity
- [ ] Tampilkan Drainage Intensity
- [ ] Tampilkan Canal Density
- [ ] Tampilkan Drainage Pressure Index
- [ ] Tampilkan Hydrology Compliance (PP 71/2014)
- [ ] Tampilkan Hydrology Risk Level
- [ ] Tampilkan Block Priority

### Multi-Hazard (belum ditampilkan)

- [ ] Tampilkan Landslide Susceptibility
- [ ] Tampilkan Ground Deformation Index
- [ ] Tampilkan Seismic Sensitivity

### AI Analyst

- [ ] Moisture Condition & Threat Status perlu data final dari AI (saat ini heuristic)

### Landsat

- [ ] Landsat gap-filling when Sentinel-2 unavailable (cloud cover)

### Data Source & Performance

- [ ] Multi-source fallback with user notification (jangan silent fallback)

### FIRMS

- [ ] Confidence filter (n/l/h) di frontend
- [ ] Tampilkan fire hotspot markers di peta (saat ini hanya count di panel)
- [ ] Support arsip FIRMS (bukan hanya NRT)

### Testing

- [ ] Unit tests for gee.pipeline_metrics
- [ ] Unit tests for firms multi-sensor
- [ ] Integration test for GEE data source
- [ ] Test for 20-layer auto-run flow
