import requests
import urllib.parse
from typing import List, Dict, Any

class GDELTClient:
    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    @classmethod
    def search_adverse_media(cls, entity_name: str) -> List[Dict[str, Any]]:
        """
        Searches GDELT for recent news articles mentioning the entity.
        """
        # We append keywords like "fraud", "laundering", "sanction" to narrow down adverse media
        query = f'"{entity_name}" (fraud OR money laundering OR sanction OR illegal OR court)'
        encoded_query = urllib.parse.quote(query)
        
        url = f"{cls.BASE_URL}?query={encoded_query}&mode=artlist&format=json"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "articles" in data:
                    return data["articles"]
            return []
        except requests.RequestException as e:
            print(f"Error querying GDELT: {e}")
            return []
