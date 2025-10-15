from flask import Flask, request, jsonify
import re
import spacy # <-- NOWA BIBLIOTEKA
import traceback
import sys

app = Flask(__name__)

# --- NOWOŚĆ: Załaduj polski model językowy przy starcie aplikacji ---
# To sprawia, że jest gotowy do pracy od razu i nie ładuje się przy każdym zapytaniu.
try:
    nlp = spacy.load("pl_core_news_sm")
    print("✅ Polski model językowy Spacy załadowany poprawnie.")
except OSError:
    print("❌ Nie znaleziono modelu 'pl_core_news_sm'. Uruchom 'python -m spacy download pl_core_news_sm'")
    nlp = None

def lemmatize_text_properly(text):
    """
    Prawdziwa lematyzacja dla języka polskiego.
    Zamienia tekst na listę słów w ich formie podstawowej (lematów).
    Przykład: "Wniósł pozwu o rozwodem" -> ['wnieść', 'pozew', 'o', 'rozwód']
    """
    if not nlp:
        # Fallback do starej metody, jeśli model się nie załadował
        return re.findall(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", text.lower())
    
    doc = nlp(text.lower())
    # Zwracamy listę lematów (form podstawowych) dla każdego słowa w tekście
    return [token.lemma_ for token in doc if token.is_alpha]

def count_keywords(text, keywords_with_ranges):
    """
    Zlicza wystąpienia słów kluczowych (lematyzowanych) w tekście.
    Teraz rozumie odmiany słów.
    """
    text_lemmas = lemmatize_text_properly(text)
    counts = {}

    for keyword in keywords_with_ranges:
        # Lematyzujemy słowo kluczowe, aby szukać jego formy podstawowej
        kw_lemmas = lemmatize_text_properly(keyword)
        kw_len = len(kw_lemmas)
        count = 0
        
        # Przesuwamy się po liście lematów tekstu i szukamy dokładnej sekwencji lematów frazy
        for i in range(len(text_lemmas) - kw_len + 1):
            if text_lemmas[i:i + kw_len] == kw_lemmas:
                count += 1
        counts[keyword] = count
    return counts

def parse_keywords_with_ranges(keyword_list_string):
    """
    Przetwarza string od użytkownika (np. "pozew o rozwód: 7-11") na słownik.
    """
    keywords = {}
    for line in keyword_list_string.strip().split('\n'):
        parts = line.split(':')
        if len(parts) == 2:
            key = parts[0].strip()
            range_parts = parts[1].strip().split('-')
            if len(range_parts) == 2:
                try:
                    min_val = int(range_parts[0])
                    max_val = int(range_parts[1])
                    keywords[key] = (min_val, max_val)
                except ValueError:
                    pass # Ignoruj linie z nieprawidłowymi liczbami
    return keywords

@app.route("/api/lemmatize_and_count", methods=["POST"])
def handle_request():
    try:
        data = request.get_json(force=True)
        text = data.get("text", "")
        # Zmieniamy sposób przyjmowania słów kluczowych, aby pasował do promptu
        keyword_list_string = data.get("keywords", "") # Oczekujemy teraz stringa, nie listy

        if not text:
            raise ValueError("Brak parametru 'text'")
        if not keyword_list_string:
             return jsonify({"keyword_report": {}, "summary": "Brak słów kluczowych do analizy."})

        # Przetwarzamy string na słownik z zakresami
        keywords_with_ranges = parse_keywords_with_ranges(keyword_list_string)
        
        # Zliczamy słowa kluczowe używając nowej, lepszej metody
        counts = count_keywords(text, keywords_with_ranges.keys())
        
        # Budujemy raport
        report = {}
        for kw, used in counts.items():
            min_val, max_val = keywords_with_ranges.get(kw, (0, 100)) # Domyślny, szeroki zakres
            
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
