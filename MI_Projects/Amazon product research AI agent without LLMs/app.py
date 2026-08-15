"""
Flask Backend for Amazon Product Research Agent
Run: python app.py
Then open index.html in your browser (or serve with: python -m http.server 8080)
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sys, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Add current directory to path so we can import Agent.py functions
sys.path.insert(0, BASE_DIR)

# Import functions from Agent.py
from Agent import (
    search_amazon_rainforest,
    search_amazon_scraperapi,
    score_product,
    analyze_with_groq,
    get_demo_products,
)

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
CORS(app)  # Allow cross-origin requests from the frontend


# ──────────────────────────────────────────────
# SERVE FRONTEND — localhost:5000 opens index.html
# ──────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/<path:filename>", methods=["GET"])
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)


# ──────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Amazon Research Agent backend is running"})


# ──────────────────────────────────────────────
# MAIN SEARCH ENDPOINT
# ──────────────────────────────────────────────
@app.route("/api/search", methods=["POST"])
def search():
    try:
        body = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON body"}), 400

    # ── Extract request params ──────────────────
    keywords       = (body.get("keywords") or "").strip()
    price_min      = body.get("price_min")   # may be None
    price_max      = body.get("price_max")   # may be None
    min_rating     = float(body.get("min_rating",  4.0))
    min_reviews    = int(body.get("min_reviews",   100))
    max_bsr        = int(body.get("max_bsr",       100000))
    category       = body.get("category",          "")
    limit          = int(body.get("limit",         20))
    extra          = body.get("extra",             "")
    skip_ai        = body.get("skip_ai",           False)

    # API keys passed from browser localStorage
    rainforest_key = body.get("rainforest_key", "").strip()
    scraper_key    = body.get("scraper_key",    "").strip()
    groq_key       = body.get("groq_key",       "").strip()

    if not keywords:
        return jsonify({"error": "keywords are required"}), 400

    criteria = {
        "keywords":    keywords,
        "price_min":   float(price_min) if price_min not in (None, "") else None,
        "price_max":   float(price_max) if price_max not in (None, "") else None,
        "min_rating":  min_rating,
        "min_reviews": min_reviews,
        "max_bsr":     max_bsr,
        "category":    category,
        "extra":       extra,
    }

    # ── Step 1: Fetch products ─────────────────
    mode = "demo"
    try:
        if rainforest_key:
            products = search_amazon_rainforest(keywords, limit=limit, api_key=rainforest_key)
            mode = "rainforest"
        elif scraper_key:
            # Temporarily monkey-patch the module-level key
            import Agent
            old_key = Agent.SCRAPER_API_KEY
            Agent.SCRAPER_API_KEY = scraper_key
            products = search_amazon_scraperapi(keywords)
            Agent.SCRAPER_API_KEY = old_key
            mode = "scraperapi"
        else:
            products = get_demo_products(keywords)
            mode = "demo"
    except Exception as e:
        print(f"[ERR] Fetch error: {e}")
        products = get_demo_products()
        mode = "demo"

    # Filter to limit
    products = products[:limit]

    # ── Step 2: Score products ─────────────────
    scored = [score_product(p, criteria) for p in products]
    scored.sort(key=lambda x: x["score"], reverse=True)

    # ── Step 3: Optional AI analysis ──────────
    if not skip_ai and groq_key:
        import Agent
        old_groq = Agent.GROQ_API_KEY
        Agent.GROQ_API_KEY = groq_key
        scored = analyze_with_groq(scored, criteria)
        Agent.GROQ_API_KEY = old_groq

    # ── Step 4: Respond ───────────────────────
    matches  = sum(1 for p in scored if p["status"] == "match")
    partials = sum(1 for p in scored if p["status"] == "partial")

    # Clean up non-serializable values
    clean = []
    for p in scored:
        clean.append({
            "asin":        p.get("asin", ""),
            "title":       p.get("title", ""),
            "price":       float(p.get("price") or 0),
            "rating":      float(p.get("rating") or 0),
            "reviews":     int(p.get("reviews") or 0),
            "bsr":         int(p.get("bsr") or 0),
            "category":    p.get("category", "General"),
            "image":       p.get("image", ""),
            "url":         p.get("url", ""),
            "fba":         bool(p.get("fba", True)),
            "competition": p.get("competition", "medium"),
            "weight":      p.get("weight", "N/A"),
            "score":       int(p.get("score", 0)),
            "status":      p.get("status", "nomatch"),
            "reasons":     p.get("reasons", []),
            "ai_note":     p.get("ai_note", ""),
            "monthlySales": 0,
            "revenue":      0,
        })

    return jsonify({
        "products": clean,
        "total":    len(clean),
        "matches":  matches,
        "partials": partials,
        "mode":     mode,
        "keywords": keywords,
    })


# ──────────────────────────────────────────────
# RUN
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  Amazon Research Agent — Flask Backend")
    print("="*55)
    print("  ✅ Open this in your browser:")
    print("     ➡  http://localhost:5000")
    print("  API Health: http://localhost:5000/api/health")
    print("="*55 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
