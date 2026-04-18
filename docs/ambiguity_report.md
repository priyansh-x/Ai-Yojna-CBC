# Ambiguity Report — APJ Abdul Kalam AI Document Intelligence Engine

**Date:** 2026-04-17  
**Total ambiguities catalogued:** 17  
**Ambiguities affecting engine output:** 13 (4 are informational only)

---

## What Is an Ambiguity?

An ambiguity in this system is a situation where **the official government guidelines are unclear, contradictory, or silent on a specific case**, creating genuine uncertainty about whether a citizen qualifies for a scheme.

We differentiate three causes:

| Type | Cause | Example |
|------|-------|---------|
| **Regulatory gap** | Guidelines don't cover the edge case at all | PM Kisan: does "farmer" include tenant farmers? (AMBIGUITY-003) |
| **Staleness** | Guidelines reference outdated data (SECC 2011) | Ayushman Bharat: SECC data is 15 years old (AMBIGUITY-004) |
| **Definitional inconsistency** | Term defined differently in different places | PM Kisan: "household" vs "individual" for ITR exclusion (AMBIGUITY-011) |

---

## Design Principle

When an ambiguous condition is the deciding factor for a scheme result, the engine:
1. Does **NOT** guess
2. Does **NOT** silently pick one interpretation
3. Marks the scheme **UNCERTAIN**
4. Surfaces the specific ambiguity flag in the output
5. Directs the user to the appropriate authority (BDO / CSC / agriculture office)

This is the only safe behaviour in a welfare eligibility context. A confident wrong answer can cause a citizen to not apply for a scheme they deserve, or to waste time applying for one they don't qualify for.

---

## Ambiguity Catalogue

---

### AMBIGUITY-001 — PM Kisan: Agricultural labourer vs farmer

**Severity:** HIGH  
**Affects:** pm_kisan, pm_fasal_bima, pm_kisan_credit_card  
**Type:** Regulatory gap

**The gap:**  
PM Kisan Operational Guidelines define beneficiaries as "farmer families... owning cultivable land." Agricultural labourers who work on others' land are not explicitly included or excluded. State governments have discretion.

**Engine behaviour:**  
If `occupation = "agricultural_labourer"` → INELIGIBLE for PM Kisan (land ownership required).  
If `occupation = "farmer"` and `land_ownership = False` → UNCERTAIN + AMBIGUITY-001 flagged.  
The contradiction detector also surfaces this as a clarification question.

**What the user is told:**  
"Aapki farming arrangement (sharecrop/labour) PM Kisan eligibility affect kar sakti hai. Apne local agriculture office se verify karen."

---

### AMBIGUITY-002 — MGNREGA/PMAY: Peri-urban jurisdiction

**Severity:** MEDIUM  
**Affects:** mgnrega, pmay_gramin, pmay_urban  
**Type:** Definitional inconsistency

**The gap:**  
MGNREGA applies to "rural areas" and PMAY-G to "rural" households. The Census defines "urban" and "rural" but some areas (notified towns, census towns, outgrowths) fall in between. A citizen in a peri-urban fringe may be administratively rural (Gram Panchayat jurisdiction) but geographically urban.

**Engine behaviour:**  
`residence_type = "peri-urban"` compared to `"rural"` or `"urban"` returns `None` (not True or False). Any scheme requiring rural/urban residence becomes UNCERTAIN for peri-urban users.

**What the user is told:**  
"Aapke area ki rural/urban classification verify karni hogi. Apne Block Development Office se check karen."

---

### AMBIGUITY-003 — PM Kisan: Leased and sharecrop land

**Severity:** CRITICAL  
**Affects:** pm_kisan  
**Type:** Regulatory gap

**The gap:**  
PM Kisan Operational Guidelines Section 4.4 excludes "farmer families who are Institutional Land holders." It does not explicitly exclude tenant farmers or sharecroppers. However, the primary eligibility criterion requires land "in the name" of the farmer. Many states have implemented PM Kisan only for landowners with recorded Khasra/Khatauni numbers, effectively excluding tenants. Some states (e.g., West Bengal with Barga system) have extended coverage.

**Engine behaviour:**  
`land_ownership = False` → UNCERTAIN (not INELIGIBLE) with AMBIGUITY-003 flagged.  
`land_type = "leased"` or `"sharecrop"` → UNCERTAIN with AMBIGUITY-003 flagged.

**What the user is told:**  
"PM Kisan mein zameen ownership ki zaroorat hai. Agar aap leased ya sharecrop zameen par kaam karte hain, to eligibility uncertain hai — apne Gram Panchayat ya agriculture office se verify karen."

**Risk if resolved incorrectly:**  
- Resolving as ELIGIBLE: millions of tenant farmers incorrectly guided to apply, wasting time and raising false expectations  
- Resolving as INELIGIBLE: legitimate beneficiaries in states with expanded coverage are told they don't qualify

---

### AMBIGUITY-004 — Ayushman Bharat: SECC 2011 staleness

**Severity:** HIGH  
**Affects:** ayushman_bharat  
**Type:** Staleness

**The gap:**  
PM-JAY (Ayushman Bharat) uses SECC 2011 deprivation data as the primary beneficiary list. As of 2026, this data is 15 years old. Families who were poor in 2011 may no longer be poor; families who became poor after 2011 are not in the list. The government has added NFSA/PHH ration card holders as an alternate pathway, but the primary SECC list is frozen.

**Engine behaviour:**  
Cannot access SECC 2011 database. Uses PHH ration card as proxy → LIKELY_ELIGIBLE (confidence 0.48) with AMBIGUITY-004 flagged.  
`secc_listed = True` (if user knows) → higher confidence.  
`secc_listed = False` and no ration card → UNCERTAIN.

**What the user is told:**  
"Aapki eligibility 2011 government survey ke data par depend karti hai. pmjay.gov.in par ya nearest Common Service Centre par apna naam check karen."

---

### AMBIGUITY-005 — PM Ujjwala: LPG connection type and refill subsidies

**Severity:** MEDIUM  
**Affects:** pm_ujjwala  
**Type:** Definitional inconsistency

**The gap:**  
PM Ujjwala provides a free LPG connection to BPL women. However, scheme guidelines are unclear about migrant families: if a woman received a connection under the scheme in her home district but relocated, and the connection is now in "inactive" status due to no refills, does she still have an "LPG connection" for exclusion purposes? PMUY 2.0 (2022) expanded eligibility but the guidelines on prior connection status remain ambiguous.

**Engine behaviour:**  
`has_lpg_connection = True` → INELIGIBLE (treated as already having connection).  
Ambiguity is surfaced when the user mentions migration + existing LPG, recommending verification.

**What the user is told:**  
"Agar aapka purana LPG connection inactive hai ya doosre state mein hai, to PMUY 2.0 mein apply karne ka option ho sakta hai. Apne nearest LPG distributor se pata karen."

---

### AMBIGUITY-006 — NSAP: Remarried widow pension continuation

**Severity:** MEDIUM  
**Affects:** nsap (IGNWPS sub-scheme)  
**Type:** Regulatory gap

**The gap:**  
The NSAP guidelines for Indira Gandhi National Widow Pension Scheme (IGNWPS) do not explicitly state that remarriage disqualifies a widow from continuing to receive pension. Some state governments discontinue on remarriage; others allow continuation for a transition period. The central guidelines are silent.

**Engine behaviour:**  
`marital_status = "remarried"` and `previous_spouse_deceased = True` → UNCERTAIN for NSAP IGNWPS sub-scheme with AMBIGUITY-006 flagged. Does NOT mark as INELIGIBLE.

**What the user is told:**  
"Aapki widow pension aur remarriage ke baare mein aapke BDO se confirm karna zaroor hai — rules state-level par alag ho sakte hain."

---

### AMBIGUITY-007 — PMAY-Gramin: House-less vs kutcha house

**Severity:** LOW  
**Affects:** pmay_gramin  
**Type:** Definitional inconsistency

**The gap:**  
PMAY-G targets "houseless" and "living in kutcha/dilapidated houses." The definition of "kutcha" is not standardised — district officials apply it differently. A house made of mud walls with a concrete floor might qualify in one district but not another.

**Engine behaviour:**  
`house_type = "kutcha"` → included in eligibility check. `house_type = "semi-pucca"` → treated as not qualifying for housing scheme. Low ambiguity impact — surfaced as informational note only.

---

### AMBIGUITY-008 — MGNREGA: 100 days per household definition

**Severity:** LOW  
**Affects:** mgnrega  
**Type:** Definitional inconsistency

**The gap:**  
MGNREGA guarantees 100 days of employment "per rural household per year." For large joint families, it is unclear whether the 100-day guarantee applies to the entire joint family unit or to each nuclear family within it. Practice varies by Gram Panchayat.

**Engine behaviour:**  
No impact on eligibility determination. Surfaced as informational ambiguity in output for users with large family sizes.

---

### AMBIGUITY-009 — PM-SYM: Entry age and exit without pension

**Severity:** LOW  
**Affects:** pm_shram_yogi_mandhan  
**Type:** Regulatory gap

**The gap:**  
PM-SYM allows entry between 18–40 years. For users approaching 40, the scheme is technically available but the long-term pension benefit may not vest before statutory retirement age. The guidelines don't address what happens if contributions stop before 60 years.

**Engine behaviour:**  
Age 41+ → INELIGIBLE (clear hard boundary). Age 38–40 → LIKELY_ELIGIBLE with note about diminishing window. This is handled as a clear rule, not an ambiguity.

---

### AMBIGUITY-010 — PMJDY: Insurance on pre-2014 accounts

**Severity:** LOW  
**Affects:** pm_jan_dhan  
**Type:** Staleness

**The gap:**  
PMJDY was launched in 2014. Bank accounts opened under the scheme automatically carry ₹2L accidental death insurance via RuPay card. However, citizens who converted a pre-existing savings account to PMJDY may not have received the RuPay card upgrade, and the insurance coverage may not apply. The guidelines on retroactive coverage are unclear.

**Engine behaviour:**  
Surfaced as informational flag when user has an existing bank account of unknown age. Core eligibility not affected — PMJDY eligibility is about opening a new account (or confirming existing account is PMJDY-compliant).

---

### AMBIGUITY-011 — PM Kisan: Household vs individual ITR exclusion

**Severity:** HIGH  
**Affects:** pm_kisan  
**Type:** Definitional inconsistency

**The gap:**  
PM Kisan exclusion criteria state "farmer families... whose members are or were income tax payers." This could mean: (a) any member of the household ever filed ITR, or (b) the farmer himself is an ITR filer. In joint families with salaried adult children, interpretation (a) would exclude many genuine small farmers.

**Engine behaviour:**  
`is_income_tax_payer = True` → INELIGIBLE for PM Kisan (conservative interpretation).  
If the household has a salaried member whose ITR status is unknown → AMBIGUITY-011 flagged, status UNCERTAIN.

**What the user is told:**  
"Agar aapke ghar mein koi income tax bharta hai, to PM Kisan eligibility uncertain ho sakti hai. Apne local agriculture office se pata karen."

---

### AMBIGUITY-012 — Sukanya Samriddhi: Guardian eligibility for non-biological guardians

**Severity:** LOW  
**Affects:** sukanya_samriddhi  
**Type:** Regulatory gap

**The gap:**  
SSY allows accounts by "natural or legal guardian of a girl child." Legal guardian eligibility for non-biological guardians (adoptive parents, grandparents raising grandchildren) is technically covered but practically difficult to establish without legal guardianship documents.

**Engine behaviour:**  
Not modelled separately — captured under `is_parent_or_guardian_of_girl` boolean. Users without legal guardianship documentation are directed to their nearest post office for assessment.

---

### AMBIGUITY-013 — MGNREGA: Peri-urban Gram Panchayat jurisdiction

**Severity:** MEDIUM  
**Affects:** mgnrega  
**Type:** Regulatory gap

**The gap:**  
MGNREGA applies to areas under Gram Panchayat jurisdiction. Some peri-urban areas that are geographically close to cities remain under Gram Panchayat (not Municipal Corporation) jurisdiction and are technically MGNREGA-eligible. Other areas have been absorbed into Urban Local Bodies and are not eligible. This is specific to each district's administrative boundary.

**Engine behaviour:**  
`residence_type = "peri-urban"` → UNCERTAIN for MGNREGA with AMBIGUITY-013 flagged.

---

### AMBIGUITY-014 — PMAY-Urban: BLC vs CLSS vs AHP sub-scheme

**Severity:** LOW  
**Affects:** pmay_urban  
**Type:** Definitional inconsistency

**The gap:**  
PMAY-U has four components: CLSS (Credit Linked Subsidy), AHP (Affordable Housing in Partnership), BLC (Beneficiary-Led Construction), and In-Situ Slum Redevelopment. Eligibility differs across sub-components (income ranges, family status, existing house ownership). The engine models PMAY-U at the scheme level, not the sub-component level.

**Engine behaviour:**  
PMAY-U eligibility check is at the top scheme level. Sub-component recommendation deferred to CSC/BDO.

---

### AMBIGUITY-015 — PMMVY: First child condition for unmarried mothers

**Severity:** MEDIUM  
**Affects:** pm_matru_vandana  
**Type:** Regulatory gap

**The gap:**  
PMMVY was originally for the "first living birth." Budget 2023 extended it to the second child if the second child is a girl. For unmarried mothers, the "first living birth" condition is not explicitly addressed — some state implementing agencies have required marriage proof, others have not.

**Engine behaviour:**  
`is_pregnant = True` and `marital_status = "single"` → LIKELY_ELIGIBLE with AMBIGUITY-015 flagged. Does not exclude on marital status.

**What the user is told:**  
"Aapki PMMVY eligibility ke baare mein aapke nearest aanganwadi ya CSC par confirm karen — marital status related requirements state-level par alag ho sakte hain."

---

### AMBIGUITY-016 — Kisan Credit Card: Tenant farmer access

**Severity:** HIGH  
**Affects:** pm_kisan_credit_card  
**Type:** Regulatory gap

**The gap:**  
KCC guidelines include "tenant farmers, oral lessees, sharecroppers, Self Help Groups (SHGs), or Joint Liability Groups (JLGs)" as eligible. However, banks in practice require land ownership documents (Khasra) for security purposes, making KCC practically inaccessible to tenant farmers despite formal eligibility. RBI guidelines acknowledge this gap.

**Engine behaviour:**  
Tenant farmers → ALMOST_ELIGIBLE for KCC with gap: "Land ownership documentation." AMBIGUITY-016 noted in output.

---

### AMBIGUITY-017 — APY: Overlap with NPS

**Severity:** LOW  
**Affects:** atal_pension_yojana  
**Type:** Definitional inconsistency

**The gap:**  
APY excludes existing NPS subscribers. However, some government employees who are in NPS have been enrolled by their employer without their knowledge. The exclusion for involuntary NPS enrollment is not addressed in APY guidelines.

**Engine behaviour:**  
`is_nps_subscriber = True` → INELIGIBLE for APY (conservative interpretation — employer-enrolled NPS still counts).

---

## Ambiguity Summary by Severity

| Severity | Count | Schemes Most Affected |
|----------|-------|-----------------------|
| CRITICAL | 1 | PM Kisan |
| HIGH | 4 | PM Kisan (×3), Ayushman Bharat |
| MEDIUM | 4 | NSAP, MGNREGA, PMAY, PMMVY |
| LOW | 8 | Various |

**Ambiguities that change engine output vs informational only:**

| ID | Changes Output? | How |
|----|-----------------|-----|
| AMBIGUITY-001 | YES | Farmer + no land → UNCERTAIN not INELIGIBLE |
| AMBIGUITY-002 | YES | Peri-urban → UNCERTAIN for rural/urban schemes |
| AMBIGUITY-003 | YES | Leased/sharecrop land → UNCERTAIN for PM Kisan |
| AMBIGUITY-004 | YES | No SECC data → LIKELY_ELIGIBLE not FULLY |
| AMBIGUITY-005 | YES | Migrant + inactive LPG → surfaced in output |
| AMBIGUITY-006 | YES | Remarried widow → UNCERTAIN not INELIGIBLE |
| AMBIGUITY-011 | YES | Household ITR ambiguity → UNCERTAIN |
| AMBIGUITY-013 | YES | Peri-urban MGNREGA → UNCERTAIN |
| AMBIGUITY-015 | YES | Unmarried mother PMMVY → LIKELY not UNCERTAIN |
| AMBIGUITY-016 | YES | Tenant farmer KCC → ALMOST_ELIGIBLE |
| AMBIGUITY-007 | Informational | Kutcha definition noted |
| AMBIGUITY-008 | Informational | 100-day household definition noted |
| AMBIGUITY-009 | No | Age boundary is clear |
| AMBIGUITY-010 | Informational | Pre-2014 account noted |
| AMBIGUITY-012 | No | Guardian=True is sufficient |
| AMBIGUITY-014 | Informational | Sub-scheme deferred to CSC |
| AMBIGUITY-017 | No | NPS exclusion is clear |
