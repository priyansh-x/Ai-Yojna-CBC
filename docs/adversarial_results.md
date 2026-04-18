# Adversarial Test Results — APJ Abdul Kalam AI Document Intelligence Engine

**Date:** 2026-04-17  
**Test Suite:** `tests/test_engine.py`  
**Result:** 10/10 PASS

---

## Test Architecture

Each adversarial test validates 4 categories of engine behaviour:

1. **Status checks** — Did the scheme get the expected status (FULLY_ELIGIBLE / LIKELY_ELIGIBLE / ALMOST_ELIGIBLE / UNCERTAIN / INELIGIBLE)?
2. **Ambiguity flag checks** — Were the expected ambiguity flags surfaced in the output?
3. **No false confidence** — Did any UNCERTAIN scheme incorrectly receive FULLY_ELIGIBLE?
4. **No checklist for INELIGIBLE** — Did clearly ineligible schemes correctly produce no document checklist?

---

## Full Test Results

---

### ADV-001 — Sunita Devi, 52, remarried widow
**Result: ✓ PASS**

**Adversarial intent:** Tests whether remarriage to widow pension is handled as ambiguous, not as a confident disqualification.

**Profile:** 52-year-old OBC woman from Bihar. Widowed, remarried 8 months ago. Previously receiving NSAP IGNWPS pension. PHH ration card. Owns 0.6 hectare land (in deceased first husband's name). Rural. Semi-pucca house. Income ₹55,000/year.

**The trap:** A naive system might immediately disqualify her from widow pension (NSAP IGNWPS) on `marital_status = "remarried"`. This would be wrong — the guidelines are silent on remarriage.

**Engine behaviour:**

| Scheme | Expected | Got | Reason |
|--------|----------|-----|--------|
| nsap | UNCERTAIN | UNCERTAIN | AMBIGUITY-006: remarriage disqualification not stated in central guidelines |
| pm_kisan | UNCERTAIN | UNCERTAIN | AMBIGUITY-003: land in deceased husband's name — ownership ambiguous |
| pmgkay | FULLY_ELIGIBLE | FULLY_ELIGIBLE | PHH ration card directly qualifies |
| pm_suraksha_bima | FULLY_ELIGIBLE | FULLY_ELIGIBLE | Age 18–70, bank account, ₹20/year premium |

**Ambiguity flags surfaced:** AMBIGUITY-006 ✓, AMBIGUITY-003 ✓

**Must-not-do violations:** None — engine correctly avoided INELIGIBLE for NSAP and avoided FULLY_ELIGIBLE for uncertain schemes.

---

### ADV-002 — Ramprasad Yadav, 38, tenant farmer
**Result: ✓ PASS**

**Adversarial intent:** Tests the PM Kisan ownership ambiguity for tenant farmers, and verifies PMFBY correctly includes them.

**Profile:** 38-year-old OBC man from Madhya Pradesh. Tenant farmer on 1.2 hectares of leased land. PHH ration card. Income ₹72,000/year. Rural, kutcha house. Bank account. Not an ITR filer.

**The trap:** (1) PM Kisan should be UNCERTAIN not INELIGIBLE — tenant farmers are not explicitly excluded. (2) PMFBY should be ALMOST_ELIGIBLE — crop insurance covers tenant farmers but requires `grows_notified_crop` field. Confusing the two schemes (or marking PM Kisan INELIGIBLE with high confidence) is wrong.

**Engine behaviour:**

| Scheme | Expected | Got | Reason |
|--------|----------|-----|--------|
| pm_kisan | UNCERTAIN | UNCERTAIN | AMBIGUITY-003: leased land, land_ownership=False |
| pm_fasal_bima | ALMOST_ELIGIBLE | ALMOST_ELIGIBLE | Tenant farmer eligible, but `grows_notified_crop` missing |
| pmgkay | FULLY_ELIGIBLE | FULLY_ELIGIBLE | PHH card qualifies |

**Ambiguity flags surfaced:** AMBIGUITY-003 ✓, AMBIGUITY-001 ✓

---

### ADV-003 — Mohan Lal, 45, unbanked farmer
**Result: ✓ PASS**

**Adversarial intent:** Tests prerequisite sequencing — unbanked user must be shown PMJDY first, not a useless PM Kisan rejection.

**Profile:** 45-year-old GEN man from Rajasthan. Owns 2.5 hectares of land. Rural. Income ₹90,000/year. **No bank account.** Not an ITR filer. All exclusion fields explicitly False.

**The trap:** Without a bank account, PM Kisan cannot disburse benefits. A naive system might either: (a) mark PM Kisan INELIGIBLE because the prerequisite is unmet, or (b) mark PM Kisan FULLY_ELIGIBLE without flagging the banking gap. Neither is correct.

**Engine behaviour:**

| Scheme | Expected | Got | Reason |
|--------|----------|-----|--------|
| pm_jan_dhan | FULLY_ELIGIBLE | FULLY_ELIGIBLE | No bank account → PMJDY is the first step |
| pm_kisan | LIKELY_ELIGIBLE | LIKELY_ELIGIBLE | Rules pass, but bank account needed for disbursement |
| pmgkay | FULLY_ELIGIBLE | FULLY_ELIGIBLE | No ration card, but GEN + income qualifies for NFSA |

**Application sequence:** PMJDY listed as Step 1 (enabler) before PM Kisan. ✓

---

### ADV-004 — Deepak Kumar, 33, peri-urban farmer
**Result: ✓ PASS**

**Adversarial intent:** Tests rural/urban boundary ambiguity — peri-urban users fall in a genuine administrative gap.

**Profile:** 33-year-old OBC man from Maharashtra. Claims to live "in between" — peri-urban fringe. Farmer with 1.8 hectares owned land. PHH ration card. Income ₹1,10,000/year. House type: semi-pucca.

**The trap:** `residence_type = "peri-urban"` is jurisdictionally ambiguous. PMAY-G (rural), PMAY-U (urban), and MGNREGA (rural) all depend on this classification. A confident answer either way would be wrong.

**Engine behaviour:**

| Scheme | Expected | Got | Reason |
|--------|----------|-----|--------|
| pmay_gramin | UNCERTAIN | UNCERTAIN | Peri-urban → rural check returns None |
| pmay_urban | UNCERTAIN | UNCERTAIN | Peri-urban → urban check returns None |
| mgnrega | UNCERTAIN | UNCERTAIN | Peri-urban → Gram Panchayat jurisdiction unclear |
| pmgkay | FULLY_ELIGIBLE | FULLY_ELIGIBLE | PHH card — no urban/rural dependency |

**Ambiguity flags surfaced:** AMBIGUITY-002 ✓, AMBIGUITY-003 ✓, AMBIGUITY-013 ✓

---

### ADV-005 — Priya, 19, unmarried pregnant
**Result: ✓ PASS**

**Adversarial intent:** Tests whether the engine adds a non-existent marital status requirement to PMMVY — a common AI hallucination.

**Profile:** 19-year-old ST woman. Unmarried. Pregnant with first child. Rural. PHH ration card. No LPG. Agricultural labourer (no land). Income ₹36,000/year. Bank account, Aadhaar linked.

**The trap:** PMMVY (maternity benefit) was originally conditional on first child and registration before delivery. Many LLMs hallucinate a "must be married" requirement that does not exist in official guidelines. Budget 2023 also extended coverage to second child if girl.

**Engine behaviour:**

| Scheme | Expected | Got | Reason |
|--------|----------|-----|--------|
| pm_matru_vandana | LIKELY_ELIGIBLE | LIKELY_ELIGIBLE | `is_pregnant=True`, `marital_status` not used as disqualifier |
| pmgkay | FULLY_ELIGIBLE | FULLY_ELIGIBLE | PHH card |
| ayushman_bharat | LIKELY_ELIGIBLE | LIKELY_ELIGIBLE | ST category + PHH card via NFSA |

**Ambiguity flags surfaced:** AMBIGUITY-015 ✓ (unmarried mother PMMVY practice)

**Anti-hallucination check:** Engine did NOT add marital status requirement. ✓

---

### ADV-006 — Giriraj Singh, 62, farmer with salaried son
**Result: ✓ PASS**

**Adversarial intent:** Tests household-vs-individual ITR interpretation for PM Kisan exclusion.

**Profile:** 62-year-old GEN man from Uttar Pradesh. Farmer with 3.2 hectares owned land. Rural. PHH ration card. Income ₹95,000/year. Has a salaried son living in the household who files ITR (`household_member_files_itr = True`). All personal exclusion fields False.

**The trap:** The salaried son's ITR filing creates an AMBIGUITY-011 situation. The PM Kisan exclusion says "family member files ITR" but this is ambiguous — if the son lives separately, the grandfather farmer would qualify. If they are one household unit, maybe not.

**Engine behaviour:**

| Scheme | Expected | Got | Reason |
|--------|----------|-----|--------|
| pm_kisan | LIKELY_ELIGIBLE | LIKELY_ELIGIBLE | AMBIGUITY-011 surfaced but not sufficient to force UNCERTAIN (personal ITR = False; son's ITR creates flag not disqualification) |
| pmay_gramin | INELIGIBLE | INELIGIBLE | Age 62 + PHH card + pucca house already owned — PMAY-G eligibility criteria not met |

**Ambiguity flags surfaced:** AMBIGUITY-011 ✓

---

### ADV-007 — Kamla Bai, 40, migrant with old LPG
**Result: ✓ PASS**

**Adversarial intent:** Tests the LPG connection ambiguity for migrant workers with old connections.

**Profile:** 40-year-old SC woman from West Bengal (migrated from UP). PHH ration card. Agricultural labourer. Income ₹42,000/year. Has LPG connection from 5 years ago (now in UP, inactive). Rural. Kutcha house. Bank account.

**The trap:** She has `has_lpg_connection = True` (technically) but the connection is inactive and in a different state. A naive system might mark PMUY as ALMOST_ELIGIBLE ("she almost qualifies but needs X"). The correct answer is INELIGIBLE — she has a connection — but with AMBIGUITY-005 surfaced for the edge case.

**Engine behaviour:**

| Scheme | Expected | Got | Reason |
|--------|----------|-----|--------|
| pm_ujjwala | INELIGIBLE | INELIGIBLE | `has_lpg_connection = True` → clean INELIGIBLE, AMBIGUITY-005 surfaced |
| pmgkay | FULLY_ELIGIBLE | FULLY_ELIGIBLE | PHH card |
| pm_suraksha_bima | FULLY_ELIGIBLE | FULLY_ELIGIBLE | Age 18–70, bank account, ₹20/year |

**Ambiguity flags surfaced:** AMBIGUITY-005 ✓

---

### ADV-008 — Suresh Bind, 41, just over age limit
**Result: ✓ PASS**

**Adversarial intent:** Tests hard age boundary — engine must return clean INELIGIBLE with non-actionable gap, not uncertainty.

**Profile:** 41-year-old OBC unorganised worker from Bihar. Not EPFO, not ESIC. Income ₹8,500/month. PHH ration card. Bank account. Rural. Semi-pucca.

**The trap:** PM-SYM and APY both have hard age cutoffs (40 years). A user who is 41 years old has missed the entry window. The engine must return INELIGIBLE with a clear "age 41 exceeds maximum entry age of 40" gap — not UNCERTAIN, not ALMOST_ELIGIBLE. The gap must be flagged as non-actionable (you cannot change your age).

**Engine behaviour:**

| Scheme | Expected | Got | Reason |
|--------|----------|-----|--------|
| pm_shram_yogi_mandhan | INELIGIBLE | INELIGIBLE | Age 41 > 40 (hard boundary) |
| atal_pension_yojana | INELIGIBLE | INELIGIBLE | Age 41 > 40 (hard boundary) |
| pm_jeevan_jyoti_bima | FULLY_ELIGIBLE | FULLY_ELIGIBLE | Age 18–50, bank account |
| pm_suraksha_bima | FULLY_ELIGIBLE | FULLY_ELIGIBLE | Age 18–70, bank account, ₹20/year |
| pmgkay | FULLY_ELIGIBLE | FULLY_ELIGIBLE | PHH card |

**Hard field check:** Age is a HARD_FIELD — failure on age → INELIGIBLE (not ALMOST_ELIGIBLE). ✓  
**Gap actionability:** "You are 41. PM-SYM requires entry before 40 — this gap cannot be closed." ✓

---

### ADV-009 — Birsa Munda, 48, tribal farmer, no formal land records
**Result: ✓ PASS**

**Adversarial intent:** Tests tribal land tenure ambiguity — FRA rights are legally valid but may not be recognized by local PM Kisan implementation.

**Profile:** 48-year-old ST man from Jharkhand. Farmer. Has Forest Rights Act (FRA) title for 1.4 hectares — `fra_title_pending = True` (title granted but administrative processing incomplete). No formal Khasra number. PHH ration card. Rural. Kutcha house. Income ₹62,000/year.

**The trap:** The `fra_title_pending = True` means he has legal land rights under FRA but lacks the administrative record typically required by PM Kisan implementation. A confident ELIGIBLE answer ignores the administrative gap; a confident INELIGIBLE answer ignores his legal rights.

**Engine behaviour:**

| Scheme | Expected | Got | Reason |
|--------|----------|-----|--------|
| pm_kisan | UNCERTAIN | UNCERTAIN | FRA title pending → land_ownership status unclear |
| mgnrega | LIKELY_ELIGIBLE | LIKELY_ELIGIBLE | ST category, rural, no hard exclusions |
| pmay_gramin | FULLY_ELIGIBLE | FULLY_ELIGIBLE | ST + kutcha house + rural → PMAY-G priority |
| ayushman_bharat | LIKELY_ELIGIBLE | LIKELY_ELIGIBLE | ST category + PHH card |
| pmgkay | FULLY_ELIGIBLE | FULLY_ELIGIBLE | PHH card |

---

### ADV-010 — Ramesh Patel, 29, factory worker self-reporting as unorganised
**Result: ✓ PASS**

**Adversarial intent:** Tests contradiction handling — user self-reports as unorganised but explicit `is_esic_member = True` must take priority.

**Profile:** 29-year-old GEN man from Gujarat. Factory worker. Self-described as "unorganised worker" (`sector_type = "unorganised"`). But **also** `is_esic_member = True` and `is_epfo_member = True` — his employer has enrolled him in both, which he may not have been aware of.

**The trap:** A naive system might grant PM-SYM or APY eligibility because `sector_type = "unorganised"` was set. The correct answer: EPFO/ESIC membership = organised sector, full stop. The contradiction detector should surface this as a clarifying question in the conversational interface. In the matching engine, explicit EPFO/ESIC membership is an exclusion criterion.

**Engine behaviour:**

| Scheme | Expected | Got | Reason |
|--------|----------|-----|--------|
| pm_shram_yogi_mandhan | INELIGIBLE | INELIGIBLE | `is_esic_member = True` → NOT condition fires |
| atal_pension_yojana | INELIGIBLE | INELIGIBLE | `is_epfo_member = True` → NOT condition fires |
| pm_jeevan_jyoti_bima | FULLY_ELIGIBLE | FULLY_ELIGIBLE | Age 18–50, bank account |
| pm_suraksha_bima | FULLY_ELIGIBLE | FULLY_ELIGIBLE | Age 18–70, bank account, ₹20/year |

**Contradiction detection:** `_check_epfo_and_unorganised()` would surface this during conversation. ✓  
**Anti-false-eligibility check:** `is_esic_member = True` correctly overrides `sector_type = "unorganised"`. ✓

---

## Summary Table

| Case | Profile | Key Test | Result |
|------|---------|----------|--------|
| ADV-001 | Sunita Devi, 52 | Remarried widow → UNCERTAIN not INELIGIBLE for pension | ✓ PASS |
| ADV-002 | Ramprasad, 38 | Tenant farmer → PM Kisan UNCERTAIN, PMFBY ALMOST | ✓ PASS |
| ADV-003 | Mohan Lal, 45 | Unbanked → PMJDY first in sequence | ✓ PASS |
| ADV-004 | Deepak, 33 | Peri-urban → UNCERTAIN for all rural/urban schemes | ✓ PASS |
| ADV-005 | Priya, 19 | Unmarried + pregnant → no hallucinated marital requirement | ✓ PASS |
| ADV-006 | Giriraj, 62 | Son's ITR → AMBIGUITY-011 surfaced, not false INELIGIBLE | ✓ PASS |
| ADV-007 | Kamla Bai, 40 | Old LPG → INELIGIBLE for PMUY + AMBIGUITY-005 | ✓ PASS |
| ADV-008 | Suresh, 41 | Age 41 → hard INELIGIBLE for PM-SYM/APY, not UNCERTAIN | ✓ PASS |
| ADV-009 | Birsa, 48 | FRA title → PM Kisan UNCERTAIN, PMAY-G FULLY | ✓ PASS |
| ADV-010 | Ramesh, 29 | ESIC member self-reports unorganised → PM-SYM INELIGIBLE | ✓ PASS |

**Final score: 10/10**

---

## Key Engine Behaviours Validated

### Ambiguity is not collapsed
ADV-001, ADV-002, ADV-004, ADV-009: In every case where the official guidelines are genuinely unclear, the engine returns UNCERTAIN and surfaces the specific ambiguity flag. It does not guess.

### Hard fields are hard
ADV-008: Age is a hard disqualifier. When a user is 41 and the cutoff is 40, the result is INELIGIBLE — not ALMOST_ELIGIBLE ("just 1 year over") and not UNCERTAIN. Age cannot be changed; the gap is non-actionable.

### NOT conditions are reliable
ADV-010: When an explicit exclusion criterion fires (`is_esic_member = True`), the result is always INELIGIBLE regardless of any other positive signals (`sector_type = "unorganised"`). The NOT condition cannot be overridden by other conditions.

### Prerequisite sequencing works
ADV-003: An unbanked user who is otherwise eligible for PM Kisan sees PMJDY as the first step in their application sequence. The system doesn't show them a PM Kisan application form without a bank account first.

### No hallucinated requirements
ADV-005: No marital status requirement was added to PMMVY. The system only evaluates rules that exist in the official guidelines, not plausible-sounding rules that were never enacted.

### OR branch safety in hard field detection
ADV-001 (NSAP): The NSAP scheme has an OR branch covering different sub-schemes (IGNOAPS for elderly, IGNWPS for widows). The hard field detector does not recurse into OR branches — doing so would have incorrectly flagged `age` (inside IGNOAPS) as a disqualifier for a user on the IGNWPS path.
