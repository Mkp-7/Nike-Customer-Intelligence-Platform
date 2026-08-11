"""
Smart Data Extractor - Multi-Brand
App Store (iTunes RSS) + Google Maps (Places API)
Scrapes Nike + all competitor brands defined in config.BRANDS
"""
import os, sys, csv, json, time, re, hashlib
import urllib.request, urllib.parse, urllib.error
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    BRANDS, APP_COUNTRY, MAX_REVIEW_PAGES,
    GOOGLE_MAX_LOCATIONS, GOOGLE_REVIEWS_PER_LOC,
    DATA_DIR, REVIEWS_CSV, BUSINESSES_CSV,
)

GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

REVIEW_FIELDS = [
    "review_id", "brand_id", "brand_name", "stars", "date", "title", "text",
    "source", "version", "vote_count",
    "place_name", "address", "city", "state",
    "latitude", "longitude", "google_rating", "total_reviews_at_location",
]

BIZ_FIELDS = [
    "business_id", "brand_id", "brand_name", "name",
    "address", "city", "state", "postal_code",
    "latitude", "longitude", "stars", "review_count", "is_open", "source",
]

US_STATES = [
    "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut",
    "Delaware","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa",
    "Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts","Michigan",
    "Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada",
    "New Hampshire","New Jersey","New Mexico","New York","North Carolina",
    "North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island",
    "South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont",
    "Virginia","Washington","West Virginia","Wisconsin","Wyoming",
]


def make_id(*parts) -> str:
    return hashlib.md5("_".join(str(p) for p in parts).encode()).hexdigest()[:16]


def fetch_url(url, timeout=20, retries=3, backoff=5):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            if attempt < retries - 1:
                wait = backoff * (2 ** attempt)
                print(f"      Retry {attempt+1}/{retries-1} after {wait}s ({e})")
                time.sleep(wait)
            else:
                raise


def scrape_app_store(brand: dict) -> list:
    app_id = brand.get("app_store_id", "").strip()
    if not app_id:
        print(f"   [{brand['name']}] App Store: skipped (no app_store_id)")
        return []

    print(f"\n   [{brand['name']}] 📱 App Store (ID: {app_id})...")
    reviews = []

    for page in range(1, MAX_REVIEW_PAGES + 1):
        url = (f"https://itunes.apple.com/{APP_COUNTRY}/rss/customerreviews"
               f"/page={page}/id={app_id}/sortby=mostrecent/json")
        try:
            data    = json.loads(fetch_url(url))
            entries = data.get("feed", {}).get("entry", [])
            if page == 1 and entries:
                entries = entries[1:]
            if not entries:
                if page == 1:
                    print(f"      Page 1 empty - waiting 15s and retrying...")
                    time.sleep(15)
                    data    = json.loads(fetch_url(url))
                    entries = data.get("feed", {}).get("entry", [])
                    if entries:
                        entries = entries[1:]
                if not entries:
                    break
            for e in entries:
                reviews.append({
                    "review_id":  make_id("appstore", app_id, e.get("id",{}).get("label","")),
                    "brand_id":   brand["brand_id"],
                    "brand_name": brand["name"],
                    "stars":      e.get("im:rating",{}).get("label",""),
                    "date":       e.get("updated",{}).get("label","")[:10],
                    "title":      e.get("title",{}).get("label",""),
                    "text":       e.get("content",{}).get("label","").replace("\n"," ").strip(),
                    "source":     "app_store",
                    "version":    e.get("im:version",{}).get("label",""),
                    "vote_count": e.get("im:voteCount",{}).get("label","0"),
                    "place_name": "", "address": "", "city": "", "state": "",
                    "latitude": "", "longitude": "", "google_rating": "",
                    "total_reviews_at_location": "",
                })
            print(f"      Page {page}: {len(entries)} reviews (total: {len(reviews)})")
            time.sleep(1)
        except Exception as ex:
            print(f"      Page {page}: {ex} - stopping.")
            break

    print(f"   [{brand['name']}] App Store: {len(reviews)} reviews ✅")
    return reviews


def places_api(endpoint: str, params: dict) -> dict:
    params["key"] = GOOGLE_PLACES_API_KEY
    url = f"https://maps.googleapis.com/maps/api/place/{endpoint}/json?{urllib.parse.urlencode(params)}"
    return json.loads(fetch_url(url))


def scrape_google_maps(brand: dict) -> tuple:
    keywords = brand.get("keywords", [])
    if not keywords:
        print(f"   [{brand['name']}] Google Maps: skipped (no keywords)")
        return [], []
    if not GOOGLE_PLACES_API_KEY:
        print(f"   [{brand['name']}] Google Maps: skipped (no API key)")
        return [], []

    print(f"\n   [{brand['name']}] 🌍 Google Maps...")
    all_reviews, all_businesses = [], []
    seen_place_ids = set()

    for keyword in keywords:
        for state in US_STATES:
            if len(seen_place_ids) >= GOOGLE_MAX_LOCATIONS:
                break
            query = f"{keyword} {state} USA"
            try:
                results = places_api("textsearch", {"query": query, "region": "us"}).get("results", [])
            except Exception as e:
                print(f"      Warning: {state}: {e}")
                continue

            for place in results:
                if len(seen_place_ids) >= GOOGLE_MAX_LOCATIONS:
                    break
                place_id = place.get("place_id")
                if not place_id or place_id in seen_place_ids:
                    continue
                seen_place_ids.add(place_id)

                try:
                    det = places_api("details", {
                        "place_id": place_id,
                        "fields": "name,formatted_address,geometry,rating,"
                                  "user_ratings_total,reviews,address_components,business_status",
                    }).get("result", {})
                except Exception as e:
                    continue

                loc_state = loc_city = loc_zip = country = ""
                for comp in det.get("address_components", []):
                    types = comp.get("types", [])
                    if "administrative_area_level_1" in types: loc_state = comp.get("short_name","")
                    if "locality"    in types: loc_city  = comp.get("long_name","")
                    if "postal_code" in types: loc_zip   = comp.get("long_name","")
                    if "country"     in types: country   = comp.get("short_name","")

                if country and country != "US":
                    continue

                geo    = det.get("geometry", {}).get("location", {})
                biz_id = make_id("google", place_id)

                all_businesses.append({
                    "business_id": biz_id, "brand_id": brand["brand_id"],
                    "brand_name": brand["name"], "name": det.get("name",""),
                    "address": det.get("formatted_address",""),
                    "city": loc_city, "state": loc_state, "postal_code": loc_zip,
                    "latitude": geo.get("lat",""), "longitude": geo.get("lng",""),
                    "stars": det.get("rating",""),
                    "review_count": det.get("user_ratings_total",0),
                    "is_open": 1 if det.get("business_status") == "OPERATIONAL" else 0,
                    "source": "google",
                })

                for r in det.get("reviews", [])[:GOOGLE_REVIEWS_PER_LOC]:
                    date_str = datetime.utcfromtimestamp(r.get("time",0)).strftime("%Y-%m-%d")
                    all_reviews.append({
                        "review_id":  make_id("google", place_id, r.get("author_name",""), date_str),
                        "brand_id":   brand["brand_id"],
                        "brand_name": brand["name"],
                        "stars":      str(r.get("rating","")),
                        "date":       date_str,
                        "title":      "",
                        "text":       r.get("text","").replace("\n"," ").strip(),
                        "source":     "google_maps",
                        "version":    "", "vote_count": str(r.get("likes",0)),
                        "place_name": det.get("name",""),
                        "address":    det.get("formatted_address",""),
                        "city":       loc_city, "state": loc_state,
                        "latitude":   str(geo.get("lat","")),
                        "longitude":  str(geo.get("lng","")),
                        "google_rating":             str(det.get("rating","")),
                        "total_reviews_at_location": str(det.get("user_ratings_total","")),
                    })
                time.sleep(0.2)

    print(f"   [{brand['name']}] Google Maps: {len(all_reviews)} reviews, {len(all_businesses)} locations ✅")
    return all_reviews, all_businesses


def main():
    print("=" * 60)
    print("  Nike Consumer Intelligence - Data Extractor")
    print(f"  Brands: {', '.join(b['name'] for b in BRANDS)}")
    print("=" * 60)

    os.makedirs(DATA_DIR, exist_ok=True)
    all_reviews, all_businesses = [], []

    for brand in BRANDS:
        print(f"\n{'─'*60}")
        print(f"  🏷  {brand['name'].upper()}")
        print(f"{'─'*60}")
        all_reviews.extend(scrape_app_store(brand))
        time.sleep(3)
        rev, biz = scrape_google_maps(brand)
        all_reviews.extend(rev)
        all_businesses.extend(biz)
        time.sleep(5)

    if not all_reviews:
        print("\n⚠️  No reviews collected.")
        sys.exit(1)

    seen, unique_reviews = set(), []
    for r in all_reviews:
        if r["review_id"] not in seen:
            seen.add(r["review_id"])
            unique_reviews.append(r)

    with open(REVIEWS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(unique_reviews)

    seen, unique_biz = set(), []
    for b in all_businesses:
        if b["business_id"] not in seen:
            seen.add(b["business_id"])
            unique_biz.append(b)

    with open(BUSINESSES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BIZ_FIELDS)
        writer.writeheader()
        writer.writerows(unique_biz)

    print(f"\n{'='*60}")
    print(f"✅ {len(unique_reviews):,} reviews  → {REVIEWS_CSV}")
    print(f"✅ {len(unique_biz)} locations → {BUSINESSES_CSV}")
    for brand in BRANDS:
        br    = [r for r in unique_reviews if r["brand_id"] == brand["brand_id"]]
        stars = [float(r["stars"]) for r in br if str(r["stars"]).replace(".","").isdigit()]
        avg   = round(sum(stars)/len(stars),2) if stars else "N/A"
        src   = {}
        for r in br: src[r["source"]] = src.get(r["source"],0) + 1
        if br:
            print(f"   {brand['name']}: {len(br):,} reviews | avg {avg}⭐ | {src}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
