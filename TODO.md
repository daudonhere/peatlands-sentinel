# Peatlands Sentinel - TODO

## Cosmetic / Display

- [ ] Loading text: "landsat" engine shows "Querying STAC assets" instead of "Querying Google Earth Engine assets" (map.js line 504-512)
- [ ] Sidebar metrics: frontend reads `spectral_metrics` (7 fields) instead of `telemetry` (all fields) → many zeros (map.js line 250)
- [ ] Spectral Feature Clusters chart: only shows NDVI vs BSI, should include all metrics (NDVI, NDWI, NDMI, MNDWI, NBR, dNBR, BSI, SAR, WTD, etc.)
- [ ] Multi-Temporal Index Trend chart (line): only shows NDVI/NDWI/NDMI, should include all metrics
- [ ] Duplicate Export button: two `btn-export-zip` buttons in index.html (lines 333 & 347)
- [ ] Inspect Available Passes display: improve UI to be more informative (show scene details, cloud cover, dates clearly)
- [ ] Map layer ordering: boundaries → AOI → 20 analysis layers → fire (on top, not overlapping) (z-index/layer order)

## Classifier Issues

- [ ] Land Conversion panel empty: classifier predicts only class 6 (Built-up Area) for all pixels, no class transitions detected
- [ ] Spectral Feature Clusters: verify scatter renders correctly with real GEE data

## Time Series

- [ ] Multi-Temporal Index Trend empty for GEE source: no observations fetched, series_from_live returns empty
- [ ] Consider adding GEE-based time series (monthly composite NDVI/NDWI/NDMI)

## DEM / Topography

- [ ] DEM COG read returns zeros (Planetary Computer COG access unreliable) → mean_elevation_m = 0
- [ ] Fallback dome model not triggered because elev_grid is zeros (not None/NaN)

## Field Validation

- [ ] Live NDVI (COG): Planetary Computer COG read unreliable → "COG read failed"
- [ ] Active Fires (FIRMS): verify FIRMS_MAP_KEY configured and working
- [ ] Fire hotspot markers: appear after drawing AOI, not after analysis (by design, but user expects after analysis) (map.js line 409)

## History Management

- [ ] Bundle all objective layer runs into 1 history entry per "Run Analysis" (currently each layer toggle creates separate run)

## UI / UX

- [ ] 20 analyze land checkboxes: add bulk checkbox (check all / uncheck all) so user doesn't toggle one by one

## Next TODO:

- (isi di sini)
