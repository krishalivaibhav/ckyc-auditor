"""VAIBHAV. Deterministic GATES first, then a soft score. Never multiply them together."""
from contracts.models import RiskAssessment


def assess(client_id: str, candidates, signals, prior_tier) -> RiskAssessment:
    raise NotImplementedError("gates: UAPA->CRITICAL | PAN_EXACT+active->HIGH | revoked->DOWNGRADE "
                              "| PEP->EDD | all-rejected->SUPPRESS. then soft score.")
