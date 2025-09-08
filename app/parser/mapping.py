import pandas as pd
from rapidfuzz import fuzz
from typing import Dict, Any, Tuple, List

SYNONYMS = {
    "year": ["Policy Year","Year","Yr"],
    "age": ["Age","Insured Age"],
    "premium": ["Planned Premium","Scheduled Premium","Annual Outlay","Modal Premium","Premium Outlay"],
    "death_benefit": ["Death Benefit","Face Amount","Specified Amount"],
    "cash_value": ["Account Value","Accumulation Value","Cash Value","Policy Value"],
    "surrender_charge": ["Surrender Charge","Surr Chg","Surrender Fee","Surrender Penalty"],
    "net_surrender_value": ["Net Cash Surrender Value","Net Surrender Value","Net CSV","Net SV"],
    "loan_balance": ["Policy Indebtedness","Outstanding Loan","Policy Loan","Loan Balance","Policy Debt"],
    "loan_interest": ["Accrued Loan Interest","Loan Interest"],
    "withdrawals": ["Withdrawal","Loan/Withdrawal","Distribution"]
}

def clean_number(x: str):
    if x is None: return None
    s = str(x).strip()
    if s == "": return None
    s = s.replace(",", "").replace("$", "")
    # Handle year ranges like 2025-26
    if "-" in s and len(s.split("-")[0]) == 4:
        s = s.split("-")[0]
    # parentheses negative
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except Exception:
        return None

def label_columns(df: pd.DataFrame) -> Dict[str, int]:
    # Try header match first
    header_map: Dict[str, int] = {}
    headers = [str(h).strip() for h in df.columns]
    for canon, syns in SYNONYMS.items():
        best = (-1, -1)
        for idx, h in enumerate(headers):
            for s in syns + [canon]:
                score = fuzz.partial_ratio(s.lower(), h.lower())
                if score > best[0] or (score == best[0] and idx > best[1]):
                    best = (score, idx)
        if best[0] >= 70:
            header_map[canon] = best[1]
    return header_map

def shape_score(df: pd.DataFrame, col_map: Dict[str, int]) -> float:
    # More robust shape scoring based on expected patterns
    scores = []
    # Year should increment by 1
    if "year" in col_map:
        years = [clean_number(v) for v in df.iloc[1:, col_map["year"]].to_list()]
        years = [y for y in years if y is not None]
        if len(years) > 1:
            year_diffs = [years[i] - years[i-1] for i in range(1, len(years))]
            scores.append(sum(1 for d in year_diffs if d == 1) / float(len(year_diffs)))

    # Surrender charge should trend to 0
    if "surrender_charge" in col_map:
        sc = [clean_number(v) for v in df.iloc[1:, col_map["surrender_charge"]].to_list()]
        sc = [v for v in sc if v is not None]
        if len(sc) > 1 and sc[-1] == 0:
            scores.append(1.0)
        elif len(sc) > 1:
            # check if it's mostly decreasing
            decreasing = [sc[i] <= sc[i-1] for i in range(1, len(sc))]
            scores.append(sum(decreasing) / len(decreasing))


    # Net surrender value <= cash value
    if "net_surrender_value" in col_map and "cash_value" in col_map:
        nsv = [clean_number(v) for v in df.iloc[1:, col_map["net_surrender_value"]].to_list()]
        cv = [clean_number(v) for v in df.iloc[1:, col_map["cash_value"]].to_list()]
        if len(nsv) == len(cv):
            valid = [nsv[i] <= cv[i] for i in range(len(nsv)) if nsv[i] is not None and cv[i] is not None]
            if valid:
                scores.append(sum(valid) / len(valid))

    return sum(scores) / len(scores) if scores else 0.0


def reconciliation_score(df: pd.DataFrame, col_map: Dict[str, int]) -> float:
    # net_sv ~= cash_value - surrender_charge - loan - interest
    required_cols = ["net_surrender_value", "cash_value", "surrender_charge"]
    if not all(c in col_map for c in required_cols):
        return 0.0

    rows_ok = 0
    total_rows = 0
    for i in range(1, len(df)):
        try:
            nsv = clean_number(df.iloc[i, col_map["net_surrender_value"]])
            cv = clean_number(df.iloc[i, col_map["cash_value"]])
            sc = clean_number(df.iloc[i, col_map["surrender_charge"]])
            loan = clean_number(df.iloc[i, col_map.get("loan_balance", -1)]) or 0.0
            interest = clean_number(df.iloc[i, col_map.get("loan_interest", -1)]) or 0.0

            if nsv is not None and cv is not None and sc is not None:
                total_rows += 1
                # Check with a 1% tolerance
                if abs(nsv - (cv - sc - loan - interest)) <= 0.01 * abs(nsv):
                    rows_ok += 1
        except (ValueError, TypeError):
            continue
    return rows_ok / total_rows if total_rows > 0 else 0.0
