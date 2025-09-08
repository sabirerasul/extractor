import fitz, tempfile, subprocess, os

def has_text_layer(pdf_path: str) -> bool:
    with fitz.open(pdf_path) as doc:
        for p in doc:
            if p.get_text().strip():
                return True
    return False

def ocr_if_needed(pdf_path: str) -> str:
    if has_text_layer(pdf_path):
        return pdf_path
    out = pdf_path.replace(".pdf", "-ocr.pdf")
    cmd = ["ocrmypdf", "--force-ocr", "--deskew", "--rotate-pages", "--clean", "--optimize", "3", pdf_path, out]
    subprocess.run(cmd, check=True)
    return out

def normalize_orientation(pdf_path: str) -> str:
    # PyMuPDF auto-rotates content when extracting. We keep as-is here.
    return pdf_path
