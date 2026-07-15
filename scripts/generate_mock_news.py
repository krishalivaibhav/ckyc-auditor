import pandas as pd
import json
import random
from datetime import datetime, timezone, timedelta

def generate_mock_news():
    print("Reading KYC dataset...")
    df = pd.read_csv("data/clients_with_fatf_ofac.csv")
    
    # Filter for high risk (PEP, Sanctions, or Sector Risk)
    high_risk = df[(df['pep_flag'] == 1) | (df['sanctions_flag'] == 1) | (df['sector_risk'] == 'High')].head(50)
    
    print(f"Found {len(high_risk)} high-risk clients. Generating mock news...")
    
    mock_articles = []
    
    sources = ["Bloomberg", "Reuters", "Financial Times", "Wall Street Journal", "Local Business Daily"]
    
    for _, row in high_risk.iterrows():
        entity = row['client_name']
        
        # 1. Generate a BENIGN (False Positive / Neutral) article
        mock_articles.append({
            "entity_name": entity, # custom field to make filtering easier for demo
            "title": f"{entity} announces Q3 earnings growth despite market headwinds",
            "description": f"The latest quarterly report from {entity} shows a strong 15% growth in revenue. CEO states they are heavily investing in new compliance and anti-fraud measures.",
            "url": f"https://mocknews.com/article/{random.randint(1000, 9999)}",
            "source": {"name": random.choice(sources)},
            "publishedAt": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 5))).isoformat()
        })
        
        # 2. Generate an ADVERSE (True Positive / Risk) article if they are sanctioned or PEP
        if row['sanctions_flag'] == 1 or row['ofac_country_flag'] == 1:
            mock_articles.append({
                "entity_name": entity,
                "title": f"BREAKING: {entity} added to international sanctions list amid money laundering probe",
                "description": f"Authorities have frozen assets linked to {entity} following a year-long investigation into alleged money laundering and violations of OFAC regulations.",
                "url": f"https://mocknews.com/article/{random.randint(1000, 9999)}",
                "source": {"name": random.choice(sources)},
                "publishedAt": (datetime.now(timezone.utc) - timedelta(hours=random.randint(2, 24))).isoformat()
            })
        elif row['pep_flag'] == 1:
             mock_articles.append({
                "entity_name": entity,
                "title": f"Top executives at {entity} questioned over alleged bribery scandal",
                "description": f"Anti-corruption regulators have summoned directors from {entity} to answer questions regarding a series of undocumented payments to foreign officials.",
                "url": f"https://mocknews.com/article/{random.randint(1000, 9999)}",
                "source": {"name": random.choice(sources)},
                "publishedAt": (datetime.now(timezone.utc) - timedelta(hours=random.randint(2, 48))).isoformat()
            })

    # Save to JSON
    out_path = "data/mock_news.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mock_articles, f, indent=2)
        
    print(f"Successfully generated {len(mock_articles)} mock articles and saved to {out_path}.")

if __name__ == "__main__":
    generate_mock_news()
