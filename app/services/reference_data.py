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
