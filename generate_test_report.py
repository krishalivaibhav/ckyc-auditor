import os
import json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('signals/.env'))

from signals import kyc_list, triage_agent
from signals.models import RawArticle, WatchedEntity
from test_accuracy import false_positive_tests, true_positive_tests

def to_raw_article(data: dict) -> RawArticle:
    return RawArticle(
        entity_name=data['entity_name'],
        headline=data['title'],
        description=data['description'],
        url=data['url'],
        source_name=data['source']['name'],
        published_at=data['publishedAt'],
    )

def generate_report():
    report_lines = []
    report_lines.append("# Adverse Media Module - Test Results Report\n")
    
    report_lines.append("## 1. False Positive Suppression (News that should be ignored)\n")
    report_lines.append("These articles contain 'bad' keywords but are contextually positive or benign. The AI should suppress them.\n")
    
    for data in false_positive_tests:
        article = to_raw_article(data)
        entity = WatchedEntity(name=data['entity_name'])
        result = triage_agent.analyse(article, entity)
        
        report_lines.append(f"### Input: News about {data['entity_name']}")
        report_lines.append(f"**Headline:** {article.headline}")
        report_lines.append(f"**Description:** {article.description}")
        report_lines.append(f"**Action Expected:** Suppress (Ignore)\n")
        
        if result is None:
            report_lines.append("✅ **Output Received:** SUCCESS (Article Suppressed)\n")
            report_lines.append("> *The AI correctly determined this is not a genuinely adverse event and suppressed it.*")
        else:
            report_lines.append("❌ **Output Received:** FAILED (Article Wrongly Flagged)\n")
        report_lines.append("\n---\n")


    report_lines.append("## 2. True Positive Detection (News that should be flagged)\n")
    report_lines.append("These articles represent genuine compliance risks. The AI should flag them and provide a severity and reasoning.\n")
    
    for data in true_positive_tests:
        article = to_raw_article(data)
        entity = WatchedEntity(name=data['entity_name'])
        result = triage_agent.analyse(article, entity)
        
        report_lines.append(f"### Input: News about {data['entity_name']}")
        report_lines.append(f"**Headline:** {article.headline}")
        report_lines.append(f"**Description:** {article.description}")
        report_lines.append(f"**Action Expected:** Flag as Adverse\n")
        
        if result is not None:
            report_lines.append("✅ **Output Received:** SUCCESS (Article Flagged)\n")
            report_lines.append(f"- **Severity:** {result.severity.value.upper()}")
            report_lines.append(f"- **Confidence:** {result.confidence * 100:.0f}%")
            report_lines.append(f"- **AI Reasoning:** {result.triage_reasoning}")
        else:
            report_lines.append("❌ **Output Received:** FAILED (Article Missed)\n")
        report_lines.append("\n---\n")

    with open("test_results_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

if __name__ == "__main__":
    generate_report()
