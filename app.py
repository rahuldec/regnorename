import io
import zipfile

import pdfplumber
from flask import Flask, jsonify, render_template, request, send_file
from pypdf import PdfReader, PdfWriter

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB


def extract_page_data(plumber_page, page_index: int) -> dict:
    """
    Extract REGN. NO. and NAME by finding the 'REGN. NO.' column header
    in the page table — works regardless of what the actual value looks like.
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

        for row in table[header_idx + 1 :]:
            if row and regn_col < len(row) and row[regn_col] and row[regn_col].strip():
                regn_no = row[regn_col].strip()
                name = ""
                if name_col is not None and name_col < len(row) and row[name_col]:
                    name = " ".join((row[name_col] or "").split())
                return {"regn_no": regn_no, "name": name or "Unknown"}

    return {"regn_no": f"PAGE_{page_index + 1}", "name": "Unknown"}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/preview", methods=["POST"])
def preview():
    """Return a JSON list of {page, regn_no, name} for display before download."""
    if "pdf" not in request.files:
        return jsonify(error="No file uploaded"), 400

    pdf_bytes = request.files["pdf"].read()
    results = []

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if not text.strip():
                    continue
                data = extract_page_data(page, i)
                data["page"] = i + 1
                results.append(data)
    except Exception as e:
        return jsonify(error=str(e)), 500

    return jsonify(results)


@app.route("/download", methods=["POST"])
def download():
    """Split PDF, rename each page by REGN. NO., return ZIP."""
    if "pdf" not in request.files:
        return jsonify(error="No file uploaded"), 400

    pdf_bytes = request.files["pdf"].read()
    zip_buf = io.BytesIO()
    count = 0

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf, zipfile.ZipFile(
            zip_buf, "w", zipfile.ZIP_DEFLATED
        ) as zf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if not text.strip():
                    continue

                data = extract_page_data(page, i)
                filename = f"{data['regn_no']}.pdf"

                writer = PdfWriter()
                writer.add_page(reader.pages[i])
                page_buf = io.BytesIO()
                writer.write(page_buf)
                zf.writestr(filename, page_buf.getvalue())
                count += 1

    except Exception as e:
        return jsonify(error=str(e)), 500

    zip_buf.seek(0)
    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="admit_cards.zip",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5050)
