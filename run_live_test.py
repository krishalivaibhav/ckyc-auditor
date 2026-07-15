import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('signals/.env'))

from signals import news_fetcher, triage_agent
from signals.models import WatchedEntity

def run_live():
    # We will test two real-world entities that often appear in the news 
    # for both positive business updates and regulatory/compliance issues.
    test_entities = [
        WatchedEntity(name="Adani Group", aliases=["Adani Enterprises"], entity_type="company", country="IN"),
        WatchedEntity(name="Tesla", aliases=["Elon Musk"], entity_type="company", country="US"),
        WatchedEntity(name="Paytm", aliases=["One97 Communications"], entity_type="company", country="IN")
    ]

    report_lines = []
    report_lines.append("# Live Data Test Results\n")
    report_lines.append("Testing the AI pipeline against **REAL, LIVE NEWS** fetched from NewsAPI.org right now.\n")

    for entity in test_entities:
        report_lines.append(f"## Entity: {entity.name}")
        print(f"Fetching live news for {entity.name}...")
        
        # Fetch actual news from the last 7 days
        articles = news_fetcher.fetch(entity_name=entity.name, aliases=entity.aliases, days_back=7)
        
        if not articles:
            report_lines.append("> *No recent news found on NewsAPI.*")
            print(f"No news found for {entity.name}.")
            continue

        report_lines.append(f"Fetched {len(articles)} live articles. AI Analysis below:\n")
        
        for idx, article in enumerate(articles[:5]):  # limit to top 5 to keep report readable
            report_lines.append(f"### Article {idx+1}")
            report_lines.append(f"**Headline:** {article.headline}")
            report_lines.append(f"**Source:** {article.source_name}")
            report_lines.append(f"**Published:** {article.published_at}\n")
            
            # Run through our two-stage AI pipeline
            print(f"  [{idx+1}] Analyzing: {article.headline[:60]}...")
            result = triage_agent.analyse(article, entity)
            
            if result is None:
                report_lines.append("✅ **AI Output:** SUPPRESSED (False Positive or Benign News)\n")
                report_lines.append("> *The AI read the context and determined this does not represent a severe compliance or regulatory risk.*")
            else:
                report_lines.append("🚨 **AI Output:** FLAGGED (Genuine Adverse Media)\n")
                report_lines.append(f"- **Severity:** {result.severity.value.upper()}")
                report_lines.append(f"- **Confidence:** {result.confidence * 100:.0f}%")
                report_lines.append(f"- **AI Reasoning:** {result.triage_reasoning}")
                report_lines.append(f"- **Entity Resolution Evidence:** {result.er_reasoning}")
            
            report_lines.append("\n---\n")

    with open("live_test_results.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print("Done! Results saved to live_test_results.md")

if __name__ == "__main__":
    run_live()
