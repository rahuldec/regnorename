import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request
from _lib import process_pdf

app = Flask(__name__)


@app.route("/api/preview", methods=["POST"])
def preview():
    if "pdf" not in request.files:
        return jsonify(error="No file uploaded"), 400
    try:
        pdf_bytes = request.files["pdf"].read()
        rows, _ = process_pdf(pdf_bytes)
        return jsonify(rows)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.errorhandler(413)
def too_large(e):
    return jsonify(error="File too large. Max ~4.5 MB on Vercel Hobby."), 413
