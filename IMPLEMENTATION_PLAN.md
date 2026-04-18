# Implementation Plan — APJ Abdul Kalam AI Document Intelligence Engine

---

## Overview

This plan covers the complete build of a welfare scheme eligibility matching system for India. The system has three pillars:
1. **Structured scheme data** — 15+ schemes with explicit logical rules
2. **Matching engine** — explainable confidence scores, gap analysis, document checklist
3. **Conversational UI** — Hinglish CLI/web interface

The core design principle: **uncertainty is first-class**. The system must fail clearly, never silently.

---

## Project Structure

```
cbc/
├── question.md
├── prompt.md                        # AI prompt log (mandatory)
├── IMPLEMENTATION_PLAN.md           # This file
├── data/
│   ├── schemes/                     # One JSON file per scheme
│   │   ├── pm_kisan.json
│   │   ├── mgnrega.json
│   │   ├── ayushman_bharat.json
│   │   ├── pmay_gramin.json
│   │   ├── pmay_urban.json
│   │   ├── pm_ujjwala.json
│   │   ├── pm_jan_dhan.json
│   │   ├── sukanya_samriddhi.json
│   │   ├── pm_matru_vandana.json
│   │   ├── national_social_assistance.json
│   │   ├── pm_fasal_bima.json
│   │   ├── pm_shram_yogi_mandhan.json
│   │   ├── atal_pension_yojana.json
│   │   ├── pm_mudra.json
│   │   └── nrega_plus.json
│   ├── ambiguity_map.json           # Cross-scheme contradictions/overlaps
│   └── prerequisites_graph.json     # Scheme dependency graph
├── engine/
│   ├── __init__.py
│   ├── rule_evaluator.py            # Core rule evaluation logic
│   ├── confidence_scorer.py         # Explainable confidence scoring
│   ├── matcher.py                   # Main matching engine
│   ├── gap_analyzer.py              # Gap + almost-eligible analysis
│   ├── document_checklist.py        # Document priority ordering
│   └── prerequisite_sequencer.py   # Application sequence logic
├── interface/
│   ├── cli.py                       # CLI conversational interface
│   ├── hinglish_handler.py          # Hinglish NLP + translation layer
│   ├── question_generator.py        # Intelligent follow-up question logic
│   └── contradiction_detector.py   # Detects inconsistent user answers
├── tests/
│   ├── adversarial_profiles.py      # 10 edge-case user profiles
│   └── test_engine.py               # Unit tests for rule evaluator
├── docs/
│   ├── architecture.md              # System diagram + tech decisions
│   ├── ambiguity_report.md          # Human-readable ambiguity map
│   └── adversarial_results.md       # Edge-case test results
└── requirements.txt
```

---

## Part I — Taming the Data

### Step 1.1: Define the Scheme Schema

Every scheme is stored as a structured JSON with explicit logical rules. No prose summaries.

**Schema for each scheme:**

```json
{
  "scheme_id": "pm_kisan",
  "scheme_name": "PM Kisan Samman Nidhi",
  "ministry": "Ministry of Agriculture & Farmers' Welfare",
  "benefit": "₹6000/year in 3 installments",
  "source_urls": ["https://pmkisan.gov.in"],
  "last_verified": "2026-04-11",
  "confidence_in_rules": 0.85,
  "rules": {
    "operator": "AND",
    "conditions": [
      {
        "field": "occupation",
        "operator": "IN",
        "value": ["farmer", "cultivator"],
        "source": "Section 2(1) of PM-KISAN guidelines",
        "ambiguity": null
      },
      {
        "field": "land_ownership",
        "operator": "EQ",
        "value": true,
        "source": "PM-KISAN operational guidelines 2019",
        "ambiguity": "Leased land not explicitly excluded but 'cultivable landholding' wording implies ownership. See AMBIGUITY-003."
      },
      {
        "operator": "NOT",
        "conditions": [
          {
            "field": "income_tax_payer",
            "operator": "EQ",
            "value": true,
            "source": "Exclusion criterion (i)"
          }
        ]
      }
    ]
  },
  "exclusions": [
    {
      "condition": "institutional_land_holder",
      "description": "Families holding institutional land",
      "source": "Exclusion criterion (ii)"
    },
    {
      "condition": "constitutional_post_holder",
      "description": "Current/former holders of constitutional posts",
      "source": "Exclusion criterion (iii)"
    }
  ],
  "required_documents": [
    {"doc": "Aadhaar", "mandatory": true, "priority": 1},
    {"doc": "Land records / Khasra-Khatauni", "mandatory": true, "priority": 2},
    {"doc": "Bank account (linked to Aadhaar)", "mandatory": true, "priority": 3}
  ],
  "prerequisites": [],
  "application_portal": "pmkisan.gov.in",
  "ambiguity_flags": ["AMBIGUITY-003", "AMBIGUITY-011"]
}
```

### Step 1.2: The 15 Schemes

| # | Scheme | Ministry | Key Eligibility Axis |
|---|--------|----------|----------------------|
| 1 | PM Kisan Samman Nidhi | Agriculture | Farmer + land owner + income |
| 2 | MGNREGA | Rural Development | Rural household, adult willing to do manual work |
| 3 | Ayushman Bharat (PMJAY) | Health | SECC database / deprivation criteria |
| 4 | PMAY-Gramin | Rural Development | Houseless or kutcha house, SECC |
| 5 | PMAY-Urban | Housing & Urban Affairs | EWS/LIG/MIG income slabs, no pucca house |
| 6 | PM Ujjwala Yojana | Petroleum | BPL woman, no existing LPG connection |
| 7 | PM Jan Dhan Yojana | Finance | Any Indian with valid ID, no existing account |
| 8 | Sukanya Samriddhi Yojana | Finance | Girl child under 10, parent/guardian |
| 9 | PM Matru Vandana Yojana | Women & Child Dev | Pregnant woman, first living child |
| 10 | National Social Assistance (NSAP) | Rural Dev | BPL, age/widow/disability criteria |
| 11 | PM Fasal Bima Yojana | Agriculture | Farmer with crop loan or voluntary |
| 12 | PM Shram Yogi Mandhan | Labour | Unorganised worker, 18–40 age, income <15k/mo |
| 13 | Atal Pension Yojana | Finance | 18–40 age, bank account, not covered under statutory pension |
| 14 | PM MUDRA Yojana | Finance | Non-farm micro-enterprise, not defaulter |
| 15 | Pradhan Mantri Garib Kalyan Anna Yojana | Food | NFSA beneficiary (PHH/AAY ration card) |

### Step 1.3: Ambiguity Map

This is a first-class deliverable. Stored in `data/ambiguity_map.json` and rendered human-readable in `docs/ambiguity_report.md`.

**Ambiguity categories:**

1. **Definitional ambiguity** — "small/marginal farmer" defined differently in PM Kisan vs PM Fasal Bima
2. **Overlap / double-dipping** — Can someone get both MGNREGA wages and PM Kisan? (Yes, but MGNREGA work must be separate — often confused by applicants)
3. **Contradiction** — PMAY-G excludes 4-wheeler owners; PMAY-U does not have this criterion
4. **Vague income thresholds** — "economically weaker section" = <₹3L/yr in PMAY-U vs undefined in PMJAY (uses SECC deprivation scoring instead of income)
5. **State variation** — MGNREGA wages vary by state; Ayushman Bharat supplemented by state schemes; PMAY targeting done by state lists

**Known critical ambiguities (pre-identified):**

| ID | Schemes | Description | Risk Level |
|----|---------|-------------|------------|
| AMBIGUITY-001 | PM Kisan, MGNREGA | "Agricultural labourer" excluded from PM Kisan but eligible for MGNREGA — boundary definition unclear for sharecroppers | HIGH |
| AMBIGUITY-002 | PMAY-G, PMAY-U | Rural/Urban boundary: census towns may fall in both jurisdictions | HIGH |
| AMBIGUITY-003 | PM Kisan | "Cultivable landholding in name of family member" — does lease qualify? Guidelines say owned but field practice varies | CRITICAL |
| AMBIGUITY-004 | Ayushman Bharat | SECC 2011 data is 15 years old — people who have since become ineligible or eligible may not be correctly matched | HIGH |
| AMBIGUITY-005 | PM Ujjwala | "BPL household" — BPL list varies by state; PMUY 2.0 relaxed to "any poor household" but definition remains vague | MEDIUM |
| AMBIGUITY-006 | NSAP, PM Kisan | Widow receiving IGNOAPS pension — can she also get PM Kisan if she has agricultural land? Rules do not explicitly address this | MEDIUM |
| AMBIGUITY-007 | Atal Pension, PM Shram Yogi | Both target unorganised workers aged 18–40 with bank accounts. They are not mutually exclusive but most beneficiaries don't know they can hold both | LOW |
| AMBIGUITY-008 | MGNREGA | 100-day guarantee is per household — multi-generational households unclear on whether sub-families count separately | MEDIUM |
| AMBIGUITY-009 | PM MUDRA | "Non-farm enterprise" — a farmer with a roadside shop: farm income disqualifying or supplementary income qualifying? | HIGH |
| AMBIGUITY-010 | PM Jan Dhan | "No frills account" superseded by PMJDY — existing zero-balance account holders may or may not qualify for PMJDY insurance rider | MEDIUM |
| AMBIGUITY-011 | PM Kisan | Income tax payer exclusion — household or individual? A farmer whose son files ITR but farmer does not | HIGH |

---

## Part II — The Matching Engine

### Step 2.1: User Input Schema

```python
UserProfile = {
    "age": int,                        # Required
    "gender": str,                     # male | female | other
    "state": str,                      # ISO state code
    "caste_category": str,             # GEN | OBC | SC | ST
    "annual_income_household": int,    # INR/year
    "land_ownership": bool,
    "land_area_hectares": float | None,
    "land_type": str | None,           # owned | leased | sharecrop | None
    "occupation": str,                 # farmer | labourer | unorganised_worker | salaried | business | unemployed
    "family_size": int,
    "has_bank_account": bool,
    "bank_account_aadhaar_linked": bool | None,
    "ration_card_type": str | None,    # AAY | PHH | None
    "is_income_tax_payer": bool,
    "has_lpg_connection": bool,
    "marital_status": str,             # single | married | widowed | divorced | remarried
    "is_pregnant": bool,
    "number_of_daughters": int,
    "residence_type": str,             # rural | urban | peri-urban
    "house_type": str | None,          # pucca | kutcha | semi-pucca | houseless
    "has_vehicle_4_wheeler": bool,
    "disability": bool,
    "secc_listed": bool | None,        # None = unknown
    "existing_schemes": list[str]      # schemes already enrolled in
}
```

### Step 2.2: Rule Evaluator

`engine/rule_evaluator.py` — evaluates a single rule condition against a user profile.

```python
class RuleEvaluator:
    def evaluate(self, condition: dict, profile: UserProfile) -> EvaluationResult:
        """
        Returns:
          - matched: bool | None  (None = cannot determine, data missing)
          - confidence: float  (0.0–1.0)
          - explanation: str
          - ambiguity_flags: list[str]
        """
```

**Key principle:** When a field is unknown/missing, the evaluator returns `matched=None` (uncertain), not `False`. This propagates uncertainty upward correctly.

### Step 2.3: Confidence Scorer

Each scheme result gets a composite confidence score:

```
confidence = product_of(rule_confidence_scores) * source_confidence * data_freshness_factor
```

- **rule_confidence_scores**: each rule has a confidence derived from clarity of source language (1.0 = unambiguous statute text, 0.6 = vague guideline prose, 0.4 = field-reported practice)
- **source_confidence**: how reliably this scheme's rules were parsed (official gazette = 0.9, ministry website = 0.75, third-party = 0.5)
- **data_freshness_factor**: penalizes schemes based on SECC 2011 or outdated BPL lists (0.7 for Ayushman Bharat due to stale data)

Confidence is **always traceable**: the UI shows which specific rules drove the score up or down.

### Step 2.4: Matcher Output

```python
MatchResult = {
    "scheme_id": str,
    "scheme_name": str,
    "status": "FULLY_ELIGIBLE" | "LIKELY_ELIGIBLE" | "ALMOST_ELIGIBLE" | "INELIGIBLE" | "UNCERTAIN",
    "confidence": float,          # 0.0–1.0
    "confidence_breakdown": [
        {
            "rule": str,
            "result": bool | None,
            "confidence": float,
            "explanation": str,
            "ambiguity_flag": str | None
        }
    ],
    "gap_analysis": [             # populated if ALMOST_ELIGIBLE
        {
            "rule": str,
            "current_value": any,
            "required_value": any,
            "gap_description": str,
            "actionable": bool    # can user actually close this gap?
        }
    ],
    "document_checklist": [
        {"document": str, "mandatory": bool, "priority": int, "obtainable_from": str}
    ],
    "application_url": str,
    "warnings": [str]             # ambiguity flags surfaced as plain-language warnings
}
```

### Step 2.5: Prerequisite Sequencer

Some schemes require others first:
- PM Kisan → requires bank account (PMJDY if unbanked)
- PMAY → requires Aadhaar (which requires PMJDY or other ID)
- Ayushman Bharat → requires SECC listing or Ration Card

A directed graph in `data/prerequisites_graph.json` is topologically sorted to produce the **correct application sequence**.

### Step 2.6: Ten Adversarial Edge Cases

| # | Profile | Expected Challenge | Pass/Fail |
|---|---------|-------------------|-----------|
| 1 | Widow (60F) who recently remarried | NSAP widow pension — does remarriage disqualify? | TBD |
| 2 | Farmer who leases (not owns) land | PM Kisan ownership ambiguity AMBIGUITY-003 | TBD |
| 3 | Person with Aadhaar but no bank account | PM Kisan, PMJDY sequencing | TBD |
| 4 | Urban sharecropper in a census town | PMAY-G vs PMAY-U jurisdiction ambiguity AMBIGUITY-002 | TBD |
| 5 | 19-year-old pregnant girl, unmarried | PM Matru Vandana — "first living child" + marital assumption | TBD |
| 6 | Farmer with ITR-filing son in same household | PM Kisan income tax payer exclusion AMBIGUITY-011 | TBD |
| 7 | BPL woman with LPG connection from previous home | PM Ujjwala — connection ownership ambiguity | TBD |
| 8 | Unorganised worker, age 41 | PM Shram Yogi Mandhan — just outside age bracket | TBD |
| 9 | Tribal farmer with no land records (oral rights) | PM Kisan — forest rights, traditional land | TBD |
| 10 | Person enrolled in ESIC — claims to be unorganised worker | Atal Pension / PM Shram Yogi exclusion for organised sector | TBD |

**The engine must:**
- For Case 1: flag uncertainty, not auto-disqualify
- For Case 2: surface AMBIGUITY-003, give 0.5 confidence, explain the ambiguity
- For Case 3: output PMJDY as prerequisite step 1 before PM Kisan
- For ambiguous cases: always say "unclear — visit nearest Jan Seva Kendra for verification" rather than a confident wrong answer

---

## Part III — Conversational Interface

### Step 3.1: CLI Flow

```
$ python interface/cli.py

> Namaskar! Main aapki sarkari yojanaon mein help kar sakta hoon.
> Aap apni situation bata sakte hain — Hindi, English, ya Hinglish mein.

User: main ek kisan hoon, UP mein rehta hoon, 2 acre zameen hai mere naam pe

System: [extracts: occupation=farmer, state=UP, land_ownership=true, land_area=0.8ha]
> Theek hai! Aapki family ki annual income roughly kitni hai?

User: pata nahi exactly, shayad 80-90 hazaar

System: [extracts: annual_income=85000, confidence=RANGE]
> Aur aapka bank account hai? Aadhaar se linked hai?

[... continues until enough data to run matcher ...]

System: [Runs matcher, generates results]
> Aap PM Kisan ke liye eligible hain (92% confidence).
> Ayushman Bharat ke liye bhi shayad eligible hain — ek aur cheez confirm karni hogi.
```

### Step 3.2: Hinglish Handler

`interface/hinglish_handler.py`:

- Uses Claude API to extract structured fields from free-form Hinglish text
- Prompt includes: "Extract the following fields from this text. If a field is not mentioned, return null. Do not guess."
- Explicitly instructs: return `null` over making an assumption
- Validates extracted fields for internal consistency before passing to matcher

### Step 3.3: Contradiction Detector

`interface/contradiction_detector.py`:

Detects when user gives inconsistent answers:
- Claims to be a farmer AND says they have no land AND land_ownership=false → ask clarifying question
- Says income > ₹5L/year AND claims BPL ration card → flag discrepancy, ask which is current
- Says age = 35 AND says they have been farming for 40 years → flag

When contradiction detected, the system does NOT pick one answer and move on. It says:
> "Ek baat thodi confusing lag rahi hai — aapne bola aapki income 5 lakh se zyada hai, lekin aapka BPL card bhi hai. Kaunsa zyada accurate hai abhi ke liye?"

### Step 3.4: Incomplete Answer Handling

If user doesn't know an answer:
- Engine uses `null` for that field
- Matcher runs with uncertainty
- Output says: "Agar aapka [field] X se kam hai, toh aap [scheme] ke liye eligible honge"

---

## Architecture Document

### System Diagram

```
User Input (Hinglish CLI / Web)
        │
        ▼
┌─────────────────────────┐
│   Hinglish Handler       │  ← Claude API (structured extraction)
│   + Contradiction Detect │
└──────────┬──────────────┘
           │ UserProfile (with null fields for unknowns)
           ▼
┌─────────────────────────┐
│   Matching Engine        │
│  ┌────────────────────┐  │
│  │  Rule Evaluator    │  │  ← data/schemes/*.json
│  │  (per-rule result, │  │
│  │   confidence,      │  │
│  │   ambiguity flags) │  │
│  └────────────────────┘  │
│  ┌────────────────────┐  │
│  │  Confidence Scorer │  │
│  └────────────────────┘  │
│  ┌────────────────────┐  │
│  │  Gap Analyzer      │  │
│  └────────────────────┘  │
│  ┌────────────────────┐  │
│  │  Prerequisite      │  │  ← data/prerequisites_graph.json
│  │  Sequencer         │  │
│  └────────────────────┘  │
└──────────┬──────────────┘
           │ MatchResult[]
           ▼
┌─────────────────────────┐
│   Output Renderer        │
│  - Eligible schemes      │
│  - Gap analysis          │
│  - Document checklist    │
│  - Application sequence  │
│  - Ambiguity warnings    │
└─────────────────────────┘
```

### Three Key Technical Decisions

**Decision 1: Rule representation as JSON logic trees, not code**
- **Chosen:** JSON with `operator`, `field`, `value` nodes (as shown above)
- **Rejected alternative A:** Python functions per scheme — fast but untestable, un-auditable, impossible for non-engineers to verify
- **Rejected alternative B:** Natural language rules stored as text + LLM evaluation at runtime — hallucinates, non-deterministic, cannot be audited
- **Why JSON:** Rules are inspectable, version-controlled, testable, and can be manually verified against source documents. An LLM can help write them but a human must verify each one.

**Decision 2: Uncertainty propagation with three-valued logic (True / False / Unknown)**
- **Chosen:** Evaluator returns `True | False | None` per rule. `None` propagates as uncertain through AND/OR/NOT trees
- **Rejected alternative:** Default missing fields to `False` (disqualifying) — causes massive false negatives, harms real users
- **Rejected alternative:** Default missing fields to `True` — causes false positives, gives wrong confident answers to real people
- **Why three-valued:** Correctly models what we don't know. The system says "we need more info" rather than fabricating an answer.

**Decision 3: Human-curated rules with AI-assisted drafting**
- **Chosen:** AI drafts rules from scheme PDFs, human verifies each rule against source, source citation stored in every rule
- **Rejected alternative:** Fully automated AI parsing — hallucination risk is real (AI confidently invents income thresholds that don't exist)
- **Rejected alternative:** Fully manual without AI — too slow for 15+ schemes
- **Why hybrid:** AI accelerates the drafting step (the boring extraction from PDF prose) but every rule must have a human-readable source citation that can be spot-checked. This is the anti-hallucination architecture.

### Two Most Critical Production-Readiness Gaps

**Gap 1: SECC 2011 data staleness for Ayushman Bharat**
The SECC used for PMJAY eligibility is from 2011 census data. 15 years of demographic change means a significant fraction of the population has moved in/out of eligibility. The system cannot know who is actually listed in SECC without querying the NHA backend. In production, the system should: (a) integrate with NHA's beneficiary API, or (b) clearly tell users "check your SECC status at nha.gov.in before applying" rather than giving a confident match.

**Gap 2: State-level scheme variations**
Every central scheme has state-specific addendums — state top-ups to PMJAY, different MGNREGA wage rates, state-specific BPL lists for Ujjwala. V1 treats all states identically. In production, a state rules layer must sit on top of central rules, with state-specific JSON files and a state resolver that merges central + state rules before evaluation.

---

## Implementation Sequence

### Phase 1 — Data (Days 1–2)
- [ ] Define and finalize the JSON schema for scheme rules
- [ ] Draft rules for all 15 schemes using AI assistance (log every prompt in prompt.md)
- [ ] Human-verify each rule against official source URLs
- [ ] Build ambiguity_map.json with all identified contradictions/overlaps
- [ ] Create prerequisites_graph.json

### Phase 2 — Engine (Days 2–3)
- [ ] Implement `RuleEvaluator` with three-valued logic
- [ ] Implement `ConfidenceScorer`
- [ ] Implement `Matcher` (aggregates evaluations across all schemes)
- [ ] Implement `GapAnalyzer`
- [ ] Implement `DocumentChecklist` generator
- [ ] Implement `PrerequisiteSequencer` (topological sort of prerequisites_graph)
- [ ] Write unit tests for all 10 adversarial profiles

### Phase 3 — Interface (Days 3–4)
- [ ] Implement `HinglishHandler` using Claude API
- [ ] Implement `ContradictionDetector`
- [ ] Implement `QuestionGenerator` (intelligent follow-up questions based on null fields)
- [ ] Build CLI loop in `cli.py`
- [ ] Test with 5+ Hinglish conversational inputs

### Phase 4 — Documentation (Day 4–5)
- [ ] Write `docs/architecture.md` with final system diagram
- [ ] Write `docs/ambiguity_report.md` human-readable ambiguity analysis
- [ ] Write `docs/adversarial_results.md` with full test results
- [ ] Finalize `prompt.md` with complete prompt log
- [ ] Submission checklist review

---

## Anti-Hallucination Protocol

Every scheme rule must pass this checklist before being committed:

- [ ] Source URL or document name cited in the rule JSON
- [ ] Rule phrasing matches source language (not paraphrased interpretation)
- [ ] Ambiguity flags added where source language is vague
- [ ] Confidence score on rule reflects clarity of source (not AI's confidence)
- [ ] At least one adversarial test case touches this rule

This protocol is the primary defence against AI hallucination corrupting the eligibility data.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.11 | Readable, fast to iterate |
| Rule evaluation | Pure Python | No ML, fully deterministic, auditable |
| Hinglish NLP | Claude API | Best multilingual extraction quality |
| CLI | Python `rich` library | Clean terminal output |
| Data format | JSON | Human-readable, versionable, diffs well |
| Tests | pytest | Standard |
| Dependencies | anthropic, rich, networkx (for DAG), pytest | Minimal |

---

## Deliverables Checklist

- [ ] Structured eligibility rules for 15+ central government schemes
- [ ] Ambiguity map documenting contradictions and overlaps across schemes
- [ ] Working matching engine with explainable confidence scores
- [ ] Ten adversarial edge-case profiles with documented results
- [ ] Conversational interface supporting Hinglish natural language input
- [ ] Architecture document with system diagram and technical decisions
- [ ] Complete prompt log in prompt.md
