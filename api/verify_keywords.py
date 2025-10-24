import json
from http.server import BaseHTTPRequestHandler
import spacy

nlp = spacy.load("pl_core_news_sm")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        data = json.loads(body.decode("utf-8"))

        text = data.get("text", "")
        keywords = data.get("keywords_with_ranges", {})

        # Obsługa różnych formatów (string, object)
        if isinstance(keywords, str):
            kw_map = {}
            for part in keywords.split(";"):
                part = part.strip()
                if "|" in part:
                    kw, rng = part.split("|")
                    min_r, max_r = map(int, rng.split("-"))
                    kw_map[kw.strip()] = {"min": min_r, "max": max_r}
                else:
                    kw_map[part] = {"min": 1, "max": 3}
            keywords = kw_map

        doc = nlp(text.lower())
        lemmatized = " ".join([t.lemma_ for t in doc])

        keyword_report = {}
        for kw, limits in keywords.items():
            kw_doc = nlp(kw.lower())
            lemmas_kw = " ".join([t.lemma_ for t in kw_doc])
            count = lemmatized.count(lemmas_kw)
            status = "OK"
            if count < limits["min"]:
                status = "UNDER"
            elif count > limits["max"]:
                status = "OVER"
            keyword_report[kw] = {
                "used": count,
                "min_allowed": limits["min"],
                "max_allowed": limits["max"],
                "status": status
            }

        response = {"keyword_report": keyword_report}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
