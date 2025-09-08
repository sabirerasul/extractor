from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ValueWithMeta(BaseModel):
    value: Optional[float] = None
    source: Optional[str] = None  # header, ledger, implied, ocr
    confidence: Optional[float] = None

class Fields(BaseModel):
    crediting_rate: Optional[ValueWithMeta] = None
    death_benefit_pattern: Optional[str] = None
    face_amount_structure: Optional[str] = None
    loan_balance_today: Optional[ValueWithMeta] = None
    loan_interest_today: Optional[ValueWithMeta] = None
    age_at_issue: Optional[int] = None
    current_age: Optional[int] = None

class Series(BaseModel):
    planned_premiums_by_year: List[float] = []
    cash_value_by_year: List[float] = []
    surrender_charge_by_year: List[float] = []
    net_surrender_value_by_year: List[float] = []

class Verifications(BaseModel):
    net_sv_identity_rmse: Optional[float] = None
    year_sequence_ok: Optional[bool] = None
    rows_parsed_pct: Optional[float] = None

class ProofSnip(BaseModel):
    label: str
    page: int
    image_b64: str

class AnalyzeResponse(BaseModel):
    decision_ready: bool = False
    needs_manual_review: bool = False
    confidence_overall: float = 0.0
    fields: Fields = Field(default_factory=Fields)
    series: Series = Field(default_factory=Series)
    verifications: Verifications = Field(default_factory=Verifications)
    proof_snips: List[ProofSnip] = []
    redacted_pdf_b64: Optional[str] = None
    notes: List[str] = []
