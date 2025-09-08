import fitz
import camelot
from typing import List, Dict, Any, Tuple
import tempfile, os
from app.parser.mapping import label_columns, shape_score, reconciliation_score

HEADER_CANDIDATES = [
    "Policy Year","Year","Yr","Age","Premium","Planned Premium","Annual Outlay",
    "Cash Value","Account Value","Accumulation Value","Surrender Charge",
    "Net Surrender Value","Net Cash Surrender Value","Indebtedness","Policy Loan","Loan"
]

def find_roi_and_tables(pdf_path: str) -> List[Dict[str, Any]]:
    tables = []
    with fitz.open(pdf_path) as doc:
        for i, p in enumerate(doc):
            text = p.get_text("text")
            # basic heuristic: if any header candidate appears, try ROI from that y to bottom
            blocks = p.get_text("blocks")
            y_candidates = []
            for (x0,y0,x1,y1,txt,_,_) in blocks:
                t = " ".join((txt or "").split()).lower()
                for term in HEADER_CANDIDATES:
                    if term.lower() in t:
                        y_candidates.append(y0)
                        break
            if not y_candidates:
                continue
            y_header = min(y_candidates)
            roi = fitz.Rect(0, max(0, y_header-6), p.rect.width, p.rect.height)
            # Save cropped page as temp single-page PDF
            pdf_roi = fitz.open()
            #pdf_roi.insert_pdf(doc, from_page=i, to_page=i, clip=roi)

            # Copy the full page first
            pdf_roi.insert_pdf(doc, from_page=i, to_page=i)
            
            # Then crop the page to ROI
            page = pdf_roi[-1]   # last inserted page
            page.set_cropbox(roi)   # roi is a fitz.Rect

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf_roi.save(tmp.name); pdf_roi.close()
            try:
                # try lattice then stream
                for flavor in ("lattice","stream"):
                    try:
                        ts = camelot.read_pdf(tmp.name, flavor=flavor, pages="1")
                        for t in ts:
                            col_map = label_columns(t.df)
                            header_strength = len(col_map) / len(HEADER_CANDIDATES)
                            shape = shape_score(t.df, col_map)
                            recon = reconciliation_score(t.df, col_map)
                            score = 0.4 * header_strength + 0.4 * shape + 0.2 * recon
                            tables.append({
                                "page": i,
                                "flavor": flavor,
                                "df": t.df,
                                "col_map": col_map,
                                "score": score,
                                "metrics": {
                                    "header_strength": header_strength,
                                    "shape_fit": shape,
                                    "recon_success": recon
                                }
                            })
                        if ts.n > 0:
                            break
                    except Exception:
                        continue
            finally:
                os.unlink(tmp.name)
    return sorted(tables, key=lambda x: x["score"], reverse=True)
