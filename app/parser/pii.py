from presidio_analyzer import AnalyzerEngine, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine
from typing import Dict, Any
import base64
import fitz

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

DEFAULT_ENTITIES = ["PERSON","PHONE_NUMBER","EMAIL_ADDRESS","CREDIT_CARD","US_SSN","IP_ADDRESS","NRP","LOCATION"]

def scrub_text(text: str) -> str:
    results = analyzer.analyze(text=text, entities=DEFAULT_ENTITIES, language="en")
    anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized.text


def find_pii_coords(pdf_path: str) -> Dict[int, list]:
    # returns dict of page_num -> list of fitz.Rect
    doc = fitz.open(pdf_path)
    coords = {}
    for i, page in enumerate(doc):
        text = page.get_text("text")
        results = analyzer.analyze(text=text, entities=DEFAULT_ENTITIES, language="en")
        page_coords = []
        for res in results:
            pii_text = text[res.start:res.end]
            for r in page.search_for(pii_text):
                page_coords.append(r)
        if page_coords:
            coords[i] = page_coords
    return coords


def redact_pdf_boxes(pdf_path: str, spans: Dict[int, list], out_path: str):
    # spans: dict of page -> list of fitz.Rect to cover
    doc = fitz.open(pdf_path)
    red = (1,1,1)  # white box
    for pno, rects in spans.items():
        if pno >= len(doc): continue
        page = doc[pno]
        for r in rects:
            page.draw_rect(r, color=red, fill=red, width=0)
    doc.save(out_path)

def pixmap_to_b64(pix) -> str:
    return base64.b64encode(pix.tobytes("png")).decode("ascii")
