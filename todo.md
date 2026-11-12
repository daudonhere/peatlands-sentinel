# Peatlands Sentinel - Review Findings Todo

Hasil review struktur kode (17 temuan). High (1-3) + Medium/Low sebagian selesai dikerjakan.

Status: `[ ]` pending, `[x]` done. Selesai: 1-5, 7-10, 15, 17. Tersisa: 6, 11-14, 16.

## High

- [x] 1. **Inkonsistensi cloud mask SCL** (dead code removed)
  - File: `app/services/geospatial.py` (`apply_s2_cloud_mask`), `app/services/cog.py` (`_SCL_INVALID`)
  - Masalah: mask geospatial `[3,8,9,10]` vs cog `{0,1,3,8,9,10}`.
  - Aksi: samakan set (tambah 0,1) atau hapus fungsi yang tidak terpakai (YAGNI).

- [x] 2. **Area AOI = luas bbox persegi panjang** (shoelace polygon area)
  - File: `app/services/geospatial.py` (`calculate_polygon_area_hectares`)
  - Masalah: menghitung rectangle bbox, bukan poligon aktual → overestimate untuk AOI irregular.
  - Aksi: gunakan `shapely` (sudah dependency) untuk area geodesic poligon yang akurat.

- [x] 3. **`_fetch_s2_bands` tanpa `return_exceptions`** (return_exceptions + partial handling)
  - File: `app/services/cog.py` (`_fetch_s2_bands`)
  - Masalah: satu band gagal → seluruh snapshot gagal → fallback simulasi.
  - Aksi: pakai `return_exceptions=True` dan handle band hilang (NaN).

## Medium

- [x] 4. **Import fragile di `simulate_aoi_transitions`** (moved TARGET_MODULATORS to top, removed inner import)
  - File: `app/services/classifier.py` (`simulate_aoi_transitions`)
  - Masalah: import `TARGET_MODULATORS` di dalam fungsi (didefinisikan di akhir modul) dan akses private `_TRAINING_X/_TRAINING_Y`.
  - Aksi: pindahkan konstanta ke atas / import di top-level.

- [x] 5. **NaN propagation di renderer zoom** (nan mask preserved via separate zoom)
  - File: `app/services/renderer.py` (`generate_spectral_overlay_png`)
  - Masalah: `scipy.ndimage.zoom` tanpa handle NaN.
  - Aksi: `np.nan_to_num` sebelum zoom.

- [ ] 6. **`map.js` mendekati batas 300 baris** (296 baris, masih compliant; split opsional)
  - File: `app/static/js/map.js` (296 baris)
  - Masalah: mendekati aturan max 300 baris/file.
  - Aksi: split (mis. results rendering) ke modul terpisah.

- [x] 7. **`resultsTargetLabel` bisa "undefined"** (guarded)
  - File: `app/static/js/map.js`
  - Masalah: `selectedTargetText.split(". ")[1]` tanpa guard.
  - Aksi: tambah fallback ke `selectedTargetText`.

- [x] 8. **`asyncio.get_event_loop()` deprecated** (get_running_loop)
  - File: `app/services/cog.py` (`_read_band`)
  - Masalah: deprecated di Python 3.12 (masih jalan, warning).
  - Aksi: gunakan loop yang sesuai / simpan loop.

- [x] 9. **Dead code `apply_s2_cloud_mask`** (removed)
  - File: `app/services/geospatial.py`
  - Masalah: tidak terpakai (YAGNI).
  - Aksi: hapus atau integrasikan ke pipeline.

- [x] 10. **Spacing slope tidak akurat** (cell size from bbox)
  - File: `app/services/geospatial.py` (`calculate_slope_degrees`)
  - Masalah: `np.gradient` dengan `cell_size_meters=30` padahal grid geografis bervariasi.
  - Aksi: hitung spacing dari bbox/shape grid.

## Low / Catatan Desain

- [ ] 11. **Filter `LandTransition` melewati same-class** (accepted design: fokus konversi)
  - File: `app/services/classifier.py` (`compute_land_transition_matrix`)
  - Masalah: menyembunyikan stabilitas lahan.
  - Aksi: evaluasi apakah perlu tampilkan transisi stabil.

- [ ] 12. **GeoTIFF tanpa kompresi** (accepted: 128x128 kecil)
  - File: `app/services/geotiff.py` (`generate_geotiff_raster`)
  - Masalah: ukuran bundle lebih besar (128x128 masih fine).
  - Aksi: opsional tambah compression (LZW/Deflate).

- [ ] 13. **Storage sync blocking di async route** (accepted: query cepat)
  - File: `app/services/storage.py` (`get_db_connection`, `get_analysis_arrays`)
  - Masalah: `get_analysis_arrays` sync dipanggil di async route (blocking); `check_same_thread=True`.
  - Aksi: bungkus di executor atau buat async wrapper.

- [x] 14. **No CORS middleware** (ditambahkan CORSMiddleware)
  - File: `app/main.py`
  - Masalah: jika frontend dipisah domain akan gagal.
  - Aksi: tambah CORS middleware (opsional, same-origin saat ini).

- [x] 15. **FIRMS CSV parsing bisa throw** (safe float parse)
  - File: `app/services/firms.py` (`fetch_active_fires`)
  - Masalah: `frp` non-numeric → exception (route tangkap → 502).
  - Aksi: safe parse dengan fallback 0.0.

- [ ] 16. **Fallback pre arrays = post arrays** (accepted: fallback simulasi)
  - File: `app/routes/api/analysis.py` (`_resolve_spectral`)
  - Masalah: jika `_pre_arrays` hilang, pre=post → transisi stabil.
  - Aksi: dokumentasikan / handle eksplisit.

- [x] 17. **ThreadPoolExecutor tidak di-shutdown** (lifespan shutdown)
  - File: `app/services/cog.py` (`_executor`)
  - Masalah: module-level, tidak di-cleanup.
  - Aksi: cleanup saat shutdown (lifespan).

---

Status legend: `[ ]` pending, `[x]` done.
}
