CLASS_NAMES = {
    0: "Primary Forest",
    1: "Wet Peatland",
    2: "Bare Land / Cleared",
    3: "Oil Palm Plantation",
    4: "Mining Excavation",
    5: "Water Body",
    6: "Built-up Area",
    7: "Cropland / Agriculture",
}

CLASS_COLORS = {
    0: "#1a5f2a",
    1: "#3f7f5f",
    2: "#b08968",
    3: "#7fb069",
    4: "#6b6b6b",
    5: "#1f5f8b",
    6: "#d62728",
    7: "#e0c341",
    -1: "#000000",
}

FEATURES = ["ndvi", "ndwi", "nbr", "bsi"]

INDEX_SERIES = [
    {"key": "ndvi", "label": "NDVI", "color": "#34d399", "unit": ""},
    {"key": "ndwi", "label": "NDWI", "color": "#38bdf8", "unit": ""},
    {"key": "mndwi", "label": "MNDWI", "color": "#2dd4bf", "unit": ""},
    {"key": "ndmi", "label": "NDMI", "color": "#facc15", "unit": ""},
    {"key": "nbr", "label": "NBR", "color": "#f87171", "unit": ""},
    {"key": "bsi", "label": "BSI", "color": "#cbd5e1", "unit": ""},
    {"key": "dnbr", "label": "dNBR", "color": "#fb923c", "unit": ""},
    {"key": "sar", "label": "SAR VH-VV", "color": "#a78bfa", "unit": "dB"},
    {"key": "lst", "label": "LST", "color": "#f472b6", "unit": "\u00b0C"},
]

INDEX_COLORS = {row["key"]: row["color"] for row in INDEX_SERIES}

UNITLESS_KEYS = [row["key"] for row in INDEX_SERIES if not row["unit"]]

ANALYSIS_TARGETS = [
    "peat_moisture",
    "topography_slope",
    "forest_to_bare",
    "forest_to_mining",
    "forest_to_palm",
    "deforest_expansion",
    "reclamation",
    "bare_to_veg",
    "wildfire_dnbr",
    "water_dynamics",
    "peat_drainage_canal",
    "carbon_subsidence",
    "coastal_inundation",
    "landslide_susceptibility",
    "ground_deformation",
    "urban_expansion",
    "cropland_expansion",
    "peat_restoration",
    "seasonal_flooding",
    "biodiversity_habitat",
]
