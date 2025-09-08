# Python slim base
FROM python:3.11-slim

# System deps for OCR and PDF tooling
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    tesseract-ocr \
    ocrmypdf \
    ghostscript \
    qpdf \
    poppler-utils \
    build-essential \
    openjdk-17-jre-headless \
    libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Workdir
WORKDIR /app

# Copy reqs and install
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy source
COPY app /app/app
COPY app/profiles /app/app/profiles

# Expose port
EXPOSE 8000

# Start
CMD ["uvicorn", "app.main:api", "--host", "0.0.0.0", "--port", "8000"]
