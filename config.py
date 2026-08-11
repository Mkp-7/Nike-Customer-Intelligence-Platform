BRAND_NAME   = "Nike"
APP_NAME     = BRAND_NAME
KEYWORDS     = [
    "Nike store",
    "Nike outlet store",
]
APP_STORE_ID = "1095459556"
APP_COUNTRY  = "us"
PLATFORM_TITLE    = "Nike Intelligence Platform"
PLATFORM_SUBTITLE = "Customer Insights & Merchandising Analytics"
PLATFORM_ICON     = "👟"
GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_REVIEW_PAGES = 10
DATA_DIR       = "data"
REVIEWS_CSV    = "data/reviews.csv"
BUSINESSES_CSV = "data/businesses.csv"
ANOMALY_THRESHOLD_STARS = 0.4
SIGNIFICANT_DELTA_STARS = 0.15

# Required by main_app.py
BRANDS = [
    {
        "brand_id":     "nike",
        "name":         "Nike",
        "app_store_id": APP_STORE_ID,
        "keywords":     KEYWORDS,
    }
]
GOOGLE_MAX_LOCATIONS   = 200
GOOGLE_REVIEWS_PER_LOC = 5
PEER_GROUP_COLUMN      = "state"
