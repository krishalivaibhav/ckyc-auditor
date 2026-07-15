"""Standalone fixture demo for the casefile vertical."""
import json
from pathlib import Path

from contracts.models import RiskAssessment
from casefile.audit import write
from casefile.sar import draft_sar
from casefile.timeline import reconstruct_timeline


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "fixtures"
    assessment = RiskAssessment(**next(row for row in json.loads(
        (root / "assessments.json").read_text()) if row["assessment_id"] == "ASM-003"))
    sar = draft_sar(assessment, assessment.evidence)
    audit = [
        write("agent:scoring", "GATE_FIRED", "RiskAssessment", "C1009", "PAN match raised risk.",
              before={"tier": "NONE", "score": 0.0},
              after={"tier": "HIGH", "score": 0.8, "dedup_key": "PAN:AGEPM6437D"}),
        write("agent:watchlist", "DOWNGRADED", "RiskAssessment", "C1009", "Order revoked.",
              before={"tier": "HIGH", "score": 0.8},
              after={"tier": "MONITOR", "score": 0.2, "dedup_key": "REVOCATION:ORD-c72b"}),
    ]
    timeline = reconstruct_timeline(audit, "C1009")
    print(f"citation coverage: {sar.citation_coverage:.0%}")
    print(f"unverified claims excluded: {len(sar.unverified_claims)}")
    print(f"audit-derived risk events: {len(timeline)}")
    for name in sar.sections:
        print(f"{name}: {sar.sections[name]}")


if __name__ == "__main__":
    main()
