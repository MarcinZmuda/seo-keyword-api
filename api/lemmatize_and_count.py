import os
import requests
import re
import spacy
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# --- KONFIGURACJA APLIKACJI ---
load_dotenv()
app = Flask(__name__)

# --- ZMIENNE ŚRODOWISKOWE I ADRESY URL ---
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SERPAPI_URL = "https://serpapi.com/search"
# Upewnij się, że URL do langextract jest poprawny
LANGEXTRACT_API_URL = "https://langextract-api.onrender.com/extract" 

# --- ZAŁADOWANIE MODELU JĘZYKOWEGO SPACY ---
try:
    nlp = spacy.load("pl_core_news_sm")
    print("✅ Polski model językowy Spacy załadowany poprawnie.")
except OSError:
    print("❌ Błąd krytyczny: Nie znaleziono modelu 'pl_core_news_sm'.")
    nlp = None

# ==============================================================================
# ENDPOINT S1: ANALIZA WSTĘPNA
# ==============================================================================

def call_serpapi(topic):
    params = {"api_key": SERPAPI_KEY, "q": topic, "gl": "pl", "hl": "pl", "engine": "google"}
    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Błąd podczas wywołania SerpApi: {e}")
        return None

def call_langextract(url):
    try:
        response = requests.post(LANGEXTRACT_API_URL, json={"url": url}, timeout=30)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException as e:
        print(f"Błąd podczas ekstrakcji treści z {url}: {e}")
        return None

@app.route("/api/s1_analysis", methods=["POST"])
def perform_s1_analysis():
    data = request.get_json()
    topic = data.get("topic")

    if not topic: return jsonify({"error": "Brak parametru 'topic'"}), 400
    if not SERPAPI_KEY: return jsonify({"error": "Brak klucza SERPAPI_KEY w zmiennych środowiskowych"}), 500

    serp_data = call_serpapi(topic)
    if not serp_data: return jsonify({"error": "Nie udało się pobrać danych z SerpApi"}), 502

    organic_results = serp_data.get("organic_results", [])
    top_5_urls = [res.get("link") for res in organic_results[:5] if res.get("link")]

    successful_sources_count = 0
    source_processing_log = []

    for url in top_5_urls:
        if successful_sources_count >= 4: break
        content_data = call_langextract(url)
        if content_data and content_data.get("content"):
            successful_sources_count += 1
            source_processing_log.append({"url": url, "status": "Success"})
        else:
            source_processing_log.append({"url": url, "status": "Failure"})
    
    final_response = {
        "identified_urls": top_5_urls,
        "processing_report": source_processing_log,
        "serp_features": {
            "ai_overview": serp_data.get("ai_overview"),
            "people_also_ask": serp_data.get("related_questions"),
            "featured_snippets": serp_data.get("answer_box") 
        },
        "successful_sources_count": successful_sources_count
    }
    return jsonify(final_response)

# ==============================================================================
# ENDPOINT S3: WERYFIKACJA SŁÓW KLUCZOWYCH
# ==============================================================================

def lemmatize_text_properly(text):
    if not nlp: return text.lower().split()
    doc = nlp(text.lower())
    return [token.lemma_ for token in doc if token.is_alpha]

def count_keywords(text, keywords_with_ranges):
    text_lemmas = lemmatize_text_properly(text)
    counts = {}
    for keyword in keywords_with_ranges:
        kw_lemmas = lemmatize_text_properly(keyword)
        kw_len = len(kw_lemmas)
        count = 0
        if kw_len == 0: continue
        for i in range(len(text_lemmas) - kw_len + 1):
            if text_lemmas[i:i + kw_len] == kw_lemmas:
                count += 1
        counts[keyword] = count
    return counts

@app.route("/api/s3_verify_keywords", methods=["POST"])
def verify_s3_keywords():
    if not nlp: return jsonify({"error": "Model językowy Spacy nie jest załadowany."}), 503
    
    data = request.get_json(force=True)
    text = data.get("text", "")
    keywords_with_ranges = data.get("keywords_with_ranges", {})

    if not text: return jsonify({"error": "Brak parametru 'text'"}), 400
    if not isinstance(keywords_with_ranges, dict): return jsonify({"error": "'keywords_with_ranges' musi być obiektem JSON"}), 400

    counts = count_keywords(text, keywords_with_ranges.keys())
    report = {}
    for kw, used in counts.items():
        min_val, max_val = keywords_with_ranges.get(kw, [0, 100])
        status = "✅"
        if used < min_val: status = "⚠️"
        if used > max_val: status = "🚨"
        report[kw] = {"used": used, "allowed": f"{min_val}-{max_val}", "status": status}
    
    return jsonify({"keyword_report": report}), 200

# --- URUCHOMIENIE SERWERA (dla testów lokalnych) ---
if __name__ == "__main__":
    app.run(port=os.getenv("PORT", 5001), debug=True)
