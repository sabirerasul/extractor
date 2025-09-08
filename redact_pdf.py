import fitz
import base64

def redact_pdf(pdf_path, out_path):
    doc = fitz.open(pdf_path)
    pii_texts = [
        "SANDRA SUMIKO ARIYAMA",
        "PHILLIP CHESHARECK",
        "1544 Sprucewood Court, Morris, IL 60450",
        "phil@doveventures.com"
    ]
    for page in doc:
        for pii in pii_texts:
            rects = page.search_for(pii)
            for r in rects:
                page.draw_rect(r, color=(1,1,1), fill=(1,1,1), width=0)
    doc.save(out_path)

def pdf_to_b64(pdf_path):
    with open(pdf_path, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode('ascii')

if __name__ == "__main__":
    pdf_path = "/home/tech9/Downloads/testing pdf/Sandra-Ariyama-Inforce-Illustration.pdf"
    out_path = "/home/tech9/Downloads/testing pdf/redacted.pdf"
    redact_pdf(pdf_path, out_path)
    b64 = pdf_to_b64(out_path)
    print(b64)