import io
import zipfile

import pdfplumber
from flask import Flask, jsonify, render_template, request, send_file
from pypdf import PdfReader, PdfWriter

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB


def _extract_page_data(plumber_page, page_index: int) -> dict:
    tables = plumber_page.extract_tables()
    for table in tables:
        header_row = None
        header_idx = None
        for ri, row in enumerate(table):
            if row and any("REGN" in str(c) or "ROLL" in str(c) for c in row if c):
                header_row = row
                header_idx = ri
                break
        if header_row is None:
            continue
        regn_col = next((j for j, c in enumerate(header_row) if c and "REGN" in c), None)
        roll_col = next((j for j, c in enumerate(header_row) if c and "ROLL" in c), None)
        name_col = next((j for j, c in enumerate(header_row) if c and "NAME" in c), None)
        id_col = regn_col if regn_col is not None else roll_col
        if id_col is None:
            continue
        for row in table[header_idx + 1:]:
            if row and id_col < len(row) and row[id_col] and row[id_col].strip():
                file_id = row[id_col].strip()
                name = ""
                if name_col is not None and name_col < len(row) and row[name_col]:
                    name = " ".join((row[name_col] or "").split())
                return {"regn_no": file_id, "name": name or "Unknown"}
    return {"regn_no": f"PAGE_{page_index + 1}", "name": "Unknown"}


def _process_pdf(pdf_bytes: bytes):
    """Single pass over pdf_bytes → (rows list, zip bytes)."""
    rows = []
    zip_buf = io.BytesIO()
    seen: dict[str, int] = {}
    reader = PdfReader(io.BytesIO(pdf_bytes))
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf, \
         zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, page in enumerate(pdf.pages):
            if not (page.extract_text() or "").strip():
                continue
            data = _extract_page_data(page, i)
            base = data["regn_no"]
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
            rows.append({"page": i + 1, "regn_no": base, "name": data["name"], "filename": filename})
    zip_buf.seek(0)
    return rows, zip_buf.getvalue()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/preview", methods=["POST"])
def api_preview():
    if "pdf" not in request.files:
        return jsonify(error="No file uploaded"), 400
    try:
        pdf_bytes = request.files["pdf"].read()
        rows, _ = _process_pdf(pdf_bytes)
        return jsonify(rows)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/api/download", methods=["POST"])
def api_download():
    if "pdf" not in request.files:
        return jsonify(error="No file uploaded"), 400
    try:
        pdf_bytes = request.files["pdf"].read()
        _, zip_bytes = _process_pdf(pdf_bytes)
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
    return jsonify(error="File too large — maximum upload size is 10 MB."), 413


@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify(error=str(e)), 500


if __name__ == "__main__":
    app.run(debug=False, port=5050)
