import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import process_pdf


def app(environ, start_response):
    if environ.get("REQUEST_METHOD") != "POST":
        start_response("405 Method Not Allowed", [("Content-Type", "application/json")])
        return [b'{"error":"Method not allowed"}']
    try:
        from werkzeug.wrappers import Request
        req = Request(environ)
        if "pdf" not in req.files:
            start_response("400 Bad Request", [("Content-Type", "application/json")])
            return [b'{"error":"No file uploaded"}']
        pdf_bytes = req.files["pdf"].read()
        rows, _ = process_pdf(pdf_bytes)
        body = json.dumps(rows).encode()
        start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
        ])
        return [body]
    except Exception as e:
        body = json.dumps({"error": str(e)}).encode()
        start_response("500 Internal Server Error", [("Content-Type", "application/json")])
        return [body]
