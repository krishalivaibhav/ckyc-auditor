from rapidfuzz import fuzz
from src.schemas import Entity
from typing import List

class ScoringEngine:
    """
    Local similarity scoring engine that runs fuzzy comparison algorithms on entity attributes 
    against watchlist candidate properties using RapidFuzz.
    """
    @staticmethod
    def compute_name_score(entity: Entity, candidate_raw: dict) -> float:
        """
        Extracts all query names/aliases and candidate names/aliases, runs fuzzy match, 
        and returns the best normalized score between 0.0 and 1.0.
        """
        query_names = [entity.name] + (entity.aliases or [])
        query_names = [n.strip().lower() for n in query_names if n and n.strip()]

        if not query_names:
            return 0.0

        candidate_names = []
        caption = candidate_raw.get("caption")
        if caption:
            candidate_names.append(caption)
            
        properties = candidate_raw.get("properties", {})
        candidate_names.extend(properties.get("name", []))
        candidate_names.extend(properties.get("alias", []))
        candidate_names = [n.strip().lower() for n in candidate_names if n and n.strip()]

        if not candidate_names:
            return 0.0

        best_score = 0.0
        for qn in query_names:
            for cn in candidate_names:
                ratio = fuzz.token_sort_ratio(qn, cn)
                normalized_ratio = ratio / 100.0
                if normalized_ratio > best_score:
                    best_score = normalized_ratio
        
        return best_score

    @staticmethod
    def identify_matched_fields(entity: Entity, candidate_raw: dict, name_threshold: float = 0.7) -> List[str]:
        """
        Determines which fields triggered matching (e.g. name, dob, nationality).
        """
        matched_fields = []
        
        name_score = ScoringEngine.compute_name_score(entity, candidate_raw)
        if name_score >= name_threshold:
            matched_fields.append("name")

        properties = candidate_raw.get("properties", {})

        if entity.dob:
            candidate_dobs = []
            if entity.type == "person":
                candidate_dobs = properties.get("birthDate", [])
            else:
                candidate_dobs = properties.get("incorporationDate", [])
            
            dob_matched = False
            for cd in candidate_dobs:
                if entity.dob in cd or cd in entity.dob:
                    dob_matched = True
                    break
            if dob_matched:
                matched_fields.append("dob")

        if entity.nationality:
            candidate_countries = []
            if entity.type == "person":
                candidate_countries = properties.get("nationality", [])
            else:
                candidate_countries = properties.get("jurisdiction", [])
            
            nat_matched = False
            for cc in candidate_countries:
                if entity.nationality.strip().lower() == cc.strip().lower():
                    nat_matched = True
                    break
            if nat_matched:
                matched_fields.append("nationality")

        return matched_fields

    @staticmethod
    def merge_scores(local_name_score: float, api_score: float, local_weight: float = 0.5) -> float:
        """
        Merges local fuzzy similarity score and OpenSanctions API match confidence score.
        Both inputs are expected in range [0.0, 1.0]. Returns result in range [0.0, 1.0].
        """
        merged = (local_name_score * local_weight) + (api_score * (1.0 - local_weight))
        return round(max(0.0, min(1.0, merged)), 4)

