import sys
from watchlist.index import ScreeningIndex

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_demo():
    print("Initializing ScreeningIndex...")
    try:
        index = ScreeningIndex()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please build the watchlist first by running: python -m watchlist.build")
        sys.exit(1)
    
    name = sys.argv[1] if len(sys.argv) > 1 else "Dipak Dwiwedi"
    pan = sys.argv[2] if len(sys.argv) > 2 else "ATDPD4055C"
    
    print(f"\nSearching for Name: '{name}' | PAN: '{pan}'")
    candidates = index.candidates(name, pan)
    
    if not candidates:
        print("No matches found.")
        return
        
    print(f"Found {len(candidates)} match(es):\n")
    for idx, c in enumerate(candidates, 1):
        print(f"--- Match #{idx} ---")
        print(f"watchlist_id:        {c.watchlist_id}")
        print(f"list:                {c.list}")
        print(f"entity_type:         {c.entity_type}")
        print(f"name:                {c.name}")
        print(f"aliases:             {c.aliases}")
        print(f"alias_quality:       {c.alias_quality}")
        print(f"PAN:                 {c.pan}")
        print(f"DOB:                 {c.dob}")
        print(f"party:               {c.party}")
        print(f"status:              {c.status}")
        print(f"order_id:            {c.order_id}")
        print(f"order_date:          {c.order_date}")
        print(f"official source URLs: {c.source_url}")
        print(f"first_seen:          {c.first_seen}")
        print(f"last_change:         {c.last_change}")
        print("-" * 30)

if __name__ == "__main__":
    run_demo()
