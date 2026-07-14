import logging
import asyncio
import httpx
from typing import List, Dict, Any
from src.schemas import Entity

logger = logging.getLogger("sanctions-agent.opensanctions")

class OpenSanctionsClient:
    """
    Client for calling the OpenSanctions /match API endpoint with automatic retry, 
    backoff, error handling, and payload mapping.
    """
    def __init__(self, api_key: str, base_url: str = "https://api.opensanctions.org", timeout: float = 5.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def match_entity(self, entity: Entity, max_retries: int = 3, base_delay: float = 0.1, backoff_factor: float = 2.0) -> List[Dict[str, Any]]:
        """
        Translates a local Entity object into FollowTheMoney structure, queries the /match 
        endpoint, manages retries, and returns parsed candidate structures.
        """
        schema = "Person" if entity.type == "person" else "Company"
        properties = {
            "name": [entity.name] + entity.aliases
        }
        if entity.type == "person":
            if entity.dob:
                properties["birthDate"] = [entity.dob]
            if entity.nationality:
                properties["nationality"] = [entity.nationality]
            if entity.din_or_cin:
                properties["idNumber"] = [entity.din_or_cin]
        else:  # company
            if entity.dob:
                properties["incorporationDate"] = [entity.dob]
            if entity.nationality:
                properties["jurisdiction"] = [entity.nationality]
            if entity.din_or_cin:
                properties["registrationNumber"] = [entity.din_or_cin]

        payload = {
            "queries": {
                "q1": {
                    "schema": schema,
                    "properties": properties
                }
            }
        }

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"

        url = f"{self.base_url}/match/default"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    
                    data = response.json()
                    results = data.get("responses", {}).get("q1", {}).get("results", [])
                    return self._parse_results(results)

                except httpx.HTTPStatusError as e:
                    logger.warning(f"OpenSanctions API HTTP status error (status {e.response.status_code}) on attempt {attempt + 1}: {e}")
                    if attempt == max_retries - 1:
                        raise e
                except httpx.RequestError as e:
                    logger.warning(f"OpenSanctions API transport/network error on attempt {attempt + 1}: {e}")
                    if attempt == max_retries - 1:
                        raise e

                delay = base_delay * (backoff_factor ** attempt)
                logger.info(f"Retrying OpenSanctions API match query in {delay} seconds...")
                await asyncio.sleep(delay)

        return []

    def _parse_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parses OpenSanctions search results to our internal/consistent Candidate shape.
        """
        candidates = []
        for res in results:
            source_list = "Watchlist"
            datasets = res.get("datasets", [])
            if datasets:
                source_list = ", ".join(datasets)

            properties = res.get("properties", {})
            topics = properties.get("topics", [])
            if "pep" in topics:
                source_list = "PEP"
            elif "sanction" in topics:
                source_list = "Sanctions"

            candidates.append({
                "candidate_id": res.get("id", ""),
                "matched_name": res.get("caption", res.get("schema", "")),
                "score": float(res.get("score", 0.0)),
                "source_list": source_list,
                "matched_fields": ["name"],
                "raw": res
            })
        return candidates

