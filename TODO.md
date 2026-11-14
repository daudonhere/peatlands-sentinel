# Peatlands Sentinel - TODO

## Dummy/Simulated Data (perlu di-real-kan)

### Training Data & Classification

- [x] Integrate ESA WorldCover v200 as baseline land cover reference & Random Forest training labels (ganti TRAINING_X/Y hardcoded)
- [x] Add WorldCover-based area masking (filter analysis to peatland/forest only, exclude urban & water)
- [x] Use WorldCover for classification validation (compare ML output vs WorldCover labels)
- [x] Replace TARGET_MODULATORS hardcoded values with computed spectral adjustments per objective

### Fallback Functions (perlu real data)

- [x] Remove simulate_class_scatter fallback — ensure pre_arrays/post_arrays always populated from real data
- [x] Remove modelled_series fallback — increase observation fetch to get >= 3 real scenes
- [x] Remove _fallback_gradient in renderer — ensure arrays always provided

### Heuristic/Estimation (opsional, bisa tetap)

- [ ] AI Analyst: improve heuristic_report to use more real metrics (saat ini rule-based)
- [ ] Canal blocking: kalibrasi rumus dengan data lapangan (pengukuran WTD sebelum/sesudah sekat)

## Landsat & WorldCover Integration

- [x] Integrate Landsat 8/9 OLI/TIRS for historical time series (pre-2015 baseline)
- [x] Add Landsat thermal band (LST) for peatland surface temperature & dryness detection
- [ ] Implement Landsat gap-filling when Sentinel-2 unavailable (cloud cover)
- [x] Add cross-sensor validation (compare Sentinel-2 vs Landsat NDVI/NDWI consistency)
- [x] Add Landsat & WorldCover as selectable data sources in UI dropdown
- [x] Implement Landsat pipeline_metrics in gee.py (saat ini hanya collection terdaftar)

## Data Source & Performance

- [ ] Improve Planetary Computer (STAC) reliability (retry logic, timeout handling)
- [ ] Add GEE pipeline_metrics optimization (reduce getInfo round-trips)
- [ ] Add multi-source fallback with user notification (jangan silent fallback)

## FIRMS

- [ ] Add confidence filter (n/l/h) di frontend
- [ ] Tampilkan fire hotspot markers di peta (saat ini hanya count di panel)
- [ ] Support arsip FIRMS (bukan hanya NRT)

## UI/UX

- [ ] Default data source: GEE (sudah) — pastikan konsisten
- [ ] Date format dd/mm/yy (sudah) — pastikan semua tampilan konsisten
- [ ] 20 layer checkbox auto-check (sudah) — pastikan toggle works
- [ ] Map default view Indonesia (sudah)

## Testing

- [ ] Add unit tests for gee.pipeline_metrics
- [ ] Add unit tests for firms multi-sensor
- [ ] Add integration test for GEE data source
- [ ] Add test for 20-layer auto-run flow
