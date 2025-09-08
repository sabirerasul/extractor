import os, io, tempfile, base64, json, uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from app.models import AnalyzeResponse, Fields, Series, Verifications, ProofSnip, ValueWithMeta
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, RedirectResponse
from app.parser.preflight import ocr_if_needed, normalize_orientation
from app.parser.tables import find_roi_and_tables
from app.parser.mapping import label_columns, clean_number
from app.parser.confidence import compute_confidence
from app.parser.pii import scrub_text, redact_pdf_boxes, find_pii_coords
from app.parser.snips import find_snip_coords, crop_to_b64
import fitz
import pandas as pd
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME]):
    raise ValueError("AWS S3 environment variables not set. Please check your .env file.")


s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.80"))


api = FastAPI(title="1035 In-Force Extractor API")

def b64_file(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")
    
api.mount("/static", StaticFiles(directory="frontend"), name="static")


@api.get("/")
async def read_index():
    return FileResponse('frontend/index.html')

@api.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    # Save temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        data = await file.read()
        tmp.write(data)
        tmp_path = tmp.name

    try:
        prepped = ocr_if_needed(tmp_path)
        prepped = normalize_orientation(prepped)

        tables = find_roi_and_tables(prepped)
        if not tables:
            # Return minimal response with low confidence
            resp = AnalyzeResponse(
                decision_ready=False,
                needs_manual_review=True,
                confidence_overall=0.0,
                notes=["No tables detected."]
            )
            return JSONResponse(content=json.loads(resp.model_dump_json()))

        # Take best table
        t = tables[0]
        df = t["df"]
        col_map = t["col_map"]
        metrics = t["metrics"]

        # Build simple series from labeled columns if present
        series = Series()
        def col_vals(key):
            idx = col_map.get(key)
            if idx is None: return []
            vals = [clean_number(v) for v in df.iloc[1:, idx].to_list()]
            return [v for v in vals if v is not None]

        series.cash_value_by_year = col_vals("cash_value")
        series.surrender_charge_by_year = col_vals("surrender_charge")
        series.net_surrender_value_by_year = col_vals("net_surrender_value")
        series.planned_premiums_by_year = col_vals("premium")

        # Simple verification metric placeholders
        verif = Verifications(
            net_sv_identity_rmse=None,
            year_sequence_ok=True,
            rows_parsed_pct=float(len(df) - 1) / float(len(df)) if len(df) > 1 else 0.0
        )
        metrics["rows_parsed"] = verif.rows_parsed_pct
        conf = compute_confidence(metrics)
        decision_ready = conf >= CONFIDENCE_THRESHOLD
        needs_review = not decision_ready

        # Redact PDF
        pii_coords = find_pii_coords(prepped)
        redacted_path = prepped.replace(".pdf", "-redacted.pdf")
        redact_pdf_boxes(prepped, pii_coords, redacted_path)
        redacted_b64 = b64_file(redacted_path)
        try:
            os.unlink(redacted_path)
        except Exception:
            pass


        # Proof snips
        snip_coords = find_snip_coords(df, t["page"])
        proof_snips = []
        for s in snip_coords:
            rect = fitz.Rect(s["box"])
            b64_img = crop_to_b64(prepped, s["page"], rect)
            s3_url = upload_file_to_s3(b64_img, 'image/png', '.png')
            image_data = s3_url if s3_url else b64_img
            proof_snips.append(ProofSnip(label=s["label"], page=s["page"], image_b64=image_data))

        s3_url = upload_file_to_s3(redacted_b64)
        if not s3_url:
            raise HTTPException(status_code=500, detail="Failed to upload file to S3")

        resp = AnalyzeResponse(
            decision_ready=decision_ready,
            needs_manual_review=needs_review,
            confidence_overall=conf,
            fields=Fields(
                crediting_rate=None,
                death_benefit_pattern=None,
                face_amount_structure=None,
                loan_balance_today=None
            ),
            series=series,
            verifications=verif,
            proof_snips=proof_snips,
            redacted_pdf_b64=s3_url,
            notes=[f"Columns found: {list(col_map.keys())}"]
        )

        # New logic to handle the API call
        # Temporarily remove the large Base64-encoded strings before sending to OpenAI
        # This is the key to solving the RateLimitError
        temp_resp_dict = resp.model_dump()
        if 'redacted_pdf_b64' in temp_resp_dict:
            del temp_resp_dict['redacted_pdf_b64']
        if 'proof_snips' in temp_resp_dict:
            del temp_resp_dict['proof_snips']
            
        json_string = json.dumps(temp_resp_dict)
        
        messages = [
            {"role": "system", "content": "You are deciding 1035 exchanges. Only use provided JSON. If confidence < 0.80, return Needs-Review."},
            {"role": "user", "content": json_string}
        ]
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_completion_tokens=1024 # Increased tokens for a complete response
        )

        final_output = response.choices[0].message.content.strip()

        final_response_content = {
            "analysis": final_output,
            "redacted_pdf_b64": s3_url
        }

        return JSONResponse(content=final_response_content)

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def upload_file_to_s3(b64_content: str, content_type: str = 'application/pdf', extension: str = '.pdf') -> str:
    try:
        # Decode base64 to bytes
        file_content = base64.b64decode(b64_content)
        # Generate random filename
        random_filename = str(uuid.uuid4()) + extension
        s3_key = f"extractor/{random_filename}"
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=file_content, ContentType=content_type)
        s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        return s3_url
    except Exception as e:
        print(f"Error uploading file to S3: {e}")
        return None