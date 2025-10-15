from flask import Flask, request, jsonify
import re
import spacy
import traceback
import sys

app = Flask(__name__)

# Załaduj polski model językowy Spacy przy starcie aplikacji
try:
    nlp = spacy.load("pl_core_news_sm")
    print("✅ Polski model językowy Spacy załadowany poprawnie.")
except OSError:
    print("❌ Nie znaleziono modelu 'pl_core_news_sm'. Uruchom 'python -m spacy download pl_core_news_sm'")
    nlp = None

def lemmatize_text_properly(text):
    """Prawdziwa lematyzacja dla języka polskiego."""
    if not nlp:
        return re.findall(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", text.lower())
    doc = nlp(text.lower())
    return [token.lemma_ for token in doc if token.is_alpha]

def count_keywords(text, keywords_with_ranges):
    """Zlicza wystąpienia słów kluczowych (lematyzowanych) w tekście."""
    text_lemmas = lemmatize_text_properly(text)
    counts = {}

    for keyword in keywords_with_ranges:
        kw_lemmas = lemmatize_text_properly(keyword)
        kw_len = len(kw_lemmas)
        count = 0
        for i in range(len(text_lemmas) - kw_len + 1):
            if text_lemmas[i:i + kw_len] == kw_lemmas:
                count += 1
        counts[keyword] = count
    return counts

@app.route("/api/lemmatize_and_count", methods=["POST"])
def handle_request():
    try:
        data = request.get_json(force=True)
        text = data.get("text", "")
        # --- KLUCZOWA ZMIANA: Oczekujemy teraz obiektu JSON, a nie stringa ---
        keywords_with_ranges = data.get("keywords_with_ranges", {}) # np. {"pozew o rozwód": [7, 11]}

        if not text:
            raise ValueError("Brak parametru 'text'")
        if not isinstance(keywords_with_ranges, dict):
            raise TypeError("'keywords_with_ranges' musi być obiektem JSON (słownikiem).")

        counts = count_keywords(text, keywords_with_ranges.keys())

        report = {}
        for kw, used in counts.items():
            min_val, max_val = keywords_with_ranges.get(kw, [0, 100])

            status = "✅"
            if used < min_val: status = "⚠️"
            if used >= max_val: status = "🚨"

            report[kw] = {
                "used": used,
                "allowed_min": min_val,
                "allowed_max": max_val,
                "status": status,
                "range": f"{min_val}-{max_val}"
            }

        response = {
            "mode": "analysis",
            "keyword_report": report,
            "summary": f"Przeanalizowano {len(counts)} fraz kluczowych."
        }
        return jsonify(response), 200

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        error_details = {"error": str(e), "line": exc_tb.tb_lineno}
        print("❌ Błąd w endpointzie:", error_details)
        return jsonify(error_details), 500
