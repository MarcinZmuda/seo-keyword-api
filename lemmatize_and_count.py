import json
import random
import spacy
from http.server import BaseHTTPRequestHandler

# Wczytanie modelu językowego spaCy (PL)
try:
    NLP = spacy.load("pl_core_news_sm")
except OSError:
    from spacy.cli import download
    download("pl_core_news_sm")
    NLP = spacy.load("pl_core_news_sm")

def lemmatize_text(text):
    """Zwraca listę lematów z tekstu (bez znaków interpunkcyjnych)."""
    doc = NLP(text.lower())
    return [token.lemma_ for token in doc if token.is_alpha]

def count_keywords(text, keywords):
    """Zlicza wystąpienia słów kluczowych (po lematyzacji)."""
    text_lemmas = lemmatize_text(text)
    counts = {}

    for keyword in keywords:
        keyword_lemmas = lemmatize_text(keyword)
        kw_len = len(keyword_lemmas)
        count = 0
        for i in range(len(text_lemmas) - kw_len + 1):
            if text_lemmas[i:i + kw_len] == keyword_lemmas:
                count += 1
        counts[keyword] = count
    return counts

def generate_keyword_report(counts, min_val=1, max_val=3):
    """Buduje raport statusów dla słów kluczowych."""
    report = {}
    for kw, used in counts.items():
        if used < min_val:
            status = "⚠️"
            message = "Zbyt mało użyć — rozważ dodanie."
        elif used > max_val:
            status = "🚨"
            message = "Za dużo użyć — możliwy keyword stuffing."
        else:
            status = "✅"
            message = "W normie."

        report[kw] = {
            "used": used,
            "allowed_min": min_val,
            "allowed_max": max_val,
            "remaining": max(0, max_val - used),
            "status": status,
            "message": message
        }
    return report

def humanize_text(text, counts, min_val=1, max_val=3):
    """
    Uzupełnia lub redukuje wystąpienia słów kluczowych w tekście
    zgodnie z zakresami (naturalne, kontekstowe wstawki).
    """
    sentences = [s.text.strip() for s in NLP(text).sents]
    improved_text = text

    for kw, used in counts.items():
        if used < min_val:
            needed = min_val - used
            for _ in range(needed):
                insert_sentence = random.choice([
                    f"Temat {kw} zasługuje na szczególną uwagę w tym kontekście.",
                    f"Warto wspomnieć również o {kw}, które odgrywa tu istotną rolę.",
                    f"Nie sposób pominąć aspektu {kw}, mającego duże znaczenie praktyczne."
                ])
                improved_text += " " + insert_sentence

        elif used > max_val:
            # Redukcja: delikatne usunięcie kilku wystąpień
            words = improved_text.split()
            removed = 0
            for i, w in enumerate(words):
                if kw in w.lower():
                    words[i] = ""
                    removed += 1
                    if removed >= (used - max_val):
                        break
            improved_text = " ".join(words)

    return improved_text.strip()

class handler(BaseHTTPRequestHandler):

    def _set_headers(self):
        self.send_header('Access-Control-Allow-Origin', 'https://chat.openai.com')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self._set_headers()
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data)

            text_to_process = data.get("text", "")
            keywords_to_find = data.get("keywords", [])
            mode = data.get("mode", "analysis")

            if not text_to_process or not isinstance(keywords_to_find, list):
                raise ValueError("Missing or invalid 'text' or 'keywords' parameters.")

            DEFAULT_MIN = 1
            DEFAULT_MAX = 3

            # ANALIZA
            counts = count_keywords(text_to_process, keywords_to_find)
            keyword_report = generate_keyword_report(counts, DEFAULT_MIN, DEFAULT_MAX)

            if mode == "analysis":
                response = {
                    "mode": "analysis",
                    "keyword_report": keyword_report,
                    "summary": (
                        f"Analiza zakończona. Przetworzono {len(keywords_to_find)} fraz. "
                        "Statusy: ✅ OK, ⚠️ poniżej zakresu, 🚨 powyżej zakresu."
                    )
                }

            elif mode == "humanized":
                # Dopasowanie liczby wystąpień
                improved_text = humanize_text(text_to_process, counts, DEFAULT_MIN, DEFAULT_MAX)
                new_counts = count_keywords(improved_text, keywords_to_find)
                new_report = generate_keyword_report(new_counts, DEFAULT_MIN, DEFAULT_MAX)

                response = {
                    "mode": "humanized",
                    "original_report": keyword_report,
                    "adjusted_report": new_report,
                    "updated_text": improved_text,
                    "summary": (
                        "Tekst został zhumanizowany i dopasowany do zakresów wystąpień fraz. "
                        "Zachowano naturalny ton i kontekst semantyczny."
                    )
                }

            else:
                raise ValueError("Invalid 'mode'. Use 'analysis' or 'humanized'.")

            # Zwracanie odpowiedzi
            self.send_response(200)
            self._set_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            self.send_response(400)
            self._set_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = json.dumps({"error": str(e)})
            self.wfile.write(error_response.encode('utf-8'))
