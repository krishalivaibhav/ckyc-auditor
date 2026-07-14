"""SNEHA. Your centrepiece. The citation validator is the whole 'AI Delivered Right' thesis."""
from contracts.models import SAR

SECTIONS = ["subject_identification", "basis_for_suspicion", "chronology_of_events",
            "evidence_summary", "risk_assessment", "recommended_action"]


def validate_sar(sar: SAR) -> SAR:
    """Every factual sentence must resolve to an [EV-nnn]. Uncited claims are STRIPPED
    into unverified_claims — not warned about. Target citation_coverage >= 0.95."""
    raise NotImplementedError
