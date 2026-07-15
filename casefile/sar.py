"""Citation-grounded SAR drafting.  Reports are structured, never free-form."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from contracts.models import Evidence, RiskAssessment, SAR

SECTIONS = ["subject_identification", "basis_for_suspicion", "chronology_of_events",
            "evidence_summary", "risk_assessment", "recommended_action"]


def validate_sar(sar: SAR) -> SAR:
    """Every factual sentence must resolve to an [EV-nnn]. Uncited claims are STRIPPED
    into unverified_claims — not warned about. Target citation_coverage >= 0.95."""
    known_ids = {e.evidence_id for e in sar.evidence}
    factual_total = cited_total = 0
    cleaned: dict[str, str] = {}
    excluded = list(sar.unverified_claims)

    for section, text in sar.sections.items():
        retained: list[str] = []
        for sentence in split_sentences(text):
            if not is_factual(sentence):
                retained.append(sentence)
                continue
            factual_total += 1
            cited = set(extract_ev_ids(sentence))
            if cited and cited <= known_ids:
                cited_total += 1
                retained.append(sentence)
            else:
                reason = "no evidence citation" if not cited else "unresolvable evidence citation"
                excluded.append(f"{strip_citations(sentence)} — EXCLUDED: {reason}. "
                                "This claim has been removed from the report.")
        cleaned[section] = " ".join(retained).strip()

    sar.sections = cleaned
    sar.unverified_claims = list(dict.fromkeys(excluded))
    sar.citation_coverage = cited_total / factual_total if factual_total else 1.0
    return sar


_SENTENCE = re.compile(
    r".+?[.!?](?:\s*\[[Ee][Vv]-\d+\])?(?=\s+|$)", re.DOTALL
)
_CITATION = re.compile(r"\[([Ee][Vv]-\d+)\]")


def split_sentences(text: str) -> list[str]:
    """A small, predictable splitter; citations stay attached to their sentence."""
    text = text.strip()
    matches = list(_SENTENCE.finditer(text))
    sentences = [match.group(0).strip() for match in matches]
    tail = text[matches[-1].end():].strip() if matches else text
    return [*sentences, *([tail] if tail else [])]


def extract_ev_ids(sentence: str) -> list[str]:
    return [item.upper() for item in _CITATION.findall(sentence)]


def strip_citations(sentence: str) -> str:
    return _CITATION.sub("", sentence).strip()


def is_factual(sentence: str) -> bool:
    """Recommendations and headings are allowed without citations; assertions are not."""
    normalized = strip_citations(sentence).strip().lower()
    if not normalized:
        return False
    return not normalized.startswith((
        "recommend ", "recommendation:", "human sign-off", "please ",
        "action: ", "could not verify:", "escalate ", "monitor ", "dismiss ",
        "request ",
    ))


def draft_sar(assessment: RiskAssessment, evidence: list[Evidence]) -> SAR:
    """Produce the six fixed SAR sections from only supplied, traceable evidence."""
    evidence = _unique_evidence([*assessment.evidence, *evidence])
    refs = _references(evidence)
    subject = _subject_name(assessment, evidence)
    primary = refs[0] if refs else None
    cite = f" [{primary}]" if primary else ""
    gates = ", ".join(assessment.gates_fired) or "no deterministic gate"

    sections = {
        "subject_identification": (
            f"The subject is {subject}; the available assessment is {assessment.assessment_id}.{cite}"
            if primary else "Subject identifiers were not supplied to the SAR drafter."
        ),
        "basis_for_suspicion": (
            f"Risk assessment {assessment.assessment_id} recorded {gates}.{cite}"
            if primary else "No cited evidence was supplied for a basis of suspicion."
        ),
        "chronology_of_events": (
            f"{assessment.assessed_at.date().isoformat()}: assessment assigned tier {assessment.tier}.{cite}"
            if primary else "No cited chronology was supplied."
        ),
        "evidence_summary": _evidence_summary(evidence),
        "risk_assessment": (
            f"The current tier is {assessment.tier} with score {assessment.score:.2f}; "
            f"gates fired: {gates}.{cite}" if primary else "Risk assessment requires human review."
        ),
        "recommended_action": _recommended_action(assessment),
    }
    sar = SAR(
        sar_id=f"SAR-{assessment.assessment_id}", case_id=f"CASE-{assessment.client_id}",
        drafted_at=datetime.now(timezone.utc), subject_name=subject, sections=sections,
        evidence=evidence,
    )
    return validate_sar(sar)


def _unique_evidence(evidence: list[Evidence]) -> list[Evidence]:
    return list({item.evidence_id: item for item in evidence}.values())


def _references(evidence: list[Evidence]) -> list[str]:
    return [item.evidence_id for item in evidence]


def _subject_name(assessment: RiskAssessment, evidence: list[Evidence]) -> str:
    # The frozen hand-off lacks Customer. Do not infer a name from a watchlist claim.
    # The client id is the only truthful subject identifier available here.
    return f"customer {assessment.client_id}"


def _evidence_summary(evidence: list[Evidence]) -> str:
    parts = []
    for status in ("CONFIRMED", "CORRELATED", "MISSING"):
        rows = [_cite_claim(item.claim, item.evidence_id)
                for item in evidence if item.status == status]
        parts.append(f"{status}: " + ("; ".join(rows) if rows else "No evidence supplied."))
    return " ".join(parts)


def _cite_claim(claim: str, evidence_id: str) -> str:
    """Attach the source to every sentence, including a compound evidence claim."""
    return " ".join(f"{sentence} [{evidence_id}]" for sentence in split_sentences(claim))


def _recommended_action(assessment: RiskAssessment) -> str:
    if assessment.tier == "CRITICAL":
        return "Recommendation: escalate to the MLRO; human sign-off is mandatory before filing."
    if assessment.tier in {"HIGH", "EDD", "EDD_LITE"}:
        return "Recommendation: route to compliance review; human sign-off is required before filing."
    return "Recommendation: monitor or dismiss after human review."


def export_pdf(sar: SAR, output_path: str | Path) -> Path:
    """Export a reviewable, self-contained SAR PDF without an extra dependency.

    The export is deliberately a rendering of the already-validated SAR: it never
    adds prose or claims, so the on-disk report preserves the citation/refusal
    guarantees of the structured artifact.
    """
    output = Path(output_path)
    lines = [f"Suspicious Activity Report — {sar.sar_id}", f"Case: {sar.case_id}",
             f"Subject: {sar.subject_name}", ""]
    for section in SECTIONS:
        lines.append(section.replace("_", " ").title())
        lines.extend(_wrap_pdf_text(sar.sections.get(section, "")))
        lines.append("")
    if sar.unverified_claims:
        lines.append("Unverified Claims Excluded")
        for claim in sar.unverified_claims:
            lines.extend(_wrap_pdf_text(claim, prefix="- "))
    lines.append(f"Citation coverage: {sar.citation_coverage:.0%}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_minimal_pdf(lines))
    return output


def _wrap_pdf_text(text: str, width: int = 92, prefix: str = "") -> list[str]:
    words, lines, line = text.split(), [], prefix
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) > width and line.strip():
            lines.append(line)
            line = f"  {word}"
        else:
            line = candidate
    return [*lines, line] if line.strip() else lines


def _minimal_pdf(lines: list[str]) -> bytes:
    """Create a compact one-page PDF using only standard PDF text operators."""
    # SAR fixture reports fit comfortably on one review page at this font size.
    commands = ["BT", "/F1 8 Tf", "45 790 Td", "10 TL"]
    for line in lines[:70]:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"({escaped}) Tj")
        commands.append("T*")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    body = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f"{number} 0 obj\n".encode())
        body.extend(obj)
        body.extend(b"\nendobj\n")
    xref = len(body)
    body.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode())
    body.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(body)
