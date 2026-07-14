from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID

class Entity(BaseModel):
    """
    Shared Entity contract representing a person or company to screen.
    Matches schema.md §1.
    """
    entity_id: UUID = Field(..., description="Unique UUID for the entity")
    type: Literal["person", "company"] = Field(..., description="Type of corporate entity")
    name: str = Field(..., description="Main matching name of the entity")
    aliases: List[str] = Field(default_factory=list, description="Alternative names / aliases")
    dob: Optional[str] = Field(default=None, description="Date of birth in YYYY-MM-DD format (or null)")
    nationality: Optional[str] = Field(default=None, description="ISO-3166 alpha-2 country code (or null)")
    din_or_cin: Optional[str] = Field(default=None, description="Director Identification Number / Corporate Identification Number (or null)")
    source: Literal["internal_kyc", "client_input"] = Field(..., description="Source of the entity record")

class Candidate(BaseModel):
    """
    Candidate match result returned by the sanctions engine.
    Matches schema.md §2.
    """
    candidate_id: str = Field(..., description="Identifier of the watchlist record (e.g. OpenSanctions ID)")
    matched_name: str = Field(..., description="Name of the record in the watchlist")
    score: float = Field(..., description="Calculated similarity score between 0.0 and 1.0")
    source_list: str = Field(..., description="Watchlist source, e.g. OFAC, UN, EU, PEP")
    matched_fields: List[str] = Field(..., description="Fields that contributed to the match")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Raw details fetched from the watchlist")

class CandidateMatches(BaseModel):
    """
    Result package mapping a query entity to its list of matching candidate watchlists.
    Matches schema.md §2.
    """
    query_entity_id: UUID = Field(..., description="UUID of the original query Entity")
    candidates: List[Candidate] = Field(default_factory=list, description="List of possible candidate matches")

