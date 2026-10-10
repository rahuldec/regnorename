# Admit Card Splitter

A Flask web portal that splits a multi-student admit card PDF into individual files named by **REGN. NO.** — reads directly from the table column, so the value format doesn't matter.

## How it works

1. Upload the combined PDF
2. Click **Preview** to see all extracted REGN. NOs and student names
3. Click **Download ZIP** to get all individual PDFs

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5050
