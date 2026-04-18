# Architecture Document — APJ Abdul Kalam AI Document Intelligence Engine

**Project:** CBC — Citizen Benefit Checker  
**Version:** 1.0.0 (Hackathon Submission)  
**Date:** 2026-04-17

---

## System Overview

The CBC engine is an AI-assisted welfare eligibility checker for Indian citizens. It ingests a citizen's profile, evaluates eligibility across 18 central government schemes, surfaces ambiguities explicitly, and presents results in conversational Hinglish.

**Design philosophy:** *The system must fail clearly, never silently.* Every uncertain outcome is surfaced as uncertainty. No guessing. No silent resolution of contradictions.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User (CLI)                               │
│                   (Hindi / English / Hinglish)                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ free-form text
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  interface/cli.py                                │
│                  Conversation Loop                               │
│  ┌──────────────────┐   ┌────────────────────────────────────┐  │
│  │ SessionLog       │   │  Contradiction Detector             │  │
│  │ - profile dict   │   │  contradiction_detector.py          │  │
│  │ - conv history   │◄──│  5 rules, Hinglish clarifications   │  │
│  │ - match history  │   └────────────────────────────────────┘  │
│  └────────┬─────────┘                                           │
│           │                                                     │
└───────────┼─────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                 interface/hinglish_handler.py                    │
│                  Claude Haiku NLP Extractor                      │
│  Input: free-form Hinglish text                                 │
│  Output: structured profile fields (only what was mentioned)    │
│  Anti-hallucination: 17-rule system prompt                      │
│  Fallback: regex demo extractor (no API key required)           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ profile dict (partial)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                interface/question_generator.py                   │
│                  Intelligent Question Prioritiser                │
│  - 22 questions across 6 priority tiers                        │
│  - Skips already-answered fields                                │
│  - Skips questions inapplicable given known profile             │
│  - Boosts impact score for fields that unlock uncertain schemes │
└──────────────────────────┬──────────────────────────────────────┘
                           │ complete profile
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     engine/matcher.py                            │
│                   Core Matching Engine                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              engine/rule_evaluator.py                    │   │
│  │           Three-Valued Logic Evaluator                   │   │
│  │                                                         │   │
│  │  evaluate_condition(condition, profile)                  │   │
│  │    → EvaluationResult(matched: True|False|None,         │   │
│  │                       confidence: 0.0–1.0,              │   │
│  │                       flags: list[str])                  │   │
│  │                                                         │   │
│  │  Operators: AND / OR / NOT / EQ / NEQ / IN / NOT_IN /  │   │
│  │             GT / GTE / LT / LTE / BETWEEN / IS_NULL /  │   │
│  │             IS_NOT_NULL                                  │   │
│  │                                                         │   │
│  │  Special behaviours:                                    │   │
│  │  - IS_NULL intercept: absent field → IS_NULL=True       │   │
│  │  - Peri-urban: compared to rural/urban → None           │   │
│  │  - Missing field: → None (never False)                  │   │
│  │  - NOT(None) → None (uncertainty propagates)            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│  Status classifier:                                             │
│  ├─ result=True, confidence ≥ 0.75 → FULLY_ELIGIBLE            │
│  ├─ result=True, confidence ≥ 0.45 → LIKELY_ELIGIBLE           │
│  ├─ result=True, confidence < 0.45 → LIKELY_ELIGIBLE (LOW)     │
│  ├─ result=None                    → UNCERTAIN                  │
│  ├─ result=False + NOT fired       → INELIGIBLE                 │
│  ├─ result=False + hard field fail → INELIGIBLE                 │
│  ├─ result=False + 1 failure + ambiguity → UNCERTAIN            │
│  ├─ result=False + 1 failure       → ALMOST_ELIGIBLE           │
│  └─ result=False + 2+ failures     → INELIGIBLE                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────────────┐
│ engine/          │ │ engine/      │ │ engine/                   │
│ gap_analyzer.py  │ │ document_    │ │ prerequisite_sequencer.py │
│                  │ │ checklist.py │ │                           │
│ For each scheme: │ │              │ │ Kahn's topological sort   │
│ - What fields   │ │ Deduplicates │ │ of 18-node prerequisite   │
│   are missing   │ │ documents    │ │ DAG.                      │
│ - Is the gap    │ │ across all   │ │                           │
│   actionable    │ │ eligible     │ │ PMJDY always Step 1 for   │
│ - What action   │ │ schemes.     │ │ unbanked users.           │
│   to take       │ │              │ │                           │
└──────────────────┘ └──────────────┘ └──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Hinglish Output Renderer                      │
│                      (in interface/cli.py)                       │
│                                                                 │
│  Section 1: Results (FULLY_ELIGIBLE → INELIGIBLE)               │
│  Section 2: Document checklist (consolidated, deduplicated)     │
│  Section 3: Application sequence ("do these first")             │
│  Section 4: Ambiguity notices ("verify at BDO/CSC")             │
│  Section 5: Disclaimer                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Layer

### Eligibility Rules: JSON Logic Trees

Every scheme is stored as a JSON file in `data/schemes/`. Eligibility rules are expressed as operator trees:

```json
{
  "scheme_id": "pm_kisan",
  "eligibility_rules": {
    "operator": "AND",
    "conditions": [
      {
        "rule_id": "pmk_r1a",
        "field": "occupation",
        "operator": "IN",
        "value": ["farmer", "cultivator", "agricultural_landowner"],
        "confidence": 0.95,
        "source": "PM-KISAN Operational Guidelines 2019, Section 4.1"
      },
      {
        "rule_id": "pmk_r1b",
        "field": "land_ownership",
        "operator": "EQ",
        "value": true,
        "confidence": 0.80,
        "ambiguity_flag": "AMBIGUITY-003",
        "source": "PM-KISAN Guidelines, Section 3 — excludes tenants by default"
      },
      {
        "operator": "NOT",
        "conditions": [{
          "operator": "OR",
          "conditions": [
            {"rule_id": "pmk_excl_1", "field": "is_income_tax_payer", "operator": "EQ", "value": true},
            {"rule_id": "pmk_excl_2", "field": "is_central_state_govt_employee", "operator": "EQ", "value": true}
          ]
        }]
      }
    ]
  }
}
```

**Key design decisions in the JSON schema:**
- `confidence` is per-rule, not per-scheme — rules with vague source language carry lower confidence
- `ambiguity_flag` links to the ambiguity map for human-readable explanation
- `source` is traceable to the specific government document and section
- Rules are human-verified: AI drafts, human checks against PDFs

### Schemes Covered (18 total)

| ID | Scheme | Category |
|----|--------|----------|
| pm_kisan | PM Kisan Samman Nidhi | Agriculture |
| mgnrega | Mahatma Gandhi NREGA | Employment |
| ayushman_bharat | PM-JAY / Ayushman Bharat | Health |
| pmay_gramin | PMAY — Gramin | Housing |
| pmay_urban | PMAY — Urban | Housing |
| pm_ujjwala | PM Ujjwala Yojana | Energy |
| pm_jan_dhan | Pradhan Mantri Jan Dhan | Banking |
| sukanya_samriddhi | Sukanya Samriddhi Yojana | Child Welfare |
| pm_matru_vandana | PMMVY | Maternal Health |
| nsap | National Social Assistance Programme | Social Security |
| pm_fasal_bima | PMFBY | Crop Insurance |
| pm_shram_yogi_mandhan | PM-SYM | Pension |
| atal_pension_yojana | Atal Pension Yojana | Pension |
| pm_mudra | PM MUDRA Yojana | Credit |
| pmgkay | PMGKAY / NFSA | Food Security |
| pm_kisan_credit_card | Kisan Credit Card | Credit |
| pm_jeevan_jyoti_bima | PMJJBY | Insurance |
| pm_suraksha_bima | PMSBY | Insurance |

---

## Three Technical Decisions

### Decision 1: Three-Valued Logic over Binary Logic

**Rejected alternative:** Binary (true/false) evaluation where missing fields default to false.

**Chosen approach:** Kleene three-valued logic — True / False / **None** (uncertain/unknown). None propagates through AND/OR/NOT using standard Kleene semantics:

```
AND(True, None)  = None    # Could be True or False — don't know
AND(False, None) = False   # Short-circuit — already disqualified
OR(False, None)  = None    # Could be True — don't know
OR(True, None)   = True    # Short-circuit — already qualified
NOT(None)        = None    # Unknown stays unknown
```

**Why:** A citizen who hasn't told us their income should NOT be told they are ineligible for PM Kisan. Binary false-default would produce that outcome. None correctly propagates uncertainty and forces the system to say "we need more information" rather than "you are ineligible."

**Trade-off:** Some users see more UNCERTAIN results than they'd like. This is intentional — an UNCERTAIN result with "go to your BDO" is better than a confident wrong answer.

---

### Decision 2: Source Citations per Rule with Human Verification Loop

**Rejected alternative:** LLM-only rule generation without source tracking.

**Chosen approach:** Every rule has a `source` field citing the specific government document and section. Rules are drafted by Claude (from government PDF text) and then manually verified by a human against the source. Four hallucinations were caught and discarded in this process.

**Hallucinations caught:**
1. PM Kisan income ceiling (₹2L/year) — does not exist in guidelines
2. PM Kisan land area restriction (≤ 2 hectares) — removed in 2019 amendment
3. MGNREGA BPL requirement — MGNREGA has no income means test
4. PM-JAY income threshold (< ₹1L/year) — PM-JAY uses SECC deprivation criteria, not income

**Why:** Without source tracking, LLM-generated rules cannot be audited or corrected. In a welfare system, a hallucinated rule could deny benefits to legitimate claimants or falsely indicate eligibility to ineligible users.

**Trade-off:** Requires human review for each rule. 18 schemes × avg 8 rules = ~144 rules reviewed. This is a one-time cost that prevents ongoing systematic errors.

---

### Decision 3: Ambiguity as First-Class Output

**Rejected alternative:** Pick the most likely interpretation of ambiguous rules and apply it silently.

**Chosen approach:** 17 documented ambiguities in `data/ambiguity_map.json`. Each ambiguity has an `engine_behaviour` instruction. When an ambiguous condition affects a result, the ambiguity flag is surfaced in the output with an actionable recommendation (e.g., "Verify at Block Development Office").

**Most critical ambiguities:**

| ID | Description | Severity | Resolution |
|----|-------------|----------|------------|
| AMBIGUITY-003 | PM Kisan: leased/sharecrop land not clearly excluded or included in all states | CRITICAL | Direct to agriculture office |
| AMBIGUITY-004 | Ayushman Bharat: SECC 2011 data is 15 years old — may not reflect current status | HIGH | Direct to pmjay.gov.in |
| AMBIGUITY-006 | NSAP: remarried widow's pension eligibility not explicit in guidelines | MEDIUM | Direct to BDO |
| AMBIGUITY-011 | PM Kisan: "income tax filer" = household member or individual? | HIGH | Direct to agriculture office |

**Why:** Silent resolution of ambiguity means the system makes a legal determination that it is not qualified to make. "Eligible" or "Ineligible" stated confidently for an ambiguous rule could cause real harm. UNCERTAIN + "verify at BDO" respects the citizen's right to correct determination.

---

## Two Production Gaps

### Gap 1: SECC 2011 Data Integration

**The gap:** Ayushman Bharat (PM-JAY) eligibility is officially determined by SECC 2011 deprivation criteria — not by income, ration card, or self-declaration. The engine cannot access SECC 2011 records.

**Current behaviour:** If a user has a PHH ration card, they are likely enrolled via NFSA expansion — marked LIKELY_ELIGIBLE (confidence 0.48) with AMBIGUITY-004 flagged.

**Production solution:** Integrate with the PMJAY beneficiary API at `pmjay.gov.in`. The API allows lookup by Aadhaar number. In V1 this requires: (1) PMJAY API access credentials, (2) user consent to Aadhaar-based lookup, (3) handling the case where SECC data is incorrect or outdated.

**Risk if unaddressed:** ~30% of Ayushman Bharat results are UNCERTAIN or LIKELY rather than confirmed. Users who are SECC-listed but don't know it cannot be told definitively that they are eligible.

---

### Gap 2: State-Specific Eligibility Variation

**The gap:** Many central schemes have state-level additions, exclusions, and top-up schemes that modify eligibility at the state level. Examples:

- MGNREGA wage rates vary by state (₹202–₹357/day as of 2024)
- Some states have expanded PMAY-G quotas beyond central limits
- States like Telangana and Andhra Pradesh have their own farmer income support (Rythu Bandhu, YSR Rythu Bharosa) that complement or intersect with PM Kisan
- Urban local body jurisdiction boundaries differ from census town classifications for PMAY-U

**Current behaviour:** Engine applies central scheme rules only. State code (e.g., "UP", "MH") is collected but not used for scheme-specific state variations.

**Production solution:** Extend the JSON schema to support `state_overrides` per scheme. For each state, store the delta from central rules (additions, exclusions, modified thresholds). This requires:
- Sourcing state-level scheme guidelines (18 schemes × 28 states/UTs = up to 504 override files)
- Ongoing maintenance as state governments modify rules

**Risk if unaddressed:** Users in states with expanded eligibility (e.g., Telangana farmers for PM Kisan equivalents) may be told UNCERTAIN when they are ELIGIBLE under state rules.

---

## File Structure

```
cbc/
├── data/
│   ├── schemes/                  # 18 JSON scheme rule files
│   ├── ambiguity_map.json        # 17 documented ambiguities
│   └── prerequisites_graph.json  # DAG for application sequencing
├── engine/
│   ├── rule_evaluator.py         # Three-valued logic evaluator
│   ├── matcher.py                # Status classifier + scheme runner
│   ├── gap_analyzer.py           # Gap identification for ALMOST_ELIGIBLE
│   ├── document_checklist.py     # Unified document requirement builder
│   └── prerequisite_sequencer.py # Topological sort for application order
├── interface/
│   ├── hinglish_handler.py       # Claude Haiku NLP field extractor
│   ├── question_generator.py     # Intelligent follow-up question prioritiser
│   ├── contradiction_detector.py # Profile contradiction checker
│   └── cli.py                    # Main conversational loop
├── tests/
│   ├── adversarial_profiles.py   # 10 edge-case test profiles
│   └── test_engine.py            # Test runner with 4 check categories
├── docs/
│   ├── architecture.md           # This file
│   ├── ambiguity_report.md       # Human-readable ambiguity analysis
│   └── adversarial_results.md    # Full test results documentation
├── prompt.md                     # AI prompt log (17 entries)
├── question.md                   # Challenge brief
├── IMPLEMENTATION_PLAN.md        # Architecture blueprint
└── requirements.txt              # Python dependencies
```

---

## Running the System

```bash
# Install dependencies
pip install -r requirements.txt

# Run adversarial test suite
python3 -m tests.test_engine

# Run conversational CLI (with API key)
ANTHROPIC_API_KEY=sk-... python3 -m interface.cli

# Run in demo mode (no API key, regex extractor)
python3 -m interface.cli --demo
```
