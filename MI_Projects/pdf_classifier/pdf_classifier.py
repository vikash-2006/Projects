"""
PDF Document Classification Script
====================================
Author  : Vikash Kumawat
Purpose : Automatically classify PDF documents into predefined categories
          using text extraction, NLP preprocessing, and rule-based + TF-IDF scoring.

Usage:
    python pdf_classifier.py --input ./sample_pdfs --output results.csv

Dependencies:
    pip install pdfplumber pypdf pandas nltk scikit-learn
"""

import os
import re
import csv
import json
import argparse
import logging
from pathlib import Path
from typing import Optional

import pdfplumber
from pypdf import PdfReader
import pandas as pd
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# ─────────────────────────────────────────────
# 1. DOWNLOAD REQUIRED NLTK DATA
# ─────────────────────────────────────────────
for pkg in ["stopwords", "punkt", "punkt_tab"]:
    nltk.download(pkg, quiet=True)

# ─────────────────────────────────────────────
# 2. LOGGING SETUP
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 3. CATEGORY DEFINITIONS
#    Each category has a list of seed keywords.
#    You can ADD / REMOVE categories here freely.
# ─────────────────────────────────────────────
CATEGORIES = {
    "Invoice / Finance": [
        "invoice", "bill", "payment", "amount", "due", "tax", "receipt",
        "total", "cost", "price", "charge", "fee", "purchase", "order",
        "vendor", "supplier", "gst", "vat", "net", "gross", "balance"
    ],
    "Medical / Healthcare": [
        "patient", "doctor", "diagnosis", "prescription", "medicine",
        "hospital", "clinic", "treatment", "symptoms", "blood", "test",
        "health", "medical", "surgery", "physician", "nurse", "disease",
        "drug", "dosage", "report", "lab", "clinical"
    ],
    "Resume / CV": [
        "resume", "curriculum", "vitae", "cv", "skills", "experience",
        "education", "objective", "internship", "projects", "certifications",
        "employment", "work", "career", "university", "college", "degree",
        "python", "developer", "engineer", "analyst", "fresher"
    ],
    "Research / Academic": [
        "abstract", "research", "paper", "study", "methodology", "hypothesis",
        "conclusion", "references", "literature", "experiment", "analysis",
        "findings", "journal", "publication", "academic", "theory", "model",
        "dataset", "algorithm", "neural", "machine learning"
    ],
    "Legal / Contract": [
        "agreement", "contract", "party", "clause", "terms", "conditions",
        "jurisdiction", "legal", "law", "court", "liability", "penalty",
        "tenant", "landlord", "lease", "sign", "witness", "notary",
        "obligation", "rights", "binding", "hereby"
    ],
    "News / Article": [
        "reported", "according", "stated", "announced", "government",
        "minister", "country", "city", "event", "breaking", "news",
        "journalist", "press", "media", "interview", "spokesperson"
    ],
    "Technical / Manual": [
        "installation", "configuration", "system", "hardware", "software",
        "manual", "guide", "steps", "procedure", "setup", "version",
        "specification", "api", "documentation", "module", "error", "debug"
    ],
}

# ─────────────────────────────────────────────
# 4. TEXT EXTRACTION
# ─────────────────────────────────────────────

def extract_text_pdfplumber(pdf_path: str) -> Optional[str]:
    """
    Primary extractor using pdfplumber.
    Better for complex layouts and tables.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            return "\n".join(pages_text) if pages_text else None
    except Exception as e:
        log.debug(f"pdfplumber failed for {pdf_path}: {e}")
        return None


def extract_text_pypdf(pdf_path: str) -> Optional[str]:
    """
    Fallback extractor using pypdf.
    Handles encrypted PDFs by detecting them early.
    """
    try:
        reader = PdfReader(pdf_path)

        # Detect encrypted PDFs that cannot be read
        if reader.is_encrypted:
            try:
                reader.decrypt("")          # Try empty password
            except Exception:
                return None                 # Truly encrypted — skip

        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        return "\n".join(pages_text) if pages_text else None

    except Exception as e:
        log.debug(f"pypdf failed for {pdf_path}: {e}")
        return None


def extract_text(pdf_path: str) -> tuple[Optional[str], str]:
    """
    Try pdfplumber first, fall back to pypdf.
    Returns (text_or_None, status_message).
    """
    text = extract_text_pdfplumber(pdf_path)
    if text and text.strip():
        return text, "ok"

    text = extract_text_pypdf(pdf_path)
    if text and text.strip():
        return text, "ok (fallback extractor)"

    # Check if file is encrypted
    try:
        reader = PdfReader(pdf_path)
        if reader.is_encrypted:
            return None, "encrypted"
    except Exception:
        pass

    return None, "empty or unreadable"


# ─────────────────────────────────────────────
# 5. TEXT PREPROCESSING
# ─────────────────────────────────────────────

STOP_WORDS = set(stopwords.words("english"))


def preprocess(text: str) -> str:
    """
    Clean and normalise raw PDF text.

    Steps:
        1. Lowercase everything
        2. Remove special characters / numbers (keep letters + spaces)
        3. Tokenize into individual words
        4. Remove stop words (the, is, at, …)
        5. Rejoin into a clean string
    """
    # Step 1: Lowercase
    text = text.lower()

    # Step 2: Remove non-alphabetic characters
    text = re.sub(r"[^a-z\s]", " ", text)

    # Step 3: Tokenize
    tokens = word_tokenize(text)

    # Step 4: Remove stop words and very short tokens
    tokens = [t for t in tokens if t not in STOP_WORDS and len(t) > 2]

    # Step 5: Rejoin
    return " ".join(tokens)


# ─────────────────────────────────────────────
# 6. CLASSIFICATION ENGINE
#    Two scoring methods combined:
#    (a) Rule-based keyword counting       → fast, interpretable
#    (b) TF-IDF cosine similarity          → handles unseen vocabulary
# ─────────────────────────────────────────────

# Build TF-IDF corpus from category seed keywords
_category_names  = list(CATEGORIES.keys())
_category_docs   = [" ".join(kws) for kws in CATEGORIES.values()]
_tfidf           = TfidfVectorizer()
_category_matrix = _tfidf.fit_transform(_category_docs)   # shape: (n_categories, vocab)


def classify(clean_text: str) -> tuple[str, float]:
    """
    Classify a preprocessed text string.

    Returns:
        (category_name, confidence_score_0_to_1)
    """
    if not clean_text.strip():
        return "Unknown", 0.0

    # ── Method A: Keyword rule-based scoring ──────────────────────
    rule_scores = {}
    words_in_doc = set(clean_text.split())

    for cat, keywords in CATEGORIES.items():
        hits = sum(1 for kw in keywords if kw in words_in_doc)
        rule_scores[cat] = hits / len(keywords)          # normalised 0-1

    # ── Method B: TF-IDF cosine similarity ───────────────────────
    try:
        doc_vector   = _tfidf.transform([clean_text])
        similarities = cosine_similarity(doc_vector, _category_matrix)[0]
        tfidf_scores = {_category_names[i]: float(similarities[i])
                        for i in range(len(_category_names))}
    except Exception:
        tfidf_scores = {cat: 0.0 for cat in _category_names}

    # ── Combine: 40% rule-based + 60% TF-IDF ─────────────────────
    final_scores = {}
    for cat in _category_names:
        final_scores[cat] = (0.40 * rule_scores.get(cat, 0.0) +
                             0.60 * tfidf_scores.get(cat, 0.0))

    best_cat   = max(final_scores, key=final_scores.get)
    best_score = final_scores[best_cat]

    # Low-confidence fallback
    if best_score < 0.02:
        return "Unknown", round(best_score, 4)

    # Normalise score to 0–1 range for readability
    total = sum(final_scores.values())
    confidence = best_score / total if total > 0 else 0.0

    return best_cat, round(confidence, 4)


# ─────────────────────────────────────────────
# 7. MAIN PIPELINE
# ─────────────────────────────────────────────

def process_folder(input_folder: str, output_file: str, fmt: str = "csv"):
    """
    Walk through all PDFs in input_folder, classify each,
    and save results to output_file (csv or json).
    """
    pdf_paths = sorted(Path(input_folder).rglob("*.pdf"))

    if not pdf_paths:
        log.warning(f"No PDF files found in: {input_folder}")
        return

    log.info(f"Found {len(pdf_paths)} PDF(s). Starting classification…\n")

    results = []

    for pdf_path in pdf_paths:
        filename = pdf_path.name
        log.info(f"Processing → {filename}")

        # ── Extract text ──────────────────────────────────────────
        raw_text, status = extract_text(str(pdf_path))

        if status != "ok" and not raw_text:
            log.warning(f"  ✗ Skipped ({status}): {filename}")
            results.append({
                "filename"        : filename,
                "category"        : "Error",
                "confidence_score": 0.0,
                "status"          : status,
                "word_count"      : 0,
            })
            continue

        # ── Preprocess ────────────────────────────────────────────
        clean_text = preprocess(raw_text)
        word_count = len(clean_text.split())

        # ── Classify ──────────────────────────────────────────────
        category, confidence = classify(clean_text)

        log.info(f"  ✔ Category : {category}")
        log.info(f"    Confidence: {confidence:.2%}")
        log.info(f"    Words     : {word_count}\n")

        results.append({
            "filename"        : filename,
            "category"        : category,
            "confidence_score": confidence,
            "status"          : status,
            "word_count"      : word_count,
        })

    # ── Save output ───────────────────────────────────────────────
    if fmt == "json":
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
    else:
        df = pd.DataFrame(results)
        df.to_csv(output_file, index=False)

    log.info(f"Results saved → {output_file}")
    log.info(f"Total processed: {len(results)} file(s)")

    # ── Print summary table ───────────────────────────────────────
    print("\n" + "="*65)
    print(f"{'FILENAME':<30} {'CATEGORY':<25} {'CONF':>6}")
    print("="*65)
    for r in results:
        conf_str = f"{r['confidence_score']:.0%}" if r['confidence_score'] else "—"
        print(f"{r['filename']:<30} {r['category']:<25} {conf_str:>6}")
    print("="*65 + "\n")


# ─────────────────────────────────────────────
# 8. CLI ENTRY POINT
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🗂  PDF Document Classifier — auto-categorises PDF files"
    )
    parser.add_argument(
        "--input", "-i",
        default="./sample_pdfs",
        help="Folder containing PDF files (default: ./sample_pdfs)"
    )
    parser.add_argument(
        "--output", "-o",
        default="results.csv",
        help="Output file path, e.g. results.csv or results.json"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["csv", "json"],
        default="csv",
        help="Output format: csv (default) or json"
    )
    args = parser.parse_args()

    # Auto-detect format from file extension if not explicitly set
    if args.output.endswith(".json"):
        args.format = "json"

    print("\n" + "="*65)
    print("   PDF DOCUMENT CLASSIFIER")
    print("="*65)
    print(f"   Input  : {args.input}")
    print(f"   Output : {args.output}")
    print(f"   Format : {args.format.upper()}")
    print("="*65 + "\n")

    process_folder(args.input, args.output, args.format)


if __name__ == "__main__":
    main()