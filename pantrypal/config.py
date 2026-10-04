"""Configuration constants and paths for PantryPal."""
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "pantrypal.db"

NUTRITION_PATH = DATA_DIR / "nutrition.json"
RECIPES_PATH = DATA_DIR / "recipes.json"
SUBSTITUTIONS_PATH = DATA_DIR / "substitutions.json"
UNITS_PATH = DATA_DIR / "units.json"
DAILY_VALUES_PATH = DATA_DIR / "daily_values.json"

# LLM / Ollama configuration
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3-vl:4b"
FALLBACK_MODELS = ["qwen2.5:3b-instruct", "llama3.2:3b", "qwen3:4b"]
LLM_TIMEOUT_S = 30
LLM_TEMPERATURE = 0.2
LLM_NUM_CTX = 2048

# Scaling & Optimization bounds
MACRO_TOLERANCE = 0.10        # Max 10% drift for substitutions
SCALE_MIN = 0.5              # Min portion scaling factor
SCALE_MAX = 2.5              # Max portion scaling factor
TOP_K = 5                    # Number of recommendations

# Carnivore fat-to-protein ratio range by weight
CARNIVORE_FAT_PROTEIN_RATIO_MIN = 0.8
CARNIVORE_FAT_PROTEIN_RATIO_MAX = 1.2

# Cooking adjustments: Added oil in grams per serving
COOKING_ADDED_OIL = {
    "air_fry": 4.0,       # light spray
    "pan_fry": 10.0,      # unless recipe fat already declared
    "microwave": 0.0,
    "boil": 0.0,
    "bake": 2.0,
}

# Cooking nutrient retention factors (rough approximations)
COOKING_RETENTION = {
    "boil": {
        "vit_c_mg": 0.70,   # water soluble loss
        "potassium_mg": 0.85,
    }
}

# Standard available utensils
ALL_UTENSILS = [
    "stove",
    "microwave",
    "air_fryer",
    "oven",
    "pressure_cooker",
    "rice_cooker",
    "kettle",
]
