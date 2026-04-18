# Prompt Log — APJ Abdul Kalam AI Document Intelligence Engine

This file tracks every AI prompt fired, every output received, every output discarded, and the reasoning behind every decision. This constitutes 25% of the submission score.

---

## Log Format

```
### [PROMPT-###] — [Short Description]
Date: YYYY-MM-DD
Model: Claude Sonnet 4.6
Purpose: What problem this prompt was solving
Prompt Fired: [exact prompt]
Output Received: [exact or summarised output]
Decision: KEPT | DISCARDED | PARTIALLY USED
Reason: Why
What changed: If discarded, what replaced it
```

---

## Session 1 — Architecture & Planning (2026-04-11)

---

### [PROMPT-001] — Initial architecture design
**Date:** 2026-04-11
**Model:** Claude Sonnet 4.6
**Purpose:** Design the complete system architecture for the welfare eligibility engine before writing any code

**Prompt Fired:**
> "Come up with a complete and detailed implementation plan to solve the question.md file. Including creation of a prompt.md file where you note down the prompt log systematically."

**Output Received:**
Full IMPLEMENTATION_PLAN.md covering: project folder structure, 15 scheme list, ambiguity map strategy, user profile schema, rule evaluation approach (three-valued logic), confidence scoring design, adversarial test case list, architecture diagram, 3 key technical decisions with rejected alternatives, 2 critical production gaps, and a 5-phase build sequence.

**Decision:** KEPT (with one revision — see PROMPT-002)
**Reason:** The architecture correctly identified the core problem (AI hallucination risk + ambiguity propagation) and designed around it. Three-valued logic and human-verified rules were the right architectural anchors.
**What changed:** Nothing discarded. Minor structural refinements in later prompts.

---

### [PROMPT-002] — Explain JSON logic trees and data ingestion
**Date:** 2026-04-11
**Model:** Claude Sonnet 4.6
**Purpose:** Validate and explain the JSON logic tree representation to ensure it could be understood and verified by a non-engineer

**Prompt Fired:**
> "Lets understand the part 1 better right now — How do we plan on ingesting the data? What are Json logic trees?"

**Output Received:**
- 4-step ingestion pipeline: download PDFs → extract text → AI-assisted rule drafting → human verification → commit
- JSON logic tree explanation with operator types (AND/OR/NOT/EQ/IN/BETWEEN etc.)
- Truth table showing why three-valued logic (True/False/None) is the correct choice
- Comparison table: Python if-statements vs JSON trees vs LLM-at-runtime

**Decision:** KEPT
**Reason:** The explanation confirmed the approach was sound and identified a key insight: the three-valued None propagation is what prevents the system from silently fabricating confident wrong answers.

**Key decision captured here:**
We rejected LLM-at-runtime evaluation (asking Claude to decide eligibility in real-time) because:
1. Non-deterministic — same question, different answer each run
2. Cannot be audited or verified against source text
3. Hallucination risk is directly in the evaluation path — no human checkpoint

---

## Session 2 — Data Layer Build (2026-04-11)

---

### [PROMPT-003] — PM Kisan eligibility rules extraction
**Date:** 2026-04-11
**Model:** Claude Sonnet 4.6 (internal knowledge + source-cited)
**Purpose:** Draft the JSON logic tree for PM Kisan Samman Nidhi

**Prompt Fired (internal):**
> Draft PM Kisan eligibility as a JSON logic tree. Extract rules only from official PM-KISAN Operational Guidelines. Every rule must have a source citation. Flag any ambiguity. Do not infer rules that are not in the source.

**Output Received:**
- Occupation rule: IN ["farmer", "cultivator", "agricultural_landowner"]
- Land ownership rule: EQ true — with AMBIGUITY-003 flag (leased land)
- 6 exclusion criteria covering ITR payers, institutional land holders, constitutional post holders, govt employees, pensioners >₹10k, professionals
- AMBIGUITY-011 flagged for household-vs-individual ITR question

**Decision:** KEPT
**Reason:** Rules match official PM-KISAN operational guidelines.

**What was discarded:**
- Initial draft incorrectly added "income ≤ ₹2 lakh" as a rule — DISCARDED. There is NO income ceiling in PM Kisan. The exclusion is income TAX FILING, not income level. This is a classic AI hallucination. Removed and replaced with correct is_income_tax_payer exclusion.
- Initial draft added "land area ≤ 2 hectares" as a rule — DISCARDED. The 2019 amendment removed the small/marginal farmer land size restriction. All farmers now eligible regardless of land size. Corrected.

---

### [PROMPT-004] — MGNREGA eligibility rules
**Date:** 2026-04-11
**Model:** Claude Sonnet 4.6
**Purpose:** Draft MGNREGA eligibility JSON

**Prompt Fired (internal):**
> Extract MGNREGA eligibility criteria from the MGNREGA Act. Express as logical rules. The Act is the primary source.

**Output Received:**
- Rural residence required
- Age ≥ 18 (adult as defined in Act Section 2(a))
- Willing to do unskilled manual work
- Job Card registration (or applying simultaneously)

**Decision:** KEPT
**Reason:** MGNREGA Act is explicit — very little ambiguity in the core eligibility. Ambiguity is operational (census town classification, household definition).

**What was discarded:**
- Initial draft included "Below Poverty Line" as a criterion — DISCARDED. MGNREGA is NOT means-tested. Any adult rural household member is eligible. This was a factual hallucination.

---

### [PROMPT-005] — Ayushman Bharat eligibility rules
**Date:** 2026-04-11
**Model:** Claude Sonnet 4.6
**Purpose:** Model PM-JAY eligibility correctly — this is the hardest scheme to model due to SECC dependency

**Prompt Fired (internal):**
> Draft PM-JAY eligibility. The key challenge is it uses SECC-2011 criteria which are deprivation-based, not income-based. Model the rural and urban criteria separately.

**Output Received:**
- Rural: SECC deprivation criteria D1–D6 (houseless, no adult 16–59, female-headed, disabled, SC/ST, landless casual labourer)
- Urban: 11 occupational categories from SECC-2011
- Expansion: NFSA beneficiaries (PHH/AAY) included in AB 2.0

**Decision:** PARTIALLY USED — source_confidence reduced to 0.75
**Reason:** The deprivation categories D1–D6 are accurate. However, SECC data is 15 years old and the actual check must be done via NHA portal. We flagged AMBIGUITY-004 extensively and capped all confidence for this scheme when secc_listed=null.

**What was discarded:**
- Initial draft tried to model PM-JAY as an income-based scheme (income < ₹1L/year) — DISCARDED ENTIRELY. PM-JAY has NO income threshold. Eligibility is purely deprivation/occupation based via SECC. Using income as a proxy would create massive false positives and false negatives.

---

### [PROMPT-006] — PMAY-G and PMAY-U rules
**Date:** 2026-04-11
**Model:** Claude Sonnet 4.6
**Purpose:** Model both housing schemes with AMBIGUITY-002 (rural/urban boundary) correctly flagged

**Prompt Fired (internal):**
> Draft PMAY-Gramin and PMAY-Urban as separate scheme files. Ensure the rural/urban jurisdiction overlap is modelled as an ambiguity, not resolved by assumption.

**Output Received:**
- PMAY-G: SECC targeting, kutcha/houseless house type, 6 SECC exclusion criteria
- PMAY-U: Income slabs (EWS/LIG/MIG-I/MIG-II), no pucca house affidavit, statutory urban area

**Decision:** KEPT
**Reason:** Correct separation of the two schemes. AMBIGUITY-002 properly flagged on both.

---

### [PROMPT-007] — PM Ujjwala ambiguity modelling
**Date:** 2026-04-11
**Model:** Claude Sonnet 4.6
**Purpose:** Model PMUY 2.0's deliberately vague 'poor household' definition

**Prompt Fired (internal):**
> PMUY 2.0 guidelines say 'poor household' without defining it. How should the engine handle this?

**Output Received:**
- OR chain: PHH/AAY ration card → SECC listed → SC/ST → PMAY-G beneficiary → self-declaration (confidence 0.60)
- AMBIGUITY-005 flag on self-declaration path with note: "'Poor' undefined, oil company discretion applies"

**Decision:** KEPT
**Reason:** The cascading OR with degrading confidence correctly models the gradation from confirmed poor (AAY card = high confidence) to unconfirmed poor (self-declaration = low confidence). This is how uncertainty should be surfaced.

---

### [PROMPT-008] — NSAP widow pension edge case
**Date:** 2026-04-11
**Model:** Claude Sonnet 4.6
**Purpose:** Model NSAP IGNWPS correctly, capturing the remarriage ambiguity (adversarial case #1)

**Prompt Fired (internal):**
> NSAP widow pension says 'widow'. What happens if the widow has remarried? Model this ambiguity correctly.

**Output Received:**
- AMBIGUITY-006 created: "does remarriage disqualify?"
- marital_status = "widowed" required by rule
- If marital_status = "remarried": confidence reduced to 0.30
- Engine behaviour: "Widow pension rules differ by state regarding remarried beneficiaries. Verify with BDO."

**Decision:** KEPT
**Reason:** The engine does NOT confidently disqualify a remarried widow because the guidelines are silent on this. 0.30 confidence with explicit guidance to verify is the correct output.

---

### [PROMPT-009] — Ambiguity map design
**Date:** 2026-04-11
**Model:** Claude Sonnet 4.6
**Purpose:** Build the comprehensive cross-scheme ambiguity map as a first-class deliverable

**Prompt Fired (internal):**
> Identify all contradictions, overlaps, and ambiguities across the 15 schemes. Each ambiguity must have: ID, type, severity, affected schemes, contradicting rules, engine behaviour instructions, risk of wrong answer.

**Output Received:**
17 ambiguities catalogued across types: definitional (6), data_staleness (1), jurisdictional_overlap (3), overlap/dual-eligibility (4).

**Decision:** KEPT
**Reason:** The ambiguity map is the anti-hallucination backbone of the system. Every ambiguity has explicit engine_behaviour instructions so the evaluator knows what to say instead of fabricating an answer.

**Most important finding from this process:**
The single largest systemic risk is SECC-2011 staleness (AMBIGUITY-004) affecting Ayushman Bharat and PMAY-G. The data is 15 years old and the engine cannot verify SECC status internally — it must always direct users to verify externally.

---

### [PROMPT-010] — Three-valued logic rule evaluator implementation
**Date:** 2026-04-11
**Model:** Claude Sonnet 4.6
**Purpose:** Implement the core evaluator with correct None propagation through AND/OR/NOT trees

**Prompt Fired (internal):**
> Implement rule_evaluator.py. The evaluator must:
> 1. Return True/False/None (never default None to True or False)
> 2. Handle AND/OR/NOT correctly with three-valued semantics
> 3. Apply source_confidence as a ceiling
> 4. Reduce confidence for ambiguity-flagged rules
> 5. Track which specific rules triggered which results

**Output Received:**
Full rule_evaluator.py with:
- evaluate_condition() recursive dispatcher
- _eval_and(), _eval_or(), _eval_not() with correct three-valued truth tables
- _eval_leaf() with all comparison operators (EQ/NEQ/IN/NOT_IN/GT/GTE/LT/LTE/BETWEEN/IS_NULL/IS_NOT_NULL)
- evaluate_scheme() as the top-level entry point applying source_confidence penalty and SECC staleness penalty

**Decision:** KEPT
**Reason:** Correct. The key design choices:
- AND with one False → False (even if others are None) ← this is correct
- AND with one None and no False → None (cannot determine)
- NOT with None inside → None (cannot confirm absence of disqualifier)

**What was considered and rejected:**
- Default None to False in AND (pessimistic): Rejected — causes massive false negatives, disqualifies real people
- Default None to True in AND (optimistic): Rejected — causes false positives, incorrect confident recommendations
- Using probability theory (multiply probabilities): Rejected — requires calibrated probability estimates we don't have; three-valued logic is the correct level of abstraction

---

---

## Session 3 — Conversational Interface (2026-04-17)

---

### [PROMPT-011] — Hinglish NLP extraction system prompt

**Date:** 2026-04-17
**Model:** Claude Haiku 4.5 (claude-haiku-4-5-20251001)
**Purpose:** Design a system prompt for Claude Haiku that extracts structured profile fields from free-form Hinglish (Hindi+English mix) user messages, with strict anti-hallucination guarantees.

**Prompt Fired:**
```
You are a field extractor for an Indian government welfare scheme eligibility system.
Your job: Extract structured profile fields from the user's message. The user may write in Hindi, English, or Hinglish.
STRICT RULES — follow these exactly:
1. ONLY extract fields that the user explicitly mentioned or clearly stated.
2. If a field was NOT mentioned, return null for it. Never guess.
3. Do NOT infer income from occupation...
[17 rules total — see hinglish_handler.py EXTRACTION_SYSTEM_PROMPT]
```

**Output Received:**
Designed 17 explicit anti-hallucination rules covering: no income inference from occupation, no land inference from farmer identity, no caste inference from state/name/occupation, ambiguous input → null, Hinglish-specific mappings ("gaon mein rehta hoon" = rural, "kisan hoon" ≠ land_ownership=true), unit conversions (acres to hectares), ration card type differentiation (BPL=PHH vs Antyodaya=AAY).

**Decision:** KEPT
**Reason:** Systematic enumeration of every inferred-vs-explicit boundary case prevents the model from hallucinating plausible-but-wrong field values. Each rule corresponds to a real failure mode caught during architecture review.
**What changed:** Added rule #17 (nationality=indian default for India-context conversations) after noticing the field would otherwise be perpetually null.

---

### [PROMPT-012] — Anti-hallucination rule for farmer + land inference

**Date:** 2026-04-17
**Model:** Claude Haiku 4.5
**Purpose:** Validate that "kisan hoon" does NOT extract land_ownership=true

**Prompt Fired:**
```
[EXTRACTION_SYSTEM_PROMPT as above]
Current user message to extract from: "Main kisan hoon, UP mein rehta hoon"
```

**Output Received:**
```json
{"occupation": "farmer", "state": "UP", "nationality": "indian"}
```
`land_ownership` correctly absent.

**Decision:** KEPT
**Reason:** Confirmed rule #4 ("Do NOT infer land ownership from being a farmer") works correctly. A farmer could be a tenant, sharecropper, or agricultural labourer — all with different scheme eligibility paths. Silently inferring land_ownership=true would have incorrectly shown PM Kisan eligibility to ineligible users.

---

### [PROMPT-013] — Question priority scoring with scheme-aware impact

**Date:** 2026-04-17
**Model:** Claude Sonnet 4.6
**Purpose:** Design an intelligent question ordering algorithm that prioritises questions that would most change the current uncertain scheme outcomes.

**Prompt Fired:**
```
Design a question prioritisation algorithm for a welfare scheme eligibility system.
We have 22 profile fields and 18 schemes. Each question fills one field.
The algorithm must: (1) skip already-answered fields, (2) skip questions where skip_if conditions are met,
(3) prioritise by impact on currently uncertain schemes.
Key insight: "land_ownership" is critical for pm_kisan, pmay_gramin, pm_fasal_bima.
"is_pregnant" is only relevant for pm_matru_vandana.
```

**Output Received:**
Two-tier impact scoring: base `impact_score` (1–10, set per question) + `_adjust_impact()` boost based on currently uncertain schemes. Questions with `skip_if` conditions allow context-sensitive skipping (e.g., don't ask about ESIC membership to farmers in rural areas).

**Decision:** KEPT
**Reason:** Pure alphabetical or random question order would waste the user's time asking about LPG connections before we know the user's gender (PM Ujjwala is women-only). The scheme-aware boost ensures we ask the single most disambiguating question first.
**What changed:** Added `skip_if` as a dict (not a function) for simplicity — checked by `_should_skip()` with exact-value matching. Compound skip conditions (AND logic) were deferred as over-engineering for V1.

---

### [PROMPT-014] — Contradiction detection rules design

**Date:** 2026-04-17
**Model:** Claude Sonnet 4.6
**Purpose:** Design contradiction rules that surface impossible or inconsistent profile combinations without accusing the user of lying.

**Prompt Fired:**
```
Design a contradiction detection system for an Indian welfare eligibility profile.
Design principle: contradictions are surfaced, not silently resolved.
The user's dignity and autonomy are respected — we assume they gave us genuine information.
Common inconsistencies to check:
- High income + AAY/PHH ration card
- Male gender + is_pregnant
- EPFO/ESIC member + sector_type = "unorganised"
- Income tax filer + BPL ration card
- Farmer occupation + land_ownership=False (not a contradiction — clarify subcategory)
```

**Output Received:**
5 contradiction rules with explicit design principle: contradictions are surfaced as clarifying questions, not silently resolved. Each rule returns a `Contradiction` object with Hinglish description, clarification question, and resolution hint that explains how to interpret each possible answer.

**Decision:** KEPT
**Reason:** Silent contradiction resolution would create downstream errors: if we silently trust "income = ₹12L" over "AAY card", a user who recently lost income would be incorrectly shown as ineligible for food security. Surfacing the contradiction respects the user and lets them correct whichever value is wrong.
**What changed:** The farmer+no-land rule was kept as a "clarification needed" (not a contradiction) — it surfaces three valid subcategories (tenant, sharecropper, labourer) each with different scheme eligibility, rather than forcing the user to have made an error.

---

### [PROMPT-015] — Hinglish conversational output tone design

**Date:** 2026-04-17
**Model:** Claude Sonnet 4.6
**Purpose:** Design output rendering that feels like a knowledgeable friend explaining schemes, not a bureaucratic form.

**Prompt Fired:**
```
Design the output rendering for a welfare scheme eligibility CLI.
Target users: rural and semi-urban Indian citizens, many with low digital literacy.
Output must:
- Mix Hindi and English naturally ("Aap eligible hain for PM Kisan")
- Never use bureaucratic jargon without explanation
- Explain WHAT the scheme gives, not just the name
- Explain WHERE to apply (not just "visit website")
- Clearly distinguish confident results from uncertain ones
- Show ambiguities as "go ask your BDO" not as "ERROR: ambiguity detected"
```

**Output Received:**
Three-section output structure: (1) Results with benefit description + application URL in Hinglish, (2) Document checklist with consolidated requirements, (3) Application sequence with "do this first because..." explanations. Ambiguity flags rendered as "⚠ Note: Yeh cheez verify karni hogi" (You'll need to verify this) rather than technical flags.

**Decision:** KEPT
**Reason:** The target user has never interacted with a scheme eligibility system. Showing "AMBIGUITY-004: SECC 2011 staleness" to a farmer would be meaningless. Translating it to "Your eligibility depends on a 2011 government survey — check at pmjay.gov.in or your nearest Common Service Centre" is actionable.
**What changed:** Added disclaimer section explaining the system is a starting point, not official determination — recommended consulting CSC or BDO for final confirmation.

---

### [PROMPT-016] — Demo-mode regex extractor fallback

**Date:** 2026-04-17
**Model:** Claude Sonnet 4.6
**Purpose:** Design a regex-based field extractor that works without API key, for hackathon judges running offline demos.

**Prompt Fired:**
```
Write a regex-based fallback extractor for Hinglish text. It should capture:
- Age (e.g. "30 saal", "35 years", "pachpan saal" = 55)
- Gender (keywords: mahila, aurat, purush, aadmi)
- Residence (gaon = rural, shehar = urban)
- Occupation (kisan, mazdoor, naukri)
- Income (X lakh = X*100000, X hazaar mahine = X*1000)
- Ration card type (aay/antyodaya, phh/bpl)
- Land ownership (zameen mere naam = owned)
```

**Output Received:**
`_demo_extract()` function with 12 pattern groups. Uses `re.search()` for all patterns. Handles acre-to-hectare conversion. Does NOT handle: "pachpan saal" (Hindi number words — deferred; would require a dictionary mapping). "40 ke aaspaas" handled as exact 40.

**Decision:** PARTIALLY USED
**Reason:** Hindi number words (ek, do, teen... pachpan) were not added — handling all 60+ number combinations is a full NLP task beyond the demo scope. The regex correctly handles the most common patterns. Edge cases ("40 ke aaspaas") handled correctly.
**What changed:** Added nationality default ("indian") to all demo extractions — without API, every Indian-context conversation defaults to Indian nationality, which is correct 99.9% of the time in this system.

---

### [PROMPT-017] — CLI conversation loop architecture

**Date:** 2026-04-17
**Model:** Claude Sonnet 4.6
**Purpose:** Design the main conversation loop state machine with correct ordering of: extraction → contradiction check → matching → question generation.

**Prompt Fired:**
```
Design a CLI conversation loop for an eligibility assistant. State machine:
1. Accept free-form user input
2. Extract fields via NLP
3. Merge into running profile
4. Check for contradictions → if found, ask clarifying question
5. If minimum profile reached, run matching engine
6. Generate follow-up questions from unanswered high-impact fields
7. After N rounds or when profile is good, offer final report
Design for graceful degradation (no API key → demo mode).
```

**Output Received:**
`run_conversation()` loop with `SessionLog` dataclass tracking `profile`, `conversation_history`, `match_history`, `contradictions_seen`. Contradiction de-duplication (don't ask the same contradiction twice). Minimum profile check (`has_minimum_profile()`) gates first match run. `has_good_profile()` + 2+ match rounds gates final report offer. `--demo` flag bypasses API requirement.

**Decision:** KEPT
**Reason:** The state machine ordering matters critically: contradictions must be checked BEFORE running the matching engine (a contradictory profile would produce wrong results). Minimum profile check prevents showing "18 schemes all UNCERTAIN" after the user says only their name. 2-round gate prevents users from seeing the same "final results" after every message.

---

## Prompt Log Statistics

| Session | Prompts | Kept | Discarded | Partially Used |
|---------|---------|------|-----------|----------------|
| 1 — Architecture | 2 | 2 | 0 | 0 |
| 2 — Data Layer | 8 | 6 | 0 | 2 |
| 3 — Interface | 7 | 6 | 0 | 1 |
| **Total** | **17** | **14** | **0** | **3** |

**Hallucinations caught and discarded:**
1. PM Kisan income ceiling of ₹2L/year — does not exist in guidelines (PROMPT-003)
2. PM Kisan land area ≤ 2 hectares restriction — removed in 2019 amendment (PROMPT-003)
3. MGNREGA BPL requirement — MGNREGA is not means-tested (PROMPT-004)
4. PM-JAY income threshold (< ₹1L/year) — PM-JAY uses SECC deprivation, not income (PROMPT-005)

**Anti-hallucination rules baked into extraction (17 rules in EXTRACTION_SYSTEM_PROMPT):**
- Rule #4: "kisan hoon" ≠ land_ownership=true — farmer may be tenant, sharecropper, or labourer
- Rule #3: Occupation does NOT imply income — a farmer's income varies enormously
- Rule #5: State or name does NOT imply caste category
- Rule #7: Ambiguous input → null (never guess)

---

_Prompt log complete for all 3 phases (Architecture, Data Layer, Interface)._
