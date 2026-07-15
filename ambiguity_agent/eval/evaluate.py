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
import sys, csv, re, unicodedata
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT))   # allow `python eval/evaluate.py` to import core/contracts

from contracts.models import Customer
from core.blocking import Blocker, load_watchlist_entries
from core.resolver import resolve

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

    def __init__(self, path=DATA / "watchlist_canonical.csv"):
        self.rows = list(csv.DictReader(open(path, encoding="utf-8")))
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


# ---------------------------------------------------------------- OURS (Rungs 0-3)
def _tier_of(list_name, status):
    """List -> tier. Same deterministic map the baseline uses (scoring/downgrade
    is a later session, so tier assignment is held identical for a fair A/B)."""
    if list_name == "MHA_UAPA":
        return "CRITICAL"
    if list_name == "NSE_SEBI_DEBARRED":
        return "HIGH" if status == "active" else "NONE"
    if list_name in ("SABHA_PEP_CURRENT", "SABHA_PEP_FORMER"):
        return "EDD"
    if list_name == "SABHA_RCA":
        return "EDD_LITE"
    return "NONE"


def _to_customer(r):
    return Customer(
        client_id=r["client_id"], client_name=r["client_name"],
        client_type=r["client_type"], pan=(r.get("pan") or None),
        country=r.get("country", "IN"), sector=r.get("sector", ""),
        branch=r.get("branch", ""), onboarding_date=r["onboarding_date"],
        exposure_inr=int(r["exposure_inr"]), last_kyc_refresh=r["last_kyc_refresh"])


def ladder_screener(cust, wl):
    """Rungs 0-3: block -> PAN gates -> name-exact fallback. Same signature as
    baseline_screener. A confirmed candidate alerts; a customer whose only
    candidates were REJECTED is suppressed with a reason (the product)."""
    blk = getattr(wl, "_blocker", None)
    if blk is None:
        blk = wl._blocker = Blocker(load_watchlist_entries(wl.rows))

    c = _to_customer(cust)
    cands = resolve(c, blk.candidates(c.client_name, c.pan))
    confirmed = [x for x in cands if x.decision == "CONFIRMED"]

    if confirmed:
        def tier_rank(x):
            t = _tier_of(x.features.get("list"), x.features.get("list_status"))
            return TIER_RANK.get(t, 0)
        best = max(confirmed, key=tier_rank)
        t = _tier_of(best.features.get("list"), best.features.get("list_status"))
        if t == "NONE":
            t = "HIGH"      # confirmed PAN match to a revoked order; downgrade is later
        return True, t, f"{best.match_method} -> {best.features.get('list')}"

    if cands:               # everything we found was rejected -> suppression log
        return False, "NONE", " | ".join(x.rejection_reason for x in cands if x.rejection_reason)
    return False, "NONE", "no watchlist candidate"


# ---------------------------------------------------------------- metrics
def evaluate(screener, cohort, wl, label):
    cust = {r["client_id"]: r for r in csv.DictReader(open(DATA / f"customers_{cohort}.csv", encoding="utf-8"))}
    truth = list(csv.DictReader(open(DATA / f"ground_truth_{cohort}.csv", encoding="utf-8")))

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
    return {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn,
            "per_bucket": {k: dict(v) for k, v in per_bucket.items()}}


FIRE_BUCKETS = ("A_TRUE_SANCTION", "D_TRUE_PEP", "E_TRUE_RCA", "G_TRUE_UAPA")


def _reduction_ratio(wl, cohort):
    blk = getattr(wl, "_blocker", None) or Blocker(load_watchlist_entries(wl.rows))
    custs = list(csv.DictReader(open(DATA / f"customers_{cohort}.csv", encoding="utf-8")))
    s = blk.stats(custs)
    print(f"\n{'='*74}\nRUNG 0 — BLOCKING REDUCTION  (cohort={cohort})\n{'='*74}")
    print(f"  watchlist entries        : {s['watchlist_size']:,}")
    print(f"  avg candidates / customer: {s['avg_candidates']:.1f}   (max {s['max_candidates']})")
    print(f"  reduction ratio          : {s['reduction_ratio']:,.0f}x  "
          f"({s['watchlist_size']:,} -> {s['avg_candidates']:.1f})")
    print(f"  customers over 50 cands  : {s['pct_over_50']:.2%}   (target: <50/customer)")


def _before_after(base, ours, cohort, fp_base, fp_ours):
    print(f"\n{'='*74}\nBEFORE / AFTER  (cohort={cohort})\n{'='*74}")
    print(f"  {'':<12}{'precision':>11}{'recall':>9}{'F1':>8}{'TP':>6}{'FP':>7}{'FN':>6}")
    print(f"  {'BASELINE':<12}{base['precision']:>11.3f}{base['recall']:>9.3f}"
          f"{base['f1']:>8.3f}{base['tp']:>6}{base['fp']:>7,}{base['fn']:>6}")
    print(f"  {'OURS 0-3':<12}{ours['precision']:>11.3f}{ours['recall']:>9.3f}"
          f"{ours['f1']:>8.3f}{ours['tp']:>6}{ours['fp']:>7,}{ours['fn']:>6}")
    dp = ours['precision'] - base['precision']
    dr = ours['recall'] - base['recall']
    print(f"  {'Δ':<12}{dp:>+11.3f}{dr:>+9.3f}{ours['f1']-base['f1']:>+8.3f}"
          f"{ours['tp']-base['tp']:>+6}{ours['fp']-base['fp']:>+7,}{ours['fn']-base['fn']:>+6}")

    print(f"\n  per-bucket fired (want FIRE=high, SILENT=low)")
    print(f"  {'bucket':<20}{'n':>6}{'baseline':>10}{'ours':>7}{'want':>9}   fixed by")
    fixer = {"B_FP_PAN_MISMATCH": "PAN mismatch gate (Rung 3)",
             "C_FP_PEP_COLLISION": "cross-list no-link (Rung 5, later)",
             "F_FP_UAPA_ALIAS": "alias-quality gate (Rung 4, later)",
             "A_TRUE_SANCTION": "PAN exact (Rung 1)",
             "G_TRUE_UAPA": "transliteration (Rung 6, later)",
             "D_TRUE_PEP": "phonetic/fuzzy (Rung 6, later)",
             "E_TRUE_RCA": "phonetic/fuzzy (Rung 6, later)"}
    for k in sorted(base["per_bucket"]):
        b, o = base["per_bucket"][k], ours["per_bucket"][k]
        want = "FIRE" if k in FIRE_BUCKETS else "SILENT"
        print(f"  {k:<20}{b['n']:>6,}{b['fired']:>10,}{o['fired']:>7,}{want:>9}   {fixer.get(k,'')}")


if __name__ == "__main__":
    wl = Watchlist()
    print(f"watchlist loaded: {len(wl.rows):,} canonical entries  "
          f"({len(wl.by_pan):,} with PAN, {len(wl.by_alias):,} alias keys)")

    b_stress = evaluate(baseline_screener, "stress", wl, "BASELINE — naive name/alias screening")
    b_real = evaluate(baseline_screener, "realistic", wl, "BASELINE — naive name/alias screening")

    o_stress = evaluate(ladder_screener, "stress", wl, "OURS — ER ladder Rungs 0-3 (PAN gates)")
    o_real = evaluate(ladder_screener, "realistic", wl, "OURS — ER ladder Rungs 0-3 (PAN gates)")

    _reduction_ratio(wl, "realistic")
    _before_after(b_stress, o_stress, "stress", b_stress["fp"], o_stress["fp"])
    _before_after(b_real, o_real, "realistic", b_real["fp"], o_real["fp"])

    print(f"\n{'='*74}\nHEADLINE — both base rates, baseline vs ours\n{'='*74}")
    print(f"  {'':<22}{'prevalence':>11}{'precision':>11}{'recall':>9}{'false pos':>11}")
    for lbl, rate, r in [("BASELINE  stress", "6.10%", b_stress),
                         ("BASELINE  realistic", "0.20%", b_real),
                         ("OURS 0-3  stress", "6.10%", o_stress),
                         ("OURS 0-3  realistic", "0.20%", o_real)]:
        print(f"  {lbl:<22}{rate:>11}{r['precision']:>11.3f}{r['recall']:>9.3f}{r['fp']:>11,}")
    print("\n  Rungs 0-3 are PAN-only. B_FP_PAN_MISMATCH falls to the Rung-3 gate and")
    print("  PAN-exact recovers noise-broken sanction TPs, so precision AND recall rise.")
    print("  C/F (cross-list, bare-alias) and noise-broken PEP/UAPA await Rungs 4-6.")
