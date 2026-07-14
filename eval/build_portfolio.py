"""
Continuous KYC — synthetic customer portfolio generator (v2).

v2 adds:
  1. NOISE INJECTION  — the bank's book is messy, the regulator's list is canonical.
     Typos, transliteration variants, dropped middle names, "SURNAME, First"
     ordering, initials, honorifics, and ~18% missing PANs are applied to the
     CUSTOMER record only. Ground truth is unchanged: a typo'd true positive is
     still a true positive, it is just harder to find. This stops the PAN gate
     from being a free win and forces the fuzzy/phonetic layer to earn its place.

  2. DUAL BASE RATE   — precision is base-rate dependent. Emits two cohorts with
     the SAME seeded entities:
        stress     ~6%    (2,000 customers)   — 20x reality, exercises every path
        realistic  ~0.2%  (60,000 customers)  — the rate a real book sees
     Report metrics at both. The degradation is the honest slide.

Outputs (/mnt/user-data/outputs):
  customers_stress.csv      ground_truth_stress.csv
  customers_realistic.csv   ground_truth_realistic.csv
  watchlist_canonical.csv   — flattened real lists; the reference side of ER
"""
import json, csv, random, re, unicodedata
from pathlib import Path
from datetime import date, timedelta
from collections import Counter

SEED = 20260714
ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "data"
OUT = ROOT / "data"
OUT.mkdir(parents=True, exist_ok=True)

STRESS_N = 2_000
REALISTIC_N = 60_000
MISSING_PAN_RATE = 0.18
NOISE_RATE = 0.45

HON = re.compile(r"^(shri|shrimati|smt|mr|mrs|ms|dr|prof|sh|md|mohd)\.?\s+", re.I)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = HON.sub("", s.strip())
    s = re.sub(r"[^A-Za-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip().upper()


def load_ndjson(p):
    with open(UP / p) as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


# ============================================================ 1. real watchlists
debarred_persons, debarred_orgs = [], []
for d in load_ndjson("targets_nested_stock_.json"):
    if d.get("schema") != "LegalEntity":
        continue
    p = d.get("properties", {})
    name = (p.get("name") or [None])[0]
    if not name:
        continue
    pans = [x.strip().upper() for x in p.get("taxNumber", []) if len(x.strip()) == 10]
    sancs = p.get("sanctions", []) or []
    active = any(
        not re.search(r"revok", " ".join(s.get("properties", {}).get("duration", [])), re.I)
        for s in sancs)
    rec = {"name": name, "pan": pans[0] if pans else "", "os_id": d["id"],
           "active": active, "list": "NSE_SEBI_DEBARRED"}
    if rec["pan"] and rec["pan"][3] == "P":
        debarred_persons.append(rec)
    elif rec["pan"] and rec["pan"][3] in "CHF":
        debarred_orgs.append(rec)

pep_current, pep_former, rca = [], [], []
for d in load_ndjson("targets_nested_sabha_.json"):
    if d.get("schema") != "Person":
        continue
    p = d.get("properties", {})
    name = (p.get("name") or [None])[0]
    if not name:
        continue
    occs = p.get("positionOccupancies", []) or p.get("occupancies", []) or []
    cur = any("current" in (o.get("properties", {}).get("status") or [])
              for o in occs if isinstance(o, dict))
    rec = {"name": name, "pan": "", "os_id": d["id"],
           "dob": (p.get("birthDate") or [""])[0],
           "party": (p.get("political") or [""])[0], "list": "SABHA_PEP"}
    t = p.get("topics", [])
    if "role.pep" in t:
        (pep_current if cur else pep_former).append(rec)
    elif "role.rca" in t:
        rec["list"] = "SABHA_RCA"
        rca.append(rec)

uapa_full, uapa_bare = [], []
for d in load_ndjson("targets_nested_mha_.json"):
    if d.get("schema") != "Person":
        continue
    p = d.get("properties", {})
    name = (p.get("name") or [None])[0]
    if not name:
        continue
    aliases = [a.strip().strip("\u201d)") for a in p.get("alias", []) if a.strip()]
    uapa_full.append({"name": name, "pan": "", "os_id": d["id"],
                      "aliases": aliases, "list": "MHA_UAPA"})
    for a in aliases:
        if len(a.split()) <= 2 and not re.fullmatch(r"\(?[A-Z\-()]{2,8}\)?", a):
            uapa_bare.append(a)
uapa_bare = sorted(set(uapa_bare))

pep_names = {norm(r["name"]) for r in pep_current + pep_former + rca}
deb_names = {norm(r["name"]) for r in debarred_persons}
collisions = sorted(pep_names & deb_names)

print(f"[real] debarred_persons={len(debarred_persons)}  debarred_orgs={len(debarred_orgs)}")
print(f"[real] pep_current={len(pep_current)}  pep_former={len(pep_former)}  rca={len(rca)}")
print(f"[real] uapa_full={len(uapa_full)}  uapa_bare_aliases={len(uapa_bare)}")
print(f"[real] PEP<->debarred name collisions={len(collisions)}")

with open(OUT / "watchlist_canonical.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["watchlist_id", "list", "name", "pan", "extra"])
    for r in debarred_persons + debarred_orgs:
        w.writerow([r["os_id"], r["list"], r["name"], r["pan"],
                    "active" if r["active"] else "revoked"])
    for r in pep_current:
        w.writerow([r["os_id"], "SABHA_PEP_CURRENT", r["name"], "", r["party"]])
    for r in pep_former:
        w.writerow([r["os_id"], "SABHA_PEP_FORMER", r["name"], "", r["party"]])
    for r in rca:
        w.writerow([r["os_id"], "SABHA_RCA", r["name"], "", ""])
    for r in uapa_full:
        w.writerow([r["os_id"], "MHA_UAPA", r["name"], "", ";".join(r["aliases"])])

# ============================================================ 2. noise injection
TRANSLIT = [("Mohammed", "Mohammad"), ("Mohammad", "Muhammad"), ("Muhammad", "Mohd."),
            ("Kumar", "Kumaar"), ("Sharma", "Sarma"), ("Chowdhury", "Choudhary"),
            ("Krishnan", "Krishnaan"), ("Reddy", "Reddi"), ("Gupta", "Gupte"),
            ("Sheikh", "Shaikh"), ("Syed", "Sayed"), ("Hussain", "Hussein"),
            ("Ahmed", "Ahmad"), ("Singh", "Sing"), ("ee", "i"), ("oo", "u"), ("ph", "f")]


def typo(s):
    if len(s) < 5:
        return s
    i = random.randrange(1, len(s) - 1)
    op = random.choice(["swap", "drop", "dup"])
    if op == "swap":
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if op == "drop":
        return s[:i] + s[i + 1:]
    return s[:i] + s[i] + s[i:]


def noisify(name):
    n, ops = name, []
    for _ in range(random.randint(1, 2)):
        k = random.choice(["typo", "translit", "initials", "reorder",
                           "drop_middle", "honorific", "case"])
        parts = n.split()
        if k == "typo":
            j = random.randrange(len(parts))
            parts[j] = typo(parts[j])
            n = " ".join(parts)
        elif k == "translit":
            src, dst = random.choice(TRANSLIT)
            if src.lower() not in n.lower():
                continue
            n = re.sub(src, dst, n, flags=re.I, count=1)
        elif k == "initials" and len(parts) >= 2:
            n = " ".join([p[0] + "." for p in parts[:-1]] + [parts[-1]])
        elif k == "reorder" and len(parts) >= 2:
            n = f"{parts[-1]}, {' '.join(parts[:-1])}"
        elif k == "drop_middle" and len(parts) >= 3:
            n = f"{parts[0]} {parts[-1]}"
        elif k == "honorific":
            n = random.choice(["Shri ", "Mr. ", "Smt. ", "Dr. "]) + n
        elif k == "case":
            n = n.upper() if random.random() < .5 else n.lower()
        else:
            continue
        ops.append(k)
    return n, ("+".join(ops) if ops else "none")


# ============================================================ 3. portfolio
PAN_L = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
FIRST = ["Rohan", "Aditya", "Priya", "Sneha", "Karan", "Neha", "Vikram", "Ananya", "Rahul",
         "Divya", "Arjun", "Meera", "Siddharth", "Kavya", "Nikhil", "Pooja", "Varun", "Ritu",
         "Aman", "Shreya", "Harsh", "Tanvi", "Kunal", "Isha", "Deepak", "Nisha", "Sanjay",
         "Farah", "Imran", "Zoya", "Rehan", "Anjali", "Gaurav", "Swati", "Manav", "Preeti"]
LAST = ["Mehta", "Iyer", "Reddy", "Nair", "Bose", "Chatterjee", "Deshmukh", "Pillai", "Rao",
        "Bhattacharya", "Sengupta", "Kulkarni", "Menon", "Trivedi", "Chauhan", "Bhardwaj",
        "Saxena", "Bhatt", "Dutta", "Ghosh", "Joshi", "Malhotra", "Sethi", "Vaidya"]
CORP_A = ["Meridian", "Aravali", "Sundara", "Kaveri", "Nilgiri", "Konark", "Vindhya",
          "Satpura", "Zenith", "Anantara", "Bhaskar", "Chandra"]
CORP_B = ["Infra", "Capital", "Exports", "Textiles", "Logistics", "Chemicals", "Holdings",
          "Ventures", "Industries", "Enterprises"]
CORP_C = ["Pvt Ltd", "Ltd", "LLP", "India Pvt Ltd"]
SECTORS = ["Import/Export", "Real Estate", "Financial Services", "Infrastructure",
           "Gems & Jewellery", "Pharma", "IT Services", "Commodities", "NBFC", "Agri"]
BRANCH = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad"]


def build(n_total, tag):
    random.seed(SEED)
    used = {r["pan"] for r in debarred_persons + debarred_orgs if r["pan"]}
    rows, truth, ctr = [], [], [1000]

    def pan(kind, sur):
        while True:
            p = ("".join(random.choice(PAN_L) for _ in range(3)) + kind
                 + (sur[:1].upper() if sur[:1].isalpha() else "X")
                 + f"{random.randint(0,9999):04d}" + random.choice(PAN_L))
            if p not in used:
                used.add(p)
                return p

    def add(name, ctype, p, bucket, fire, tier, reason, link="", noise=False):
        ctr[0] += 1
        cid = f"C{ctr[0]}"
        disp, ntag = (noisify(name) if (noise and random.random() < NOISE_RATE)
                      else (name, "none"))
        shown = "" if (p and random.random() < MISSING_PAN_RATE) else p
        onb = date(2019, 1, 1) + timedelta(days=random.randint(0, 2400))
        rows.append({"client_id": cid, "client_name": disp, "client_type": ctype,
                     "pan": shown, "country": "IN", "sector": random.choice(SECTORS),
                     "branch": random.choice(BRANCH), "onboarding_date": onb.isoformat(),
                     "exposure_inr": int(random.lognormvariate(14.5, 1.4)),
                     "last_kyc_refresh": (onb + timedelta(days=random.randint(200, 1100))).isoformat()})
        truth.append({"client_id": cid, "canonical_name": name, "recorded_name": disp,
                      "bucket": bucket, "expected_alert": int(fire), "expected_tier": tier,
                      "name_noise": ntag, "pan_present": int(bool(shown)),
                      "reason": reason, "linked_watchlist_id": link})

    for r in random.sample([r for r in debarred_persons if r["active"]], 40):
        add(r["name"], "Individual", r["pan"], "A_TRUE_SANCTION", True, "HIGH",
            "PAN exact-matches an active NSE/SEBI debarment", r["os_id"], noise=True)
    for r in random.sample([r for r in debarred_orgs if r["active"]], 10):
        add(r["name"], "Corporate", r["pan"], "A_TRUE_SANCTION", True, "HIGH",
            "PAN exact-matches an active NSE/SEBI debarment (corporate)", r["os_id"], noise=True)
    for r in random.sample(debarred_persons, 60):
        add(r["name"], "Individual", pan("P", r["name"].split()[-1]), "B_FP_PAN_MISMATCH",
            False, "NONE",
            "Name matches a debarred entity but PAN differs -> different person",
            r["os_id"], noise=True)
    for nm in random.sample(collisions, min(30, len(collisions))):
        disp = next(r["name"] for r in debarred_persons if norm(r["name"]) == nm)
        add(disp, "Individual", pan("P", disp.split()[-1]), "C_FP_PEP_COLLISION", False, "NONE",
            "Name on BOTH the PEP register and the debarred list; the two sources share no "
            "identifier -> must not auto-link", "", noise=True)
    for r in random.sample(pep_current or pep_former, 40):
        add(r["name"], "Individual", pan("P", r["name"].split()[-1]), "D_TRUE_PEP", True, "EDD",
            f"Sitting MP ({r['party'] or 'party n/a'}) -> PEP / enhanced due diligence, "
            f"NOT an adverse-media hit", r["os_id"], noise=True)
    for r in random.sample(rca, 25):
        add(r["name"], "Individual", pan("P", r["name"].split()[-1]), "E_TRUE_RCA", True,
            "EDD_LITE", "Relative/close associate of a PEP (Sabha family graph)",
            r["os_id"], noise=True)
    dangerous = [a for a in uapa_bare if len(a) > 2]
    for a in random.sample(dangerous, min(35, len(dangerous))):
        nm = a if len(a.split()) > 1 else f"{a} {random.choice(LAST)}"
        add(nm, "Individual", pan("P", nm.split()[-1]), "F_FP_UAPA_ALIAS", False, "NONE",
            f"Matches the bare UAPA alias '{a}'. Single-token / common-name aliases must "
            f"never trigger alone.", "", noise=True)
    for r in random.sample(uapa_full, 5):
        for v in ([r["name"]] + [a for a in r["aliases"] if len(a.split()) >= 3][:1])[:2]:
            add(v, "Individual", pan("P", v.split()[-1]), "G_TRUE_UAPA", True, "CRITICAL",
                f"Full-name match to a UAPA 4th-schedule designated individual "
                f"(canonical: {r['name']})", r["os_id"], noise=True)

    while len(rows) < n_total:
        if random.random() < 0.62:
            nm = f"{random.choice(FIRST)} {random.choice(LAST)}"
            add(nm, "Individual", pan("P", nm.split()[-1]), "H_CLEAN", False, "NONE",
                "Not on any watchlist")
        else:
            nm = f"{random.choice(CORP_A)} {random.choice(CORP_B)} {random.choice(CORP_C)}"
            add(nm, "Corporate", pan("C", nm.split()[0]), "H_CLEAN", False, "NONE",
                "Not on any watchlist")

    order = list(range(len(rows)))
    random.shuffle(order)
    rows = [rows[i] for i in order]
    truth = [truth[i] for i in order]

    with open(OUT / f"customers_{tag}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(OUT / f"ground_truth_{tag}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(truth[0])); w.writeheader(); w.writerows(truth)

    fire = sum(t["expected_alert"] for t in truth)
    c = Counter(t["bucket"] for t in truth)
    noisy = sum(1 for t in truth if t["name_noise"] != "none")
    nopan = sum(1 for t in truth if not t["pan_present"] and t["bucket"] != "H_CLEAN")
    print(f"\n=== {tag.upper()}   n={len(rows):,}   prevalence={fire/len(rows):.2%} ===")
    for k in sorted(c):
        tier = next(t["expected_tier"] for t in truth if t["bucket"] == k)
        print(f"  {k:20s} n={c[k]:6,}   expect={tier}")
    print(f"  must-fire={fire}   must-stay-silent={len(rows)-fire}")
    print(f"  seeded names corrupted={noisy}   seeded rows with PAN withheld={nopan}")


build(STRESS_N, "stress")
build(REALISTIC_N, "realistic")
n_wl = (len(debarred_persons) + len(debarred_orgs) + len(pep_current)
        + len(pep_former) + len(rca) + len(uapa_full))
print(f"\nwatchlist_canonical.csv written ({n_wl:,} rows)")
