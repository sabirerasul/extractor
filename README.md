# 1035 In-Force Extractor API (Carrier-Agnostic) - Step-by-Step Guide

This repo is a working scaffold showing WHERE CODE GOES and EXACTLY HOW TO RUN IT.
It ingests a PDF, runs OCR if needed, finds ledger tables, labels columns, builds series,
computes a confidence score, PII scrubs (text-first in the skeleton), and returns JSON plus a redacted PDF.

NOTE: This is a starter. Your developer will expand table scoring, scenario selection, PII boxes on-page,
proof snip cropping, and the reconciliation math.

============================================================
1) FILE LAYOUT (put code exactly here)
============================================================
/app/main.py                  FastAPI app with /analyze endpoint
/app/models.py                Pydantic response models
/app/parser/preflight.py      OCR and basic PDF preflight
/app/parser/tables.py         ROI table discovery with Camelot
/app/parser/mapping.py        Header synonyms and basic shape helpers
/app/parser/confidence.py     Confidence blending
/app/parser/pii.py            Text PII scrub and PDF redaction helper stubs
/app/parser/snips.py          Proof snip cropping helper
/app/profiles/                Auto-learned carrier profiles (JSON), persisted at runtime
/golden_set/                  A few test PDFs for QA (you add these)
requirements.txt              Python packages
Dockerfile                    Container with Tesseract, ocrmypdf, Ghostscript, Java (for Tabula)
.env.example                  Example environment variables

============================================================
2) RUN LOCALLY WITH DOCKER (no system setup on your machine)
============================================================
Prereqs: Docker Desktop installed.

Commands:
- docker build -t extractor:latest .
- docker run --rm -p 8000:8000 --name extractor extractor:latest

Test the API:
- curl -F "file=@/path/to/your.pdf" http://localhost:8000/analyze

You should get back JSON with series, confidence, and a base64 redacted_pdf_b64.

============================================================
3) RUN WITHOUT DOCKER (developer machines or CI)
============================================================
Prereqs (Debian/Ubuntu):
- sudo apt-get update && sudo apt-get install -y tesseract-ocr ocrmypdf ghostscript qpdf poppler-utils openjdk-17-jre-headless
- python -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python -m spacy download en_core_web_sm
Run:
- uvicorn app.main:api --host 0.0.0.0 --port 8000

============================================================
4) EXPAND THE CORE LOGIC (what to implement next)
============================================================
A) Table scoring and scenario selection
- Scan each page, produce multiple ROI candidates, and parse with Camelot (lattice then stream).
- Score candidates by:
  - header synonym strength
  - shape patterns (year increments by 1, surrender_charge trends to 0, net_sv <= cash_value)
  - reconciliation identity: net_sv ~= cash_value - surrender_charge - loan - loan_interest (tolerance <= 1%)
- Choose the best candidate and set the "Current/Non-Guaranteed" scenario column using header proximity and identity fit.

B) Current-year row selection
- If issue date/age found, pick year approx equal to (today - issue_year). Else pick latest complete row.

C) Confidence
- Compute confidence_overall using app/parser/confidence.py. Threshold via CONFIDENCE_THRESHOLD env var.

D) PII scrubbing (page coordinates, not just text)
- Use Presidio to detect entities in text, then map to PDF coordinates using PyMuPDF search_for.
- Draw opaque white rectangles over spans on each page.
- Always strip PDF metadata (Author, Title, XMP).

E) Proof snips
- Crop small images: current rate header, first-year ledger row, current-year row, surrender charge current row, loan/indebtedness callout.
- Encode to base64 and include in proof_snips array.

F) Auto profiles
- After a successful parse, save a small JSON profile in /app/profiles capturing:
  - carrier/product tokens found on first pages
  - ROI hints (page index, y ranges)
  - selected scenario column index
  - header label map used
- On new uploads, attempt to load a matching profile before discovery.

============================================================
5) DEPLOYMENT (AWS sample)
============================================================
Option A: ECS Fargate
- Build and push image to ECR.
- Create Fargate service with 0.5 vCPU / 1GB memory.
- Set env vars (CONFIDENCE_THRESHOLD=0.80, PROFILE_DIR=/app/app/profiles).
- Attach an Application Load Balancer exposing port 8000.

Option B: Cloud Run (GCP) or Azure Container Apps
- Deploy container and set similar env vars and CPU/memory.
- Enable HTTPS.

============================================================
6) INTEGRATION (Zapier/Make and OpenAI)
============================================================
Workflow:
- Trigger: New PDF uploaded to your storage.
- Action 1: HTTP POST to /analyze with the PDF file.
- Action 2: Send the returned JSON to OpenAI for the decision + narrative (do not send raw PDF).
- Action 3: Fill a document template (Documint, PDFMonkey, etc.) embedding proof snips and flags.

============================================================
7) QA AND ACCEPTANCE
============================================================
- Place 20 to 30 varied PDFs in golden_set/ and create a small script to compare parsed numbers with labeled truth.
- Targets: numeric accuracy >= 95 percent; 0 PII leaks; average runtime <= 30s with OCR.

============================================================
8) COMMON FIXES
============================================================
- Camelot fails: ensure Ghostscript is installed and try flavor=stream fallback.
- OCR too slow: drop --optimize 3 to 1 in ocrmypdf or precheck text layer first.
- Java missing errors from Tabula: ensure openjdk is installed (Dockerfile includes it).
- Presidio misses names: consider upgrading to spaCy large model en_core_web_lg.

============================================================
9) EXAMPLE CURL
============================================================
curl -F "file=@/absolute/path/to/your.pdf" http://localhost:8000/analyze

The JSON response contains series arrays, confidence_overall, needs_manual_review flag, and redacted_pdf_b64.
