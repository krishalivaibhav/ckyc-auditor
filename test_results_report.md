# Adverse Media Module - Test Results Report

## 1. False Positive Suppression (News that should be ignored)

These articles contain 'bad' keywords but are contextually positive or benign. The AI should suppress them.

### Input: News about Infosys
**Headline:** Infosys launches new initiative to fight against financial fraud
**Description:** Infosys announced a new AI-powered system to help banks detect and prevent fraud.
**Action Expected:** Suppress (Ignore)

✅ **Output Received:** SUCCESS (Article Suppressed)

> *The AI correctly determined this is not a genuinely adverse event and suppressed it.*

---

### Input: News about Adani Group
**Headline:** Adani Group wins legal case against fraud allegations
**Description:** The Supreme Court cleared Adani Group of all fraud charges, calling the claims baseless.
**Action Expected:** Suppress (Ignore)

✅ **Output Received:** SUCCESS (Article Suppressed)

> *The AI correctly determined this is not a genuinely adverse event and suppressed it.*

---

### Input: News about Infosys
**Headline:** Infosys partners with RBI to strengthen cybersecurity measures
**Description:** Infosys will help the Reserve Bank of India build defences against money laundering detection.
**Action Expected:** Suppress (Ignore)

✅ **Output Received:** SUCCESS (Article Suppressed)

> *The AI correctly determined this is not a genuinely adverse event and suppressed it.*

---

## 2. True Positive Detection (News that should be flagged)

These articles represent genuine compliance risks. The AI should flag them and provide a severity and reasoning.

### Input: News about Nirav Modi
**Headline:** Nirav Modi found guilty of defrauding PNB of 13000 crores
**Description:** UK court convicts Nirav Modi in the Punjab National Bank fraud case involving 13000 crore rupees in fraudulent letters of undertaking.
**Action Expected:** Flag as Adverse

✅ **Output Received:** SUCCESS (Article Flagged)

- **Severity:** CRITICAL
- **Confidence:** 100%
- **AI Reasoning:** The article reports a confirmed criminal conviction of Nirav Modi by a UK court for defrauding Punjab National Bank, which is a severe adverse media finding indicating a high level of regulatory risk.

---

### Input: News about Adani Group
**Headline:** SEBI bars Adani Group directors for market manipulation
**Description:** Securities and Exchange Board of India has issued orders barring 4 Adani Group directors for alleged stock price manipulation and insider trading.
**Action Expected:** Flag as Adverse

✅ **Output Received:** SUCCESS (Article Flagged)

- **Severity:** HIGH
- **Confidence:** 90%
- **AI Reasoning:** The article reports that SEBI has barred Adani Group directors for alleged market manipulation and insider trading, which is a regulatory action indicating serious compliance issues, and the source is a reputable business publication.

---

### Input: News about Adani Group
**Headline:** CBI arrests senior Adani executive in bribery case
**Description:** The Central Bureau of Investigation arrested a top executive of Adani Group in connection with a bribery scandal involving government contracts.
**Action Expected:** Flag as Adverse

✅ **Output Received:** SUCCESS (Article Flagged)

- **Severity:** HIGH
- **Confidence:** 90%
- **AI Reasoning:** The article reports the arrest of a senior Adani executive by the CBI in connection with a bribery scandal, indicating a serious regulatory and compliance issue. The involvement of a top executive and the CBI's action suggests a significant adverse event.

---
