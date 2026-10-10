import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, send_file
from _lib import process_pdf

app = Flask(__name__)


@app.route("/api/download", methods=["POST"])
def download():
    if "pdf" not in request.files:
        return jsonify(error="No file uploaded"), 400
    try:
        pdf_bytes = request.files["pdf"].read()
        _, zip_bytes = process_pdf(pdf_bytes)
        return send_file(
            io.BytesIO(zip_bytes),
            mimetype="application/zip",
            as_attachment=True,
            download_name="admit_cards.zip",
        )
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.errorhandler(413)
def too_large(e):
    return jsonify(error="File too large. Max ~4.5 MB on Vercel Hobby."), 413
