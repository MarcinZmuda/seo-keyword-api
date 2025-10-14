from flask import Flask, request, jsonify
import re
import random

app = Flask(__name__)

def lemmatize_text(text):
    """Zwraca listę 'lepszych' tokenów (bez interpunkcji i liczb)."""
    return re.findall(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", text.lower())

def count_keywords(text, keywords):
    """Zlicza wystąpienia słów kluczowych (po uproszczonej lematyzacji)."""
    text_tokens = lemmatize_text(text)
    counts = {}

    for keyword in keywords:
        kw_tokens = lemmatize_text(keyword)
        kw_len = len(kw_tokens)
        count = 0
        for i in range(len(text_tokens) - kw_len + 1):
            if text_tokens[i:i + kw_len] == kw_tokens:
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
    """Dodaje lub redukuje słowa kluczowe, zachowując naturalność."""
    improved_text = text
    for kw, used in counts.items():
        if used < min_val:
            needed = min_val - used
            for _ in range(needed):
                insert_sentence = random.choice([
                    f"Temat {kw} jest tutaj kluczowy.",
                    f"Warto również omówić {kw}.",
                    f"Nie można pominąć zagadnienia {kw}."
                ])
                improved_text += " " + insert_sentence
        elif used > max_val:
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

@app.route("/api/lemmatize_and_count", methods=["POST"])
def handle_request():
    try:
        data = request.get_json(force=True)
        text = data.get("text", "")
        keywords = data.get("keywords", [])
        mode = data.get("mode", "analysis")

        if not text or not isinstance(keywords, list):
            raise ValueError("Brak lub nieprawidłowe dane: 'text' lub 'keywords'.")

        DEFAULT_MIN, DEFAULT_MAX = 1, 3
        counts = count_keywords(text, keywords)
        keyword_report = generate_keyword_report(counts, DEFAULT_MIN, DEFAULT_MAX)

        if mode == "analysis":
            response = {
                "mode": "analysis",
                "keyword_report": keyword_report,
                "summary": f"Przetworzono {len(keywords)} fraz."
            }
        elif mode == "humanized":
            improved_text = humanize_text(text, counts, DEFAULT_MIN, DEFAULT_MAX)
            new_counts = count_keywords(improved_text, keywords)
            new_report = generate_keyword_report(new_counts, DEFAULT_MIN, DEFAULT_MAX)
            response = {
                "mode": "humanized",
                "original_report": keyword_report,
                "adjusted_report": new_report,
                "updated_text": improved_text,
                "summary": "Tekst został dopasowany semantycznie."
            }
        else:
            raise ValueError("Nieprawidłowy tryb. Użyj 'analysis' lub 'humanized'.")

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 400

def handler(request):
    """Kompatybilność z Vercel Python Runtime"""
    with app.request_context(request.environ):
        return app.full_dispatch_request()
