"""
Continuous KYC — evaluation harness.

Runs a screener over both cohorts and reports precision / recall / FP count,
overall and per ground-truth bucket.

Ships with BASELINE: a naive batch screener — normalise the name, match against
every watchlist name AND alias, alert on any hit. This is what a traditional
compliance tool does, and it is the number your system has to beat.

To evaluate YOUR system, implement a screener with the same signature and pass it
to `evaluate()`:

    def my_screener(customer: dict, wl: Watchlist) -> tuple[bool, str, str]:
        '''returns (alert, tier, reason)'''

Run:  python3 evaluate.py
"""
import csv, re, unicodedata
from pathlib import Path
from collections import defaultdict

OUT = Path("/mnt/user-data/outputs")
HON = re.compile(r"^(shri|shrimati|smt|mr|mrs|ms|dr|prof|sh|md|mohd)\.?\s+", re.I)

TIER_RANK = {"NONE": 0, "EDD_LITE": 1, "EDD": 2, "HIGH": 3, "CRITICAL": 4}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = s.replace(",", " ")
    s = HON.sub("", s.strip())
    s = re.sub(r"[^A-Za-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip().upper()


class Watchlist:
    """The canonical reference side. Real data, never noisy."""

    def __init__(self, path=OUT / "watchlist_canonical.csv"):
        self.rows = list(csv.DictReader(open(path)))
        self.by_pan = {}
        self.by_name = defaultdict(list)     # normalised full name -> rows
        self.by_alias = defaultdict(list)    # normalised alias     -> rows
        for r in self.rows:
            if r["pan"]:
                self.by_pan[r["pan"].strip().upper()] = r
            self.by_name[norm(r["name"])].append(r)
            if r["list"] == "MHA_UAPA" and r["extra"]:
                for a in r["extra"].split(";"):
                    if a.strip():
                        self.by_alias[norm(a)].append(r)

    def tier_for(self, row):
        L = row["list"]
        if L == "MHA_UAPA":
            return "CRITICAL"
        if L == "NSE_SEBI_DEBARRED":
            return "HIGH" if row["extra"] == "active" else "NONE"
        if L in ("SABHA_PEP_CURRENT", "SABHA_PEP_FORMER"):
            return "EDD"
        if L == "SABHA_RCA":
            return "EDD_LITE"
        return "NONE"


# ---------------------------------------------------------------- BASELINE
def baseline_screener(cust, wl):
    """Naive batch screening: any name or alias match -> alert. No ER at all."""
    n = norm(cust["client_name"])
    hits = wl.by_name.get(n, []) + wl.by_alias.get(n, [])
    if not hits:
        return False, "NONE", ""
    best = max(hits, key=lambda r: TIER_RANK[wl.tier_for(r)])
    t = wl.tier_for(best)
    if t == "NONE":
        t = "HIGH"          # naive tools alert on revoked orders too
    return True, t, f"name match -> {best['list']}"


# ---------------------------------------------------------------- metrics
def evaluate(screener, cohort, wl, label):
    cust = {r["client_id"]: r for r in csv.DictReader(open(OUT / f"customers_{cohort}.csv"))}
    truth = list(csv.DictReader(open(OUT / f"ground_truth_{cohort}.csv")))

    tp = fp = fn = tn = 0
    per_bucket = defaultdict(lambda: {"n": 0, "fired": 0, "correct": 0})
    tier_ok = tier_wrong = 0

    for t in truth:
        c = cust[t["client_id"]]
        alert, tier, _ = screener(c, wl)
        want = bool(int(t["expected_alert"]))
        b = per_bucket[t["bucket"]]
        b["n"] += 1
        b["fired"] += int(alert)
        b["correct"] += int(alert == want)
        if alert and want:
            tp += 1
            (tier_ok := tier_ok + 1) if tier == t["expected_tier"] else None
            if tier != t["expected_tier"]:
                tier_wrong += 1
        elif alert and not want:
            fp += 1
        elif not alert and want:
            fn += 1
        else:
            tn += 1

    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    n = len(truth)

    print(f"\n{'='*74}\n{label}  |  cohort={cohort}  n={n:,}  prevalence={(tp+fn)/n:.2%}\n{'='*74}")
    print(f"  alerts raised : {tp+fp:,}     (a human must review every one of these)")
    print(f"  TP {tp:<5}  FP {fp:<6}  FN {fn:<5}  TN {tn:,}")
    print(f"  precision {prec:.3f}   recall {rec:.3f}   F1 {f1:.3f}")
    if tp:
        print(f"  tier correct on TPs: {tier_ok}/{tp}  (wrong tier on {tier_wrong})")
    print(f"\n  {'bucket':<20}{'n':>7}{'fired':>8}{'expected':>10}{'correct':>9}")
    for k in sorted(per_bucket):
        b = per_bucket[k]
        want = "FIRE" if k in ("A_TRUE_SANCTION", "D_TRUE_PEP", "E_TRUE_RCA",
                               "G_TRUE_UAPA") else "SILENT"
        mark = "" if b["correct"] == b["n"] else "  <-- "
        print(f"  {k:<20}{b['n']:>7,}{b['fired']:>8,}{want:>10}"
              f"{b['correct']:>6,}/{b['n']:<6,}{mark}")
    return {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


if __name__ == "__main__":
    wl = Watchlist()
    print(f"watchlist loaded: {len(wl.rows):,} canonical entries  "
          f"({len(wl.by_pan):,} with PAN, {len(wl.by_alias):,} alias keys)")

    r_stress = evaluate(baseline_screener, "stress", wl, "BASELINE — naive name/alias screening")
    r_real = evaluate(baseline_screener, "realistic", wl, "BASELINE — naive name/alias screening")

    print(f"\n{'='*74}\nBASE-RATE EFFECT (same screener, same seeded entities)\n{'='*74}")
    print(f"  {'':<14}{'prevalence':>12}{'precision':>12}{'recall':>10}{'false pos':>12}")
    print(f"  {'stress':<14}{'6.10%':>12}{r_stress['precision']:>12.3f}"
          f"{r_stress['recall']:>10.3f}{r_stress['fp']:>12,}")
    print(f"  {'realistic':<14}{'0.20%':>12}{r_real['precision']:>12.3f}"
          f"{r_real['recall']:>10.3f}{r_real['fp']:>12,}")
    print("\n  ^ this is the slide. Precision collapses at a realistic base rate")
    print("    even though recall is unchanged. Your ER gates are what hold it up.")
