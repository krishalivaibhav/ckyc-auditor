from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('signals/.env'))

from signals import kyc_list, triage_agent
from signals.models import RawArticle, WatchedEntity
from datetime import datetime, timezone

kyc_list.seed_defaults()

# === Articles that should NOT be flagged (false positives) ===
false_positive_tests = [
    {
        'entity_name': 'Infosys',
        'title': 'Infosys launches new initiative to fight against financial fraud',
        'description': 'Infosys announced a new AI-powered system to help banks detect and prevent fraud.',
        'url': 'https://example.com/1',
        'publishedAt': '2026-07-15',
        'source': {'name': 'Economic Times'}
    },
    {
        'entity_name': 'Adani Group',
        'title': 'Adani Group wins legal case against fraud allegations',
        'description': 'The Supreme Court cleared Adani Group of all fraud charges, calling the claims baseless.',
        'url': 'https://example.com/2',
        'publishedAt': '2026-07-15',
        'source': {'name': 'Mint'}
    },
    {
        'entity_name': 'Infosys',
        'title': 'Infosys partners with RBI to strengthen cybersecurity measures',
        'description': 'Infosys will help the Reserve Bank of India build defences against money laundering detection.',
        'url': 'https://example.com/5',
        'publishedAt': '2026-07-15',
        'source': {'name': 'Livemint'}
    },
]

# === Articles that SHOULD be flagged (true positives) ===
true_positive_tests = [
    {
        'entity_name': 'Nirav Modi',
        'title': 'Nirav Modi found guilty of defrauding PNB of 13000 crores',
        'description': 'UK court convicts Nirav Modi in the Punjab National Bank fraud case involving 13000 crore rupees in fraudulent letters of undertaking.',
        'url': 'https://example.com/3',
        'publishedAt': '2026-07-15',
        'source': {'name': 'NDTV'}
    },
    {
        'entity_name': 'Adani Group',
        'title': 'SEBI bars Adani Group directors for market manipulation',
        'description': 'Securities and Exchange Board of India has issued orders barring 4 Adani Group directors for alleged stock price manipulation and insider trading.',
        'url': 'https://example.com/4',
        'publishedAt': '2026-07-15',
        'source': {'name': 'Business Standard'}
    },
    {
        'entity_name': 'Adani Group',
        'title': 'CBI arrests senior Adani executive in bribery case',
        'description': 'The Central Bureau of Investigation arrested a top executive of Adani Group in connection with a bribery scandal involving government contracts.',
        'url': 'https://example.com/6',
        'publishedAt': '2026-07-15',
        'source': {'name': 'The Hindu'}
    },
]

def to_raw_article(data: dict) -> RawArticle:
    return RawArticle(
        entity_name=data['entity_name'],
        headline=data['title'],
        description=data['description'],
        url=data['url'],
        source_name=data['source']['name'],
        published_at=data['publishedAt'],
    )

print("\n=== TEST 1: FALSE POSITIVE SUPPRESSION (should NOT be flagged) ===")
fp_suppressed = 0
for data in false_positive_tests:
    article = to_raw_article(data)
    entity = kyc_list.get_entity(data['entity_name']) or WatchedEntity(name=data['entity_name'])
    result = triage_agent.analyse(article, entity)
    
    if result is None:
        fp_suppressed += 1
        print(f"  PASS (correctly suppressed): {article.headline[:75]}")
    else:
        print(f"  FAIL (wrongly flagged)     : {article.headline[:75]}")

print("\n=== TEST 2: TRUE POSITIVE DETECTION (should be flagged) ===")
tp_detected = 0
for data in true_positive_tests:
    article = to_raw_article(data)
    entity = kyc_list.get_entity(data['entity_name']) or WatchedEntity(name=data['entity_name'])
    result = triage_agent.analyse(article, entity)
    
    if result is not None:
        tp_detected += 1
        print(f"  PASS (correctly flagged): {article.headline[:65]}")
        print(f"        Severity={result.severity.value.upper()} | Confidence={result.confidence:.0%}")
        print(f"        Reason: {result.triage_reasoning}")
    else:
        print(f"  FAIL (missed)           : {article.headline[:75]}")

total = len(false_positive_tests) + len(true_positive_tests)
correct = fp_suppressed + tp_detected
print("\n=== ACCURACY REPORT ===")
print(f"False Positive Suppression : {fp_suppressed}/{len(false_positive_tests)} articles correctly suppressed")
print(f"True Positive Detection    : {tp_detected}/{len(true_positive_tests)} adverse articles correctly caught")
print(f"Overall Accuracy           : {correct}/{total} = {correct/total*100:.0f}%")
