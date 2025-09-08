from typing import Dict

def compute_confidence(metrics: Dict[str, float]) -> float:
    # Weighted blend: header 20%, shape 25%, reconcil 35%, rows 20%
    header = metrics.get("header_strength", 0.0)
    shape = metrics.get("shape_fit", 0.0)
    recon = metrics.get("recon_success", 0.0)
    rows  = metrics.get("rows_parsed", 0.0)
    return 0.20*header + 0.25*shape + 0.35*recon + 0.20*rows
