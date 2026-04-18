# Yojna.ai — India's Welfare Scheme Eligibility Engine

> *Aapki Yojana, Aapka Haq.* — Your Scheme, Your Right.

Built for the **APJ Abdul Kalam AI Hackathon**. Yojna.ai tells Indian citizens which government welfare schemes they qualify for, what documents to prepare, and in what order to apply — in plain Hinglish.

---

## The Problem

Millions of Indians qualify for government welfare schemes but never claim them. Eligibility criteria are buried across hundreds of bureaucratic PDFs, written in vague language that preserves administrative discretion. Most people don't know what they're entitled to.

Yojna.ai changes that.

---

## What It Does

You describe your situation in Hindi, English, or Hinglish. The system:

1. **Extracts** your profile fields (age, occupation, income, land, caste, etc.) from natural language
2. **Evaluates** your eligibility across 18 central government schemes using explicit logical rules
3. **Surfaces ambiguities** — when government guidelines are genuinely unclear, it says so rather than guessing
4. **Asks follow-up questions** only for the fields that are still missing, one at a time
5. **Outputs** eligible schemes, a unified document checklist, and a step-by-step application sequence

---

## Key Design Principle

> **The system must fail clearly, never silently.**

When rules are ambiguous, the engine returns `UNCERTAIN` and directs the user to the right government office. It never fabricates a confident answer. Every confidence score is traceable to a specific rule evaluation with a source citation.

---

## Schemes Covered (18)

| Scheme | Category |
|--------|----------|
| PM Kisan Samman Nidhi | Agriculture |
| Mahatma Gandhi NREGA | Employment |
| Ayushman Bharat (PM-JAY) | Health |
| PMAY — Gramin | Housing |
| PMAY — Urban | Housing |
| PM Ujjwala Yojana | Energy |
| PM Jan Dhan Yojana | Banking |
| Sukanya Samriddhi Yojana | Child Welfare |
| PM Matru Vandana Yojana | Maternal Health |
| National Social Assistance Programme | Social Security |
| PM Fasal Bima Yojana | Crop Insurance |
| PM Shram Yogi Mandhan | Pension |
| Atal Pension Yojana | Pension |
| PM MUDRA Yojana | Credit |
| PMGKAY / NFSA | Food Security |
| Kisan Credit Card | Farm Credit |
| PM Jeevan Jyoti Bima | Insurance |
| PM Suraksha Bima | Insurance |

---

## Setup

### Requirements

- Python 3.10+
- Google Gemini API key (free at [aistudio.google.com](https://aistudio.google.com))

### Install

```bash
git clone <repo>
cd cbc
pip install -r requirements.txt
```

### Run

```bash
# With Gemini API (full Hinglish NLP extraction)
GEMINI_API_KEY=your-key python3 -m interface.cli

# Demo mode (no API key — regex-based extraction)
python3 -m interface.cli --demo
```

---

## Example Conversation

```
◈  Namaskar! Main Yojna.ai hoon.

   Apni situation ek baar mein bata dijiye:
   umar, kaam, kahan rehte hain, income, zameen, bank account, ration card

╭─ Apni baat kaho
╰❯ main 38 saal ka kisan hoon UP mein, gaon mein rehta hoon,
   2 acre zameen hai mere naam pe, BPL card hai, bank account hai

✓  Samjha — umar: 38, kaam: farmer, state: UP, residence: rural

[████████████░░░░░░░░] 62%  Profile 62% complete — thoda aur batao

──────── Ek sawaal ────────
◈  Aapke poore parivaar ki saal bhar ki kamai kitni hai?
╰❯ 90 hazaar

✓  Samjha — income: 90000

... (2-3 more questions)

══════════════════════════════
  AAPKE LIYE YOJANAEN
══════════════════════════════

✦  PM Kisan Samman Nidhi      [████████████] 80%
✦  PMGKAY / NFSA              [██████████░░] 86%
✦  PM Suraksha Bima           [████████████] 94%
◉  PMJJBY                     [██████████░░] 82%
```

---

## Architecture

### Three-Valued Logic

Rules are evaluated as **True / False / None** (uncertain). `None` propagates through AND/OR/NOT — a missing field never collapses to a confident wrong answer.

### JSON Logic Trees

Each scheme is stored as a structured JSON file with operator trees (`AND`, `OR`, `NOT`, `EQ`, `IN`, `BETWEEN`, etc.), source citations, confidence scores, and ambiguity flags per rule.

```json
{
  "rule_id": "pmk_r1b",
  "field": "land_ownership",
  "operator": "EQ",
  "value": true,
  "confidence": 0.80,
  "ambiguity_flag": "AMBIGUITY-003",
  "source": "PM-KISAN Guidelines, Section 3"
}
```

### Ambiguity Map

17 documented ambiguities in `data/ambiguity_map.json` — every place where government language is genuinely unclear. The engine surfaces these explicitly instead of guessing.

### Anti-Hallucination Protocol

AI-drafted rules are verified against source government PDFs before being committed. 4 hallucinations were caught during development:

- PM Kisan income ceiling (₹2L/year) — **does not exist**
- PM Kisan land area limit (≤ 2 hectares) — **removed in 2019**
- MGNREGA BPL requirement — **MGNREGA has no means test**
- PM-JAY income threshold — **PM-JAY uses SECC deprivation, not income**

---

## Project Structure

```
cbc/
├── data/
│   ├── schemes/          # 18 JSON scheme rule files
│   ├── ambiguity_map.json
│   └── prerequisites_graph.json
├── engine/
│   ├── rule_evaluator.py     # Three-valued logic engine
│   ├── matcher.py            # Status classifier
│   ├── gap_analyzer.py       # Gap identification
│   ├── document_checklist.py # Unified document builder
│   └── prerequisite_sequencer.py  # Topological sort
├── interface/
│   ├── cli.py                # Main conversation loop
│   ├── hinglish_handler.py   # Gemini NLP extractor
│   ├── question_generator.py # Intelligent follow-up questions
│   └── contradiction_detector.py  # Profile consistency checks
├── tests/
│   ├── adversarial_profiles.py   # 10 edge-case profiles
│   └── test_engine.py            # Test runner
├── docs/
│   ├── architecture.md
│   ├── ambiguity_report.md
│   └── adversarial_results.md
└── prompt.md             # Mandatory AI prompt log (17 entries)
```

---

## Test Suite

```bash
python3 -m tests.test_engine
```

**10/10 adversarial cases passing.** Tests cover:

| Case | Tests |
|------|-------|
| Remarried widow | NSAP pension → UNCERTAIN, not INELIGIBLE |
| Tenant farmer | PM Kisan → UNCERTAIN, not INELIGIBLE |
| Unbanked farmer | Jan Dhan shown first in sequence |
| Peri-urban resident | All rural/urban schemes → UNCERTAIN |
| Unmarried pregnant | PMMVY eligible — no hallucinated marital rule |
| Farmer with salaried son | ITR ambiguity flagged correctly |
| Migrant with old LPG | Ujjwala → INELIGIBLE |
| Age 41 for PM-SYM | Hard INELIGIBLE — not UNCERTAIN |
| Tribal, no formal land records | PM Kisan → UNCERTAIN |
| ESIC member calls self "unorganised" | PM-SYM → INELIGIBLE |

---

## Prompt Log

All 17 AI prompts used to build this system are documented in [`prompt.md`](prompt.md), including:
- Every output kept or discarded
- Hallucinations caught and why they were wrong
- Anti-hallucination rules built into the extraction system prompt

This file constitutes **25% of the hackathon submission score**.

---

## Production Gaps

Two known gaps acknowledged in the architecture:

1. **SECC 2011 data** — Ayushman Bharat uses a 15-year-old deprivation survey. Integration with the PMJAY beneficiary API would fix this.
2. **State-specific variations** — Only central scheme rules are modelled. State-level additions (e.g., Rythu Bandhu in AP) are not yet covered.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| NLP Extraction | Google Gemini 2.5 Flash API |
| Rule Engine | Pure Python — no ML, full explainability |
| CLI | ANSI terminal with progress bars, spinners |
| Data | Hand-verified JSON logic trees |
| Tests | Custom adversarial test runner |
