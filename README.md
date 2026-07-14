# Challenge 3 — Continuous KYC Autonomous Auditor

## Problem Statement

Know-Your-Customer (KYC) onboarding and periodic refreshes are slow, expensive, and reactive. Build an autonomous Continuous KYC agent network that monitors high-risk corporate accounts in near real time, using adverse media, sanctions lists, and risk signals to generate explainable risk assessments and draft Suspicious Activity Reports (SARs).

---

## Datasets

| # | Dataset | Format | Size | License | Credential | Source |
|---|---------|--------|------|---------|-----------|--------|
| 1 | **Synthetic KYC & Transaction Risk Dataset** | CSV / XLSX | ~5–10 MB | Apache 2.0 | Kaggle | [Kaggle](https://www.kaggle.com/datasets/berkanoztas/synthetic-kyc-transaction-risk-dataset) |
| 2 | **Anti Money Laundering Transaction Data (SAML-D)** | CSV | ~500 MB–1 GB | CDLA-Sharing-1.0 | Kaggle | [Kaggle](https://www.kaggle.com/datasets/berkanoztas/synthetic-transaction-monitoring-dataset-aml) |
| 3 | **OpenSanctions** (100+ gov sanction lists) | CSV / JSON | ~500 MB | CC0 / ODbL | ❌ None | [OpenSanctions](https://www.opensanctions.org/datasets/default/) |
| 4 | **OFAC SDN List** (US Treasury) | CSV | ~5 MB | Public Domain | ❌ None | [US Treasury](https://www.treasury.gov/ofac/downloads/sdn.csv) |
| 5 | **PrivacyQA** | JSON | 5 MB | CC-BY 4.0 | ❌ None | [HuggingFace](https://huggingface.co/datasets/allenai/privacy_qa) |
| 6 | **GDPR Full Text** | JSON | <1 MB | Public Domain | ❌ None | [GitHub](https://github.com/nickmvincent/gdpr_text) |
| 7 | **OPP-115 Privacy Policies** | JSON / CSV | ~10 MB | CC-BY 4.0 | ❌ None | [GitHub](https://github.com/citp/privacy-policy-annotated) |

**Total: ~1,020–1,520 MB**

> **Kaggle API required** for datasets 1 and 2. See [SETUP.md](../SETUP.md#step-5--configure-kaggle-api) for setup instructions.

---

## Dataset Details

### 1. Synthetic KYC & Transaction Risk Dataset

**Kaggle:** https://www.kaggle.com/datasets/berkanoztas/synthetic-kyc-transaction-risk-dataset
**License:** Apache 2.0 — free to use, modify, and distribute

Synthetic corporate client profiles enriched with FATF/OFAC risk indicators, PEP flags, sector-based risk, and transaction anomaly signals. Designed specifically for KYC/AML compliance modeling.

**Key Fields:**

| Field | Description |
|-------|-------------|
| `client_id` | Unique client identifier |
| `client_name` | Synthetic company name |
| `client_type` | Corporate / Individual / Financial Institution |
| `country` | Primary jurisdiction |
| `sector` | Industry sector (e.g., Real Estate, Finance, Mining) |
| `sector_risk` | Sector-level risk score (Low/Medium/High) |
| `pep_flag` | Politically Exposed Person indicator (0/1) |
| `sanctions_flag` | Directly sanctioned entity indicator (0/1) |
| `fatf_country_flag` | FATF blacklist/greylist country indicator |

**Use cases:**
- Train entity risk scoring models
- Build PEP/sanctions screening workflows
- Simulate KYC onboarding risk assessment

```python
import pandas as pd

df = pd.read_csv("data/kyc_profiles/synthetic_kyc_dataset.csv")
print(f"Total clients: {len(df):,}")
print(f"PEP clients: {df['pep_flag'].sum():,}")
print(f"Sanctioned: {df['sanctions_flag'].sum():,}")
print(f"FATF flagged: {df['fatf_country_flag'].sum():,}")

# High-risk clients
high_risk = df[(df['pep_flag']==1) | (df['sanctions_flag']==1) | (df['sector_risk']=='High')]
print(f"\nHigh-risk clients: {len(high_risk):,}")
print(high_risk[['client_id','client_name','country','sector','sector_risk','pep_flag','sanctions_flag']].head())
```

---

### 2. Anti Money Laundering Transaction Data (SAML-D)

**Kaggle:** https://www.kaggle.com/datasets/berkanoztas/synthetic-transaction-monitoring-dataset-aml
**License:** CDLA-Sharing-1.0

Large-scale synthetic AML transaction dataset with ~9.5 million transactions and 28 typologies (11 normal, 17 suspicious). Built in collaboration with AML specialists. Mirrors real-world class imbalance (~0.1% suspicious).

**Key Fields:**

| Field | Description |
|-------|-------------|
| `Date` | Transaction date/time |
| `Sender_account` | Sending account identifier |
| `Receiver_account` | Receiving account identifier |
| `Amount` | Transaction amount |
| `Sender_bank_location` | Country of the sending bank |
| `Receiver_bank_location` | Country of the receiving bank |
| `Payment_type` | Wire / SWIFT / ACH / Crypto / etc. |
| `Is_laundering` | Label — 0=Normal, 1=Suspicious |
| `Typology` | One of 28 transaction pattern types |

**Use cases:**
- Train transaction monitoring models (graph-based, time-series, tabular)
- Detect structuring, layering, and integration patterns
- Build risk exposure timeline for SAR drafting

```python
import pandas as pd

# Load a sample (full dataset is ~500MB–1GB)
df = pd.read_csv("data/aml_transactions/aml_transactions.csv", nrows=100_000)
print(f"Shape: {df.shape}")
print(f"Suspicious transactions: {df['Is_laundering'].sum():,} ({df['Is_laundering'].mean()*100:.2f}%)")
print(f"\nTypology distribution:")
print(df[df['Is_laundering']==1]['Typology'].value_counts().head(10))

# Cross-border transactions
cross_border = df[df['Sender_bank_location'] != df['Receiver_bank_location']]
print(f"\nCross-border transactions: {len(cross_border):,}")
```

---

### 3. OpenSanctions — 100+ Government Sanction Lists

**Source:** https://www.opensanctions.org/datasets/default/
**License:** CC0 / ODbL — freely downloadable, no login

Aggregates OFAC, UN, EU, UK, and 100+ other government sanctions lists into a single machine-readable dataset. Used in production by compliance technology vendors.

```bash
# Download (no login needed)
wget https://data.opensanctions.org/datasets/latest/default/targets.simple.csv \
     -O data/sanctions/opensanctions_targets.csv
```

**Key Fields:** `entity_id`, `name`, `aliases`, `dob`, `nationality`, `sanction_program`, `source_list`

---

### 4. OFAC SDN List — US Treasury

**Source:** https://www.treasury.gov/ofac/downloads/sdn.csv
**License:** Public Domain

The most globally enforced sanctions list. All financial institutions must screen against this.

```bash
wget https://www.treasury.gov/ofac/downloads/sdn.csv -O data/sanctions/ofac_sdn.csv
```

---

### 5–7. Regulatory Compliance Datasets

| Dataset | Use in Challenge |
|---------|-----------------|
| **PrivacyQA** | Understanding regulatory Q&A for SAR reasoning |
| **GDPR Full Text** | Regulatory obligation extraction |
| **OPP-115** | Privacy policy annotation and risk categorization |

---

## Data Folder Structure

```
challenge-3-kyc-autonomous-auditor/data/
├── kyc_profiles/
│   └── synthetic_kyc_dataset.csv    ← Client profiles with risk flags
├── aml_transactions/
│   └── aml_transactions.csv         ← 9.5M+ labeled transactions (SAML-D)
├── sanctions/
│   ├── opensanctions_targets.csv    ← 100+ gov sanction lists
│   └── ofac_sdn.csv                 ← OFAC Specially Designated Nationals
├── privacy_qa/                      ← Regulatory Q&A pairs
├── gdpr_text/
│   └── gdpr.json                    ← Full GDPR structured text
└── opp115/                          ← Annotated privacy policies
```

---

## Quick Start

```bash
# 1. Set up Kaggle API (required for datasets 1 & 2)
# See SETUP.md for instructions

# 2. Run the downloader
python download.py

# 3. Install dependencies
pip install pandas numpy scikit-learn
```

---

## Suggested Build Path for Participants

1. **Entity screening** → Cross-reference `kyc_profiles` against `opensanctions_targets` + `ofac_sdn`
2. **Transaction monitoring** → Train an AML classifier on SAML-D with entity risk context
3. **Risk timeline** → Join KYC profile changes with transaction anomaly spikes
4. **SAR drafting** → Use GDPR + PrivacyQA for regulatory language generation
5. **Human review workflow** → Build audit trail with evidence, AI decisions, and reviewer actions

---

*Tech Mahindra CODE Hackathon — Challenge 3 Dataset*
