import pytest
from src.services.scoring import ScoringEngine
from src.schemas import Entity

def test_compute_name_score_exact():
    """Verify that compute_name_score returns 1.0 (exact match) for matching names."""
    entity = Entity(
        entity_id="89eb5b10-e7f0-4592-8086-599187ea1320",
        type="person",
        name="John Doe",
        source="client_input"
    )
    candidate_raw = {
        "caption": "John Doe",
        "properties": {
            "name": ["John Doe"]
        }
    }
    score = ScoringEngine.compute_name_score(entity, candidate_raw)
    assert score == 1.0

def test_compute_name_score_fuzzy_and_aliases():
    """Verify that compute_name_score computes correct fuzzy matches against query name and aliases."""
    entity = Entity(
        entity_id="89eb5b10-e7f0-4592-8086-599187ea1320",
        type="person",
        name="Johnathan Doe",
        aliases=["Johnny Doe", "J. Doe"],
        source="client_input"
    )
    # The candidate has matching alias name "Johnny Doe"
    candidate_raw = {
        "caption": "Jon Doe",
        "properties": {
            "name": ["Jon Doe"],
            "alias": ["Johnny Doe"]
        }
    }
    score = ScoringEngine.compute_name_score(entity, candidate_raw)
    # "Johnny Doe" compared to "Johnny Doe" should yield 1.0
    assert score == 1.0

    # The candidate has near match "Jonathan Doe"
    candidate_raw_fuzzy = {
        "caption": "Jonathan Doe",
        "properties": {}
    }
    score_fuzzy = ScoringEngine.compute_name_score(entity, candidate_raw_fuzzy)
    # "Johnathan Doe" vs "Jonathan Doe" should yield a high similarity score (approx 0.96)
    assert 0.90 < score_fuzzy < 1.0

def test_identify_matched_fields_person():
    """Verify matched fields are correctly extracted for person types."""
    entity = Entity(
        entity_id="89eb5b10-e7f0-4592-8086-599187ea1320",
        type="person",
        name="John Doe",
        dob="1985-05-15",
        nationality="US",
        source="client_input"
    )
    # Match both name, DOB, and nationality
    candidate_raw = {
        "caption": "John Doe",
        "properties": {
            "birthDate": ["1985-05-15"],
            "nationality": ["US"]
        }
    }
    matched = ScoringEngine.identify_matched_fields(entity, candidate_raw)
    assert "name" in matched
    assert "dob" in matched
    assert "nationality" in matched

def test_identify_matched_fields_company():
    """Verify matched fields are correctly mapped for company types (incorporationDate & jurisdiction)."""
    entity = Entity(
        entity_id="89eb5b10-e7f0-4592-8086-599187ea1321",
        type="company",
        name="Acme Corp",
        dob="2010-10-10",
        nationality="IN",
        source="client_input"
    )
    candidate_raw = {
        "caption": "Acme Corp",
        "properties": {
            "incorporationDate": ["2010-10-10"],
            "jurisdiction": ["IN"]
        }
    }
    matched = ScoringEngine.identify_matched_fields(entity, candidate_raw)
    assert "name" in matched
    assert "dob" in matched
    assert "nationality" in matched

def test_merge_scores():
    """Verify merging scores applies weights correctly and bounds the output."""
    # 50/50 split
    merged = ScoringEngine.merge_scores(local_name_score=0.8, api_score=0.9, local_weight=0.5)
    assert merged == 0.85

    # 70/30 split
    merged_weighted = ScoringEngine.merge_scores(local_name_score=0.8, api_score=0.9, local_weight=0.7)
    assert merged_weighted == 0.83  # (0.8 * 0.7) + (0.9 * 0.3) = 0.56 + 0.27 = 0.83
