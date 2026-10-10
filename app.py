import io
import os
import tempfile
import uuid
import zipfile

import pdfplumber
from flask import Flask, jsonify, render_template, request, send_file
from pypdf import PdfReader, PdfWriter

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB

# In-memory map of token → temp file path; cleaned up after download
_uploads: dict[str, str] = {}


def extract_page_data(plumber_page, page_index: int) -> dict:
    """
    Find the column whose header contains 'REGN' and read whatever value is
    there — no hardcoded pattern, works for any REGN. NO. format.
    """
    tables = plumber_page.extract_tables()
    for table in tables:
        header_row = None
        header_idx = None
        for ri, row in enumerate(table):
            if row and any("REGN" in str(c) for c in row if c):
                header_row = row
                header_idx = ri
                break

        if header_row is None:
            continue

        regn_col = next((j for j, c in enumerate(header_row) if c and "REGN" in c), None)
        name_col = next((j for j, c in enumerate(header_row) if c and "NAME" in c), None)

        if regn_col is None:
            continue

        for row in table[header_idx + 1:]:
            if row and regn_col < len(row) and row[regn_col] and row[regn_col].strip():
                regn_no = row[regn_col].strip()
                name = ""
                if name_col is not None and name_col < len(row) and row[name_col]:
                    name = " ".join((row[name_col] or "").split())
                return {"regn_no": regn_no, "name": name or "Unknown"}

    return {"regn_no": f"PAGE_{page_index + 1}", "name": "Unknown"}


def _scan_pdf(path: str) -> list[dict]:
    """Return preview rows for all non-blank pages."""
    results = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            if not (page.extract_text() or "").strip():
                continue
            data = extract_page_data(page, i)
            data["page"] = i + 1
            results.append(data)
    return results


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    """
    Accept the PDF once, save to a temp file, return a token + preview rows.
    The client uses the token for /download — no second upload needed.
    """
    if "pdf" not in request.files:
        return jsonify(error="No file uploaded"), 400

    f = request.files["pdf"]
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as fp:
            f.save(fp)

        rows = _scan_pdf(path)
        token = str(uuid.uuid4())
        _uploads[token] = path
        return jsonify(token=token, pages=rows)
    except Exception as e:
        try:
            os.unlink(path)
        except OSError:
            pass
        return jsonify(error=str(e)), 500


@app.route("/download/<token>")
def download(token: str):
    """Build and return a ZIP of per-page PDFs named by REGN. NO."""
    path = _uploads.get(token)
    if not path or not os.path.exists(path):
        return jsonify(error="Session expired — please re-upload the PDF."), 404

    zip_buf = io.BytesIO()
    try:
        reader = PdfReader(path)
        with pdfplumber.open(path) as pdf, zipfile.ZipFile(
            zip_buf, "w", zipfile.ZIP_DEFLATED
        ) as zf:
            seen: dict[str, int] = {}
            for i, page in enumerate(pdf.pages):
                if not (page.extract_text() or "").strip():
                    continue
                data = extract_page_data(page, i)
                base = data["regn_no"]
                # Avoid collisions if same REGN appears more than once
                if base in seen:
                    seen[base] += 1
                    filename = f"{base}_{seen[base]}.pdf"
                else:
                    seen[base] = 1
                    filename = f"{base}.pdf"

                writer = PdfWriter()
                writer.add_page(reader.pages[i])
                page_buf = io.BytesIO()
                writer.write(page_buf)
                zf.writestr(filename, page_buf.getvalue())
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        # Clean up temp file after download
        try:
            os.unlink(path)
            _uploads.pop(token, None)
        except OSError:
            pass

    zip_buf.seek(0)
    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="admit_cards.zip",
    )


@app.errorhandler(413)
def too_large(e):
    return jsonify(error="File too large — maximum upload size is 500 MB."), 413


@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify(error=str(e)), 500


if __name__ == "__main__":
    app.run(debug=False, port=5050)
