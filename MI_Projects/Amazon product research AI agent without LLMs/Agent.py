"""
Amazon Product Research Agent - Python Backend
Free Stack: ScraperAPI (free tier) + Groq (free LLaMA 3) + Google Sheets API (free)

Install:
  pip install requests groq google-auth google-auth-oauthlib google-api-python-client beautifulsoup4

Usage:
  python Agent.py --keywords "smartphone" --price-min 300 --price-max 700
"""

import argparse, json, os, csv, time, re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ──────────────────────────────────────────────
# CONFIG — API keys loaded from environment
# ──────────────────────────────────────────────
SCRAPER_API_KEY    = os.getenv("SCRAPER_API_KEY", "")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
RAINFOREST_API_KEY = os.getenv("RAINFOREST_API_KEY", "")
# GOOGLE_SHEETS_ID   = os.getenv("GOOGLE_SHEETS_ID",   "1YjISkW7HomQVgQnv_vzjTTs1I1-C9fTetQiJ8w50nNI")  # Fixed: d/ hata diya

# ──────────────────────────────────────────────
# STEP 1: SCRAPE AMAZON
# ──────────────────────────────────────────────
def search_amazon_scraperapi(keywords: str, pages: int = 2) -> list[dict]:
    if not SCRAPER_API_KEY:
        print("[WARN] No SCRAPER_API_KEY — returning demo data")
        return get_demo_products()

    products = []
    for page in range(1, pages + 1):
        amazon_url = f"https://www.amazon.com/s?k={requests.utils.quote(keywords)}&page={page}"
        proxy_url  = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={requests.utils.quote(amazon_url)}&render=true"
        print(f"[SCRAPE] Page {page}: {amazon_url}")
        try:
            resp = requests.get(proxy_url, timeout=60)
            resp.raise_for_status()
            products.extend(parse_amazon_search_html(resp.text))
            time.sleep(1)
        except Exception as e:
            print(f"[ERR] ScraperAPI error: {e}")
    return products


def search_amazon_rainforest(keywords: str, limit: int = 20, api_key: str = None) -> list[dict]:
    key = api_key or RAINFOREST_API_KEY
    if not key:
        return search_amazon_scraperapi(keywords)

    url = "https://api.rainforestapi.com/request"
    params = {
        "api_key":      key,
        "type":         "search",
        "amazon_domain":"amazon.com",
        "search_term":  keywords,
        "sort_by":      "featured",
    }
    print(f"[API] RainforestAPI search: {keywords}")
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        req_info = data.get("request_info", {})
        if req_info.get("success") is False:
            print(f"[ERR] RainforestAPI key issue: {req_info.get('message', 'Request failed')}")
            print("[FALLBACK] Trying ScraperAPI...")
            return search_amazon_scraperapi(keywords)
    except Exception as e:
        print(f"[ERR] RainforestAPI failed: {e}")
        print("[FALLBACK] Trying ScraperAPI...")
        return search_amazon_scraperapi(keywords)

    products = []
    for item in data.get("search_results", []):
        asin = (item.get("asin") or "").strip()
        title = (item.get("title") or "").strip()

        # Skip sponsored containers, video ads, or empty placeholders without ASIN or title
        if not asin or not title:
            continue

        # Extract price
        price_val = 0
        p_data = item.get("price")
        if isinstance(p_data, dict):
            price_val = p_data.get("value", 0) or p_data.get("amount", 0)
        elif isinstance(p_data, (int, float)):
            price_val = float(p_data)
        elif item.get("prices") and isinstance(item.get("prices"), list) and len(item.get("prices")) > 0:
            price_val = item.get("prices")[0].get("value", 0)

        # Extract rating
        rating_val = item.get("rating") or item.get("stars") or item.get("rating_star") or 0

        # Extract reviews count
        reviews_val = 0
        r_total = (
            item.get("ratings_total") or
            item.get("reviews_total") or
            item.get("rating_count") or
            item.get("total_ratings") or
            item.get("ratings_count") or
            item.get("rating_number")
        )
        if r_total:
            reviews_val = r_total
        elif isinstance(item.get("reviews"), int):
            reviews_val = item.get("reviews")
        elif isinstance(item.get("reviews"), dict):
            reviews_val = item.get("reviews", {}).get("total", 0) or item.get("reviews", {}).get("count", 0)
        elif isinstance(item.get("ratings"), int):
            reviews_val = item.get("ratings")

        # Extract BSR rank
        bsr_val = 0
        bsr_data = item.get("bestsellers_rank") or item.get("bestseller_rank")
        if isinstance(bsr_data, list) and len(bsr_data) > 0:
            bsr_val = bsr_data[0].get("rank", 0) if isinstance(bsr_data[0], dict) else 0
        elif isinstance(bsr_data, dict):
            bsr_val = bsr_data.get("rank", 0)
        elif isinstance(bsr_data, (int, float)):
            bsr_val = int(bsr_data)
        else:
            bsr_val = item.get("bsr") or item.get("rank") or item.get("position") or 0

        # Extract image URL
        img_val = (
            item.get("image") or
            item.get("image_url") or
            item.get("thumbnail") or
            item.get("link_image") or
            ""
        )
        if not img_val and isinstance(item.get("main_image"), dict):
            img_val = item.get("main_image", {}).get("link", "")
        elif not img_val and isinstance(item.get("main_image"), str):
            img_val = item.get("main_image")

        # Extract category name
        cat_val = "General"
        if item.get("categories") and isinstance(item.get("categories"), list) and len(item.get("categories")) > 0:
            cat_val = item.get("categories")[0].get("name", "General")

        products.append({
            "asin":        asin,
            "title":       title[:150],
            "price":       float(price_val or 0),
            "rating":      float(rating_val or 0),
            "reviews":     int(reviews_val or 0),
            "bsr":         int(bsr_val or 0),
            "category":    cat_val,
            "image":       img_val,
            "url":         item.get("link") or f"https://www.amazon.com/dp/{asin}",
            "fba":         True,
            "competition": "medium",
            "weight":      "N/A",
        })

        if len(products) >= limit:
            break

    if not products:
        print("[WARN] RainforestAPI returned no results — falling back to demo data")
        return get_demo_products(keywords)
    return products


def parse_amazon_search_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for el in soup.select("[data-asin]"):
        asin = el.get("data-asin", "")
        if not asin or len(asin) != 10:
            continue
        title_el   = el.select_one("h2 a span") or el.select_one("[class*='a-text-normal']")
        price_el   = el.select_one("[class*='a-price'] [class*='a-offscreen']") or el.select_one(".a-price-whole")
        rating_el  = el.select_one("[class*='a-icon-star-small'] span") or el.select_one("i[class*='a-star'] span")
        reviews_el = el.select_one("[class*='a-size-base'][class*='s-underline-text']")
        img_el     = el.select_one("img.s-image")
        if not title_el:
            continue
        price_txt = price_el.get_text(strip=True) if price_el else "0"
        price = float(re.sub(r"[^\d.]", "", price_txt) or 0)
        rating_txt = rating_el.get_text(strip=True) if rating_el else "4.0"
        rating = float(re.search(r"[\d.]+", rating_txt).group() if re.search(r"[\d.]+", rating_txt) else 4.0)
        reviews_txt = reviews_el.get_text(strip=True) if reviews_el else "0"
        reviews = int(re.sub(r"[^\d]", "", reviews_txt) or 0)
        img_src = img_el.get("src", "") if img_el else ""
        products.append({
            "asin":        asin,
            "title":       title_el.get_text(strip=True)[:150],
            "price":       price,
            "rating":      rating,
            "reviews":     reviews,
            "bsr":         0,
            "category":    "General",
            "image":       img_src,
            "url":         f"https://www.amazon.com/dp/{asin}",
            "fba":         True,
            "competition": "medium",
            "weight":      "N/A",
        })
    return products


# ──────────────────────────────────────────────
# STEP 2: SCORE PRODUCTS
# ──────────────────────────────────────────────
def score_product(product: dict, criteria: dict) -> dict:
    score = 0
    reasons = []
    p = product

    if criteria.get("price_min") and p["price"] < criteria["price_min"]:
        reasons.append(f"✗ Price ${p['price']:.2f} below min ${criteria['price_min']:.2f}")
    elif criteria.get("price_max") and p["price"] > criteria["price_max"]:
        reasons.append(f"✗ Price ${p['price']:.2f} above max ${criteria['price_max']:.2f}")
    elif p["price"] > 0:
        score += 25
        reasons.append(f"✓ Price ${p['price']:.2f} in range")

    if p["rating"] >= criteria.get("min_rating", 4.0):
        score += 20
        reasons.append(f"✓ Rating {p['rating']}★ meets threshold")
    else:
        reasons.append(f"✗ Rating {p['rating']}★ below {criteria.get('min_rating', 4.0)}★")

    if p["reviews"] >= criteria.get("min_reviews", 100):
        score += 20
        reasons.append(f"✓ {p['reviews']:,} reviews meets threshold")
    else:
        reasons.append(f"✗ Only {p['reviews']:,} reviews (need {criteria.get('min_reviews', 100):,})")

    if p["bsr"] > 0 and p["bsr"] <= criteria.get("max_bsr", 100000) and p["bsr"] < 999999:
        score += 20
        reasons.append(f"✓ BSR #{p['bsr']:,} is acceptable")
    elif p["bsr"] == 0 or p["bsr"] >= 999999:
        score += 10
        reasons.append("~ BSR unknown")
    else:
        reasons.append(f"✗ BSR #{p['bsr']:,} too high")

    if not criteria.get("category") or criteria["category"].lower() in p["category"].lower():
        score += 15

    if p.get("fba"):
        score += 5
        reasons.append("✓ FBA eligible")

    match_status = "match" if score >= 75 else "partial" if score >= 45 else "nomatch"
    return {**p, "score": min(score, 100), "reasons": reasons, "status": match_status}


# ──────────────────────────────────────────────
# STEP 3: AI ANALYSIS — FIXED MODEL
# ──────────────────────────────────────────────
def analyze_with_groq(products: list[dict], criteria: dict) -> list[dict]:
    if not GROQ_API_KEY:
        print("[WARN] No GROQ_API_KEY — skipping AI analysis")
        return products

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        for p in products[:5]:
            prompt = (
                f"Amazon FBA research. Product: '{p['title'][:80]}', "
                f"Price: ${p['price']:.2f}, Rating: {p['rating']}★, "
                f"Reviews: {p['reviews']:,}, BSR: #{p['bsr']:,}. "
                f"Criteria: price ${criteria.get('price_min','any')}-${criteria.get('price_max','any')}, "
                f"extra notes: {criteria.get('extra','none')}. "
                f"In ONE sentence (max 25 words), is this a good FBA opportunity?"
            )
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",   # ✅ FIXED: Naya model
                messages=[{"role": "user", "content": prompt}],
                max_tokens=60
            )
            p["ai_note"] = response.choices[0].message.content.strip()
            time.sleep(0.2)
    except Exception as e:
        print(f"[ERR] Groq analysis failed: {e}")

    return products


# ──────────────────────────────────────────────
# STEP 4: OUTPUT
# ──────────────────────────────────────────────
def export_to_csv(products: list[dict], filename: str = None) -> str:
    if not filename:
        filename = f"amazon_research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = ["ASIN","Title","Price","Rating","Reviews","BSR","Category","FBA","Score","Status","AI Note","URL"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for p in products:
            w.writerow([
                p.get("asin",""), p.get("title",""), f"${p.get('price',0):.2f}",
                p.get("rating",0), p.get("reviews",0), p.get("bsr",0),
                p.get("category",""), "Yes" if p.get("fba") else "No",
                p.get("score",0), p.get("status",""), p.get("ai_note",""), p.get("url","")
            ])
    print(f"[OUT] CSV saved: {filename}")
    return filename


def export_to_google_sheets(products: list[dict], spreadsheet_id: str):
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            "service_account.json",
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        sheet   = service.spreadsheets()

        values = [["ASIN","Title","Price","Rating","Reviews","BSR","Category","FBA","Score","Status","AI Note","URL"]]
        for p in products:
            values.append([
                p.get("asin",""), p.get("title",""), p.get("price",0),
                p.get("rating",0), p.get("reviews",0), p.get("bsr",0),
                p.get("category",""), "Yes" if p.get("fba") else "No",
                p.get("score",0), p.get("status",""), p.get("ai_note",""), p.get("url","")
            ])

        sheet.values().clear(spreadsheetId=spreadsheet_id, range="Sheet1").execute()
        sheet.values().update(
            spreadsheetId=spreadsheet_id, range="Sheet1!A1",
            valueInputOption="RAW", body={"values": values}
        ).execute()
        print(f"[OUT] Google Sheets updated!")
    except Exception as e:
        print(f"[ERR] Google Sheets export failed: {e}")


# ──────────────────────────────────────────────
# DEMO DATA — 50+ products across all categories
# ──────────────────────────────────────────────
ALL_DEMO_PRODUCTS = [
    # Home & Kitchen — Curtains / Window
    {"asin":"B08KJ7WKPT","title":"NICETOWN Blackout Curtains 52x84 Inch Thermal Insulated Grommet Curtain Panels","price":24.99,"rating":4.5,"reviews":18420,"bsr":320,"category":"Home & Kitchen","fba":True,"competition":"medium","weight":"2.1 lbs","image":"https://images.unsplash.com/photo-1513694203232-719a280e022f?w=200","url":"https://amazon.com/dp/B08KJ7WKPT"},
    {"asin":"B07XQKJ6YP","title":"BGment Blackout Curtains for Bedroom 52x63 Inch Thermal Insulated Room Darkening","price":19.99,"rating":4.4,"reviews":24800,"bsr":285,"category":"Home & Kitchen","fba":True,"competition":"high","weight":"1.9 lbs","image":"https://images.unsplash.com/photo-1513694203232-719a280e022f?w=200","url":"https://amazon.com/dp/B07XQKJ6YP"},
    {"asin":"B09LMRK6WT","title":"Deconovo Curtains 2 Panels Set 52x96 Inch Silver Grommet Window Curtains","price":32.99,"rating":4.6,"reviews":9200,"bsr":512,"category":"Home & Kitchen","fba":True,"competition":"medium","weight":"2.4 lbs","image":"https://images.unsplash.com/photo-1513694203232-719a280e022f?w=200","url":"https://amazon.com/dp/B09LMRK6WT"},
    # Kitchen — Cups & Mugs
    {"asin":"B08KJLMP9X","title":"Lamosi Coffee Cups 12 oz 120 Pack Disposable Paper Coffee Cups Insulated","price":28.99,"rating":4.6,"reviews":8450,"bsr":410,"category":"Home & Kitchen","fba":True,"competition":"medium","weight":"2.5 lbs","image":"https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=200","url":"https://amazon.com/dp/B08KJLMP9X"},
    {"asin":"B07XQTRP4M","title":"Turbo Bee 16 oz Clear Plastic Cups 300 Count Disposable Party Cups","price":26.99,"rating":4.7,"reviews":14200,"bsr":290,"category":"Home & Kitchen","fba":True,"competition":"medium","weight":"3.1 lbs","image":"https://images.unsplash.com/photo-1577968897966-3d4325b36b61?w=200","url":"https://amazon.com/dp/B07XQTRP4M"},
    {"asin":"B09LMNPB8W","title":"SIUQ 600 Pack 9 oz Plastic Cups Clear Disposable Water Cups","price":24.99,"rating":4.6,"reviews":9800,"bsr":530,"category":"Home & Kitchen","fba":True,"competition":"low","weight":"2.8 lbs","image":"https://images.unsplash.com/photo-1577968897966-3d4325b36b61?w=200","url":"https://amazon.com/dp/B09LMNPB8W"},
    # Home & Kitchen — Doors & Hardware
    {"asin":"B08SMTDOR1","title":"SMARTSTANDARD 36in x 84in Sliding Barn Door with Hardware Kit Included","price":129.99,"rating":4.5,"reviews":6400,"bsr":820,"category":"Tools & Home Improvement","fba":True,"competition":"medium","weight":"42 lbs","image":"https://images.unsplash.com/photo-1513694203232-719a280e022f?w=200","url":"https://amazon.com/dp/B08SMTDOR1"},
    # Electronics — Smartphones / Accessories
    {"asin":"B09G9D8KRQ","title":"Anker 20W USB C Charger Fast Charging Wall Charger for iPhone 13 Samsung","price":15.99,"rating":4.7,"reviews":52000,"bsr":45,"category":"Electronics","fba":True,"competition":"high","weight":"0.2 lbs","image":"https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=200","url":"https://amazon.com/dp/B09G9D8KRQ"},
    {"asin":"B09KLMN7XT","title":"Spigen Tempered Glass Screen Protector for Samsung Galaxy S22 2-Pack","price":9.99,"rating":4.5,"reviews":38100,"bsr":112,"category":"Electronics","fba":True,"competition":"high","weight":"0.1 lbs","image":"https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=200","url":"https://amazon.com/dp/B09KLMN7XT"},
    {"asin":"B08N5M9XKL","title":"Bluetooth Earbuds Wireless Headphones 48H Playtime IPX7 Waterproof Sport Earphones","price":29.99,"rating":4.4,"reviews":15300,"bsr":230,"category":"Electronics","fba":True,"competition":"high","weight":"0.3 lbs","image":"https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=200","url":"https://amazon.com/dp/B08N5M9XKL"},
    # Sports & Outdoors
    {"asin":"B09XKT5FMZ","title":"TOPLUS Yoga Mat Non Slip 1/4 inch TPE Thick Exercise Mat","price":32.99,"rating":4.6,"reviews":8420,"bsr":312,"category":"Sports & Outdoors","fba":True,"competition":"medium","weight":"2.2 lbs","image":"https://images.unsplash.com/photo-1601925260368-ae2f83cf8b7f?w=200","url":"https://amazon.com/dp/B09XKT5FMZ"},
    {"asin":"B08C4K9L2D","title":"Resistance Bands Set 5 Pack Loop Exercise Bands for Legs and Glutes","price":16.99,"rating":4.5,"reviews":22400,"bsr":189,"category":"Sports & Outdoors","fba":True,"competition":"high","weight":"0.5 lbs","image":"https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=200","url":"https://amazon.com/dp/B08C4K9L2D"},
    {"asin":"B07WQTM3PN","title":"Water Bottle 32oz Stainless Steel Insulated Sports Bottle BPA Free","price":22.99,"rating":4.7,"reviews":34000,"bsr":145,"category":"Sports & Outdoors","fba":True,"competition":"high","weight":"0.7 lbs","image":"https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=200","url":"https://amazon.com/dp/B07WQTM3PN"},
    {"asin":"B09P7XTNB2","title":"Adjustable Dumbbell Set 25LB Single Dumbbell for Home Gym Workout","price":89.99,"rating":4.4,"reviews":5600,"bsr":780,"category":"Sports & Outdoors","fba":True,"competition":"medium","weight":"25 lbs","image":"https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=200","url":"https://amazon.com/dp/B09P7XTNB2"},
    # Home & Kitchen — General
    {"asin":"B08N5M7S6K","title":"Bamboo Kitchen Drawer Organizer Adjustable Dividers Set of 4","price":28.49,"rating":4.7,"reviews":5210,"bsr":891,"category":"Home & Kitchen","fba":True,"competition":"low","weight":"1.8 lbs","image":"https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=200","url":"https://amazon.com/dp/B08N5M7S6K"},
    {"asin":"B07VGRJDQY","title":"Eco-Friendly Reusable Produce Bags Mesh Washable Set of 9","price":14.99,"rating":4.5,"reviews":12800,"bsr":445,"category":"Home & Kitchen","fba":True,"competition":"high","weight":"0.4 lbs","image":"https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=200","url":"https://amazon.com/dp/B07VGRJDQY"},
    {"asin":"B08P4RMGPL","title":"Stainless Steel Measuring Cups and Spoons Set 14-Piece Kitchen Baking","price":21.99,"rating":4.8,"reviews":3890,"bsr":1102,"category":"Home & Kitchen","fba":True,"competition":"medium","weight":"1.1 lbs","image":"https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=200","url":"https://amazon.com/dp/B08P4RMGPL"},
    {"asin":"B07TK2NTLD","title":"Magnetic Knife Strip Holder Stainless Steel Wall Mount 16 inch Kitchen","price":26.99,"rating":4.6,"reviews":4100,"bsr":760,"category":"Home & Kitchen","fba":True,"competition":"low","weight":"1.2 lbs","image":"https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=200","url":"https://amazon.com/dp/B07TK2NTLD"},
    # Beauty & Personal Care
    {"asin":"B08RVTLF7N","title":"Vitamin C Face Serum with Hyaluronic Acid Brightening Anti-Aging Skin Care","price":18.99,"rating":4.4,"reviews":28900,"bsr":210,"category":"Beauty & Personal Care","fba":True,"competition":"high","weight":"0.2 lbs","image":"https://images.unsplash.com/photo-1556228720-195a672e8a03?w=200","url":"https://amazon.com/dp/B08RVTLF7N"},
    {"asin":"B09BKRQ5MT","title":"Jade Roller and Gua Sha Set Face Roller Skin Care Facial Massage Tool","price":12.99,"rating":4.5,"reviews":42000,"bsr":156,"category":"Beauty & Personal Care","fba":True,"competition":"high","weight":"0.3 lbs","image":"https://images.unsplash.com/photo-1556228720-195a672e8a03?w=200","url":"https://amazon.com/dp/B09BKRQ5MT"},
    # Pet Supplies
    {"asin":"B07XQKL9VW","title":"Monitor Stand Riser with USB Hub 4 Ports Adjustable Desk Organizer Storage","price":42.99,"rating":4.5,"reviews":6800,"bsr":670,"category":"Office Products","fba":True,"competition":"low","weight":"2.8 lbs","image":"","url":"https://amazon.com/dp/B07XQKL9VW"},
    # Toys & Games
    {"asin":"B08KGJK9RT","title":"Kinetic Sand 6lbs Beach Sand for Kids 3+ Sensory Play Sandbox Toy","price":19.99,"rating":4.6,"reviews":14500,"bsr":280,"category":"Toys & Games","fba":True,"competition":"medium","weight":"6 lbs","image":"","url":"https://amazon.com/dp/B08KGJK9RT"},
    {"asin":"B09NPLM4KS","title":"LEGO Classic Creative Color Fun 90 Pieces Building Toy for Kids Ages 5+","price":14.99,"rating":4.8,"reviews":9700,"bsr":195,"category":"Toys & Games","fba":True,"competition":"high","weight":"0.8 lbs","image":"","url":"https://amazon.com/dp/B09NPLM4KS"},
    # Clothing
    {"asin":"B09QML5RKP","title":"Women High Waist Yoga Pants Leggings 4-Way Stretch Tummy Control Workout","price":28.99,"rating":4.5,"reviews":31000,"bsr":170,"category":"Clothing","fba":True,"competition":"high","weight":"0.5 lbs","image":"","url":"https://amazon.com/dp/B09QML5RKP"},
    {"asin":"B08NVT7RKJ","title":"Men's Running Shorts 5 inch Quick Dry Athletic Gym Workout Shorts with Pockets","price":19.99,"rating":4.4,"reviews":8200,"bsr":490,"category":"Clothing","fba":True,"competition":"medium","weight":"0.3 lbs","image":"","url":"https://amazon.com/dp/B08NVT7RKJ"},
    # Tools & Home Improvement
    {"asin":"B08RSTUVWX","title":"Command Strips Large Heavy Duty Picture Hanging Strips No Damage Walls 16 Pairs","price":11.99,"rating":4.6,"reviews":67000,"bsr":90,"category":"Tools & Home Improvement","fba":True,"competition":"high","weight":"0.2 lbs","image":"","url":"https://amazon.com/dp/B08RSTUVWX"},
    {"asin":"B09DRLLPQT","title":"Digital Measuring Tape 150ft Laser Distance Meter with Backlit LCD USB Charging","price":45.99,"rating":4.4,"reviews":3200,"bsr":1560,"category":"Tools & Home Improvement","fba":True,"competition":"low","weight":"0.4 lbs","image":"","url":"https://amazon.com/dp/B09DRLLPQT"},
]


def get_demo_products(keywords: str = "") -> list[dict]:
    """Return demo products filtered by keyword if provided."""
    if not keywords:
        return ALL_DEMO_PRODUCTS[:10]

    kw_list = [w.lower() for w in keywords.split() if len(w) >= 2]
    if not kw_list:
        return ALL_DEMO_PRODUCTS[:10]

    # Score each product by keyword relevance
    scored = []
    for p in ALL_DEMO_PRODUCTS:
        text = (p["title"] + " " + p["category"]).lower()
        hits = sum(1 for k in kw_list if k in text)
        scored.append((hits, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score = scored[0][0]

    # Return products that matched at least one keyword, else all
    if best_score > 0:
        matched = [p for hits, p in scored if hits > 0]
        return matched if matched else ALL_DEMO_PRODUCTS[:10]
    return ALL_DEMO_PRODUCTS[:10]


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Amazon Product Research Agent")
    parser.add_argument("--keywords",    default="smartphone",  help="Product keywords to search")
    parser.add_argument("--price-min",   type=float, default=0,      help="Min price USD")
    parser.add_argument("--price-max",   type=float, default=9999,   help="Max price USD")
    parser.add_argument("--min-rating",  type=float, default=4.0,    help="Min star rating")
    parser.add_argument("--min-reviews", type=int,   default=100,    help="Min review count")
    parser.add_argument("--max-bsr",     type=int,   default=100000, help="Max BSR rank")
    parser.add_argument("--category",    default="",   help="Amazon category filter")
    parser.add_argument("--extra",       default="",   help="Extra criteria notes for AI")
    parser.add_argument("--pages",       type=int, default=2, help="Pages to scrape")
    parser.add_argument("--output",      default="csv", choices=["csv","sheets","both"])
    parser.add_argument("--no-ai",       action="store_true", help="Skip AI analysis")
    args = parser.parse_args()

    criteria = {
        "keywords":    args.keywords,
        "price_min":   args.price_min,
        "price_max":   args.price_max,
        "min_rating":  args.min_rating,
        "min_reviews": args.min_reviews,
        "max_bsr":     args.max_bsr,
        "category":    args.category,
        "extra":       args.extra,
    }

    print(f"\n{'='*55}")
    print(f"  Amazon Research Agent — Free Stack")
    print(f"{'='*55}")
    print(f"  Keywords : {args.keywords}")
    print(f"  Price    : ${args.price_min} – ${args.price_max}")
    print(f"  Rating   : ≥ {args.min_rating}★")
    print(f"  Reviews  : ≥ {args.min_reviews:,}")
    print(f"  Max BSR  : #{args.max_bsr:,}")
    print(f"{'='*55}\n")

    print("[1/4] Fetching products from Amazon...")
    try:
        if RAINFOREST_API_KEY:
            products = search_amazon_rainforest(args.keywords)
        else:
            products = search_amazon_scraperapi(args.keywords, pages=args.pages)
    except Exception as e:
        print(f"[ERR] Fetching failed: {e}")
        print("[FALLBACK] Using demo products")
        products = get_demo_products()
    print(f"      Found {len(products)} raw products")

    print("[2/4] Scoring products against criteria...")
    scored = [score_product(p, criteria) for p in products]
    scored.sort(key=lambda x: x["score"], reverse=True)
    matches  = sum(1 for p in scored if p["status"] == "match")
    partials = sum(1 for p in scored if p["status"] == "partial")
    print(f"      {matches} strong matches, {partials} partial matches")

    if not args.no_ai:
        print("[3/4] Running AI analysis (Groq LLaMA 3.3)...")
        scored = analyze_with_groq(scored, criteria)
    else:
        print("[3/4] AI analysis skipped (--no-ai flag)")

    print("[4/4] Exporting results...")
    if args.output in ("csv", "both"):
        export_to_csv(scored)
    if args.output in ("sheets", "both") and GOOGLE_SHEETS_ID:
        export_to_google_sheets(scored, GOOGLE_SHEETS_ID)

    print(f"\n{'─'*75}")
    print(f"{'#':<3} {'Score':>5} {'Status':<8} {'Price':>7} {'Rating':>6} {'Reviews':>8}  Title")
    print(f"{'─'*75}")
    for i, p in enumerate(scored[:15], 1):
        status_sym = "✓" if p["status"]=="match" else "~" if p["status"]=="partial" else "✗"
        print(f"{i:<3} {p['score']:>4}% {status_sym:<8} ${p['price']:>6.2f} {p['rating']:>6}★ {p['reviews']:>8,}  {p['title'][:40]}")
    print(f"{'─'*75}")
    print(f"\nDone! {len(scored)} products analyzed.\n")


if __name__ == "__main__":
    main()