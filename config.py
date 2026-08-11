"""
Nike Consumer Intelligence Platform - Configuration
"""

PLATFORM_TITLE    = "Nike Consumer Intelligence Platform"
PLATFORM_SUBTITLE = "Competitive Analytics & Consumer Recovery Intelligence"
PLATFORM_ICON     = "👟"
APP_NAME          = "Nike"
PRIMARY_BRAND_ID  = "nike"

GROQ_MODEL = "llama-3.3-70b-versatile"

DATA_DIR       = "data"
REVIEWS_CSV    = "data/reviews.csv"
BUSINESSES_CSV = "data/businesses.csv"

# ── All brands tracked (Nike + key competitors) ───────────────────────────────
# Verify App Store IDs at: apps.apple.com/us/app/<name>/id<ID>
BRANDS = [
    {
        "brand_id":     "nike",
        "name":         "Nike",
        "app_store_id": "1095459556",
        "color":        "#FF6B35",
        "keywords":     ["Nike store", "Nike outlet store"],
        "is_primary":   True,
    },
    {
        "brand_id":     "on_running",
        "name":         "On Running",
        "app_store_id": "1043400401",   # On - Cloud Running Shoes
        "color":        "#00B4D8",
        "keywords":     [],
        "is_primary":   False,
    },
    {
        "brand_id":     "hoka",
        "name":         "HOKA",
        "app_store_id": "1493519917",   # HOKA
        "color":        "#FFB703",
        "keywords":     [],
        "is_primary":   False,
    },
    {
        "brand_id":     "new_balance",
        "name":         "New Balance",
        "app_store_id": "863036925",    # New Balance Run
        "color":        "#6A4C93",
        "keywords":     [],
        "is_primary":   False,
    },
]

APP_COUNTRY      = "us"
MAX_REVIEW_PAGES = 10

GOOGLE_MAX_LOCATIONS   = 200
GOOGLE_REVIEWS_PER_LOC = 5

ANOMALY_THRESHOLD_STARS = 0.4
SIGNIFICANT_DELTA_STARS = 0.15
PEER_GROUP_COLUMN       = "state"

# ── Defection signals - language patterns indicating consumers switching away ──
DEFECTION_KEYWORDS = [
    "switched to", "switching to", "moved to", "going with",
    "bought on running", "trying on running", "on running instead", "on cloud instead",
    "bought hoka", "trying hoka", "hoka instead", "switched to hoka",
    "new balance instead", "adidas instead", "asics instead", "brooks instead",
    "returned my nike", "returning these nikes", "returning my nikes",
    "last pair of nikes", "last nike", "never buying nike again",
    "used to love nike", "nike has gone downhill", "nike quality has dropped",
    "not the nike i knew", "disappointed in nike", "not worth the price anymore",
    "cheaper alternatives", "better options out there",
]

# ── Product category keywords for classifying reviews ─────────────────────────
PRODUCT_CATEGORIES = {
    "Running": [
        "running", "marathon", "half marathon", "5k", "10k", "trail",
        "road running", "pace", "mileage", "pegasus", "vomero", "zoom fly",
        "invincible", "structure", "react infinity", "run club", "nrc",
    ],
    "Training": [
        "training", "gym", "workout", "cross-training", "hiit",
        "lifting", "metcon", "free trainer", "superrep", "cross fit",
    ],
    "Basketball": [
        "basketball", "court", "jordan", "air jordan", "lebron",
        "kyrie", "giannis", "pg ", "kobe", "dunk",
    ],
    "Lifestyle": [
        "casual", "everyday", "streetwear", "fashion", "style",
        "air force 1", "air max", "blazer", "cortez", "dunk low",
        "going out", "comfortable for walking",
    ],
    "App / Tech": [
        "app", "software", "update", "bug", "crash", "login",
        "account", "glitch", "membership", "nike run club", "nike app",
        "subscription", "sign in", "password",
    ],
}
