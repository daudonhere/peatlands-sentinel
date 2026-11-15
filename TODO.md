# Peatlands Sentinel - TODO

## Cosmetic / Display

- [x] Loading text: "landsat" engine shows "Querying STAC assets" instead of "Querying Google Earth Engine assets" (map.js line 504-512)
- [x] Sidebar metrics: frontend reads `spectral_metrics` (7 fields) instead of `telemetry` (all fields) → many zeros (map.js line 250)
- [x] Spectral Feature Clusters chart: now shows all metrics (NDVI, NDWI, NDMI, BSI, NBR pre/post) as grouped bar chart
- [x] Multi-Temporal Index Trend chart (line): now shows NDVI, NDWI, NDMI, NBR, BSI (5 metrics)
- [x] Inspect Available Passes display: improve UI to be more informative (show scene details, cloud cover, dates clearly)
- [x] Map layer ordering: boundaries → AOI → 20 analysis layers → fire (on top, not overlapping) (z-index/layer order)
- [x] Duplicate Export button: two `btn-export-zip` buttons in index.html (lines 333 & 347)

## Classifier Issues

- [x] Land Conversion panel empty: classifier predicts only class 6 (Built-up Area) for all pixels, no class transitions detected — FIXED (WorldCover + merged training data, now predicts 4 classes)
- [x] Spectral Feature Clusters: verify scatter renders correctly with real GEE data — FIXED (now shows grouped bar chart with all 5 metrics)

## Time Series

- [x] Multi-Temporal Index Trend empty for GEE source: no observations fetched, series_from_live returns empty
- [x] Consider adding GEE-based time series (monthly composite NDVI/NDWI/NDMI) — DONE (gee_monthly_time_series)
- [x] Time series now includes NBR and BSI (not just NDVI/NDWI/NDMI)

## DEM / Topography

- [x] DEM COG read returns zeros (Planetary Computer COG access unreliable) → mean_elevation_m = 0
- [x] Fallback dome model not triggered because elev_grid is zeros (not None/NaN)

## Field Validation

- [x] Live NDVI (COG): Planetary Computer COG read unreliable → "COG read failed" — FIXED (GEE fallback added)
- [x] Active Fires (FIRMS): verify FIRMS_MAP_KEY configured and working — VERIFIED (works, 5 fires found)
- [x] Fire hotspot markers: appear after drawing AOI, not after analysis (by design, but user expects after analysis) (map.js line 409) — FIXED (removed from draw callback, now only after analysis)

## History Management

- [x] Bundle all objective layer runs into 1 history entry per "Run Analysis" (currently each layer toggle creates separate run) — FIXED (save_to_history flag)

## UI / UX

- [x] 20 analyze land checkboxes: add bulk checkbox (check all / uncheck all) so user doesn't toggle one by one

## WorldCover Fix

- [x] WorldCover image is Image not ImageCollection → fixed _worldcover_image
- [x] _with_indices uses B08/B04 instead of B8/B4 → fixed
- [x] worldcover_training_data uses cover.eq() as region (invalid) → fixed to use geom with updateMask
- [x] worldcover_training_data uses B02/B03 (wrong band names) → fixed to B2/B3
- [x] Merge WorldCover training data with hardcoded for class diversity

## Next TODO:

- (isi di sini)
