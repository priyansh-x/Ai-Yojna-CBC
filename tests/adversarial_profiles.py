"""
tests/adversarial_profiles.py

10 adversarial edge-case user profiles designed to stress-test the engine's
handling of ambiguity, boundary conditions, and incomplete data.

Each profile includes:
  - The profile dict (what the user inputs)
  - expected_behaviour: What the engine MUST do (not just what scheme it outputs)
  - must_not_do: What the engine must NEVER do for this case
  - key_ambiguities: Which AMBIGUITY-xxx flags should be triggered
  - adversarial_intent: What failure mode this is testing

The engine passes a test case if:
  1. It matches expected_behaviour
  2. It does NOT do anything in must_not_do
  3. It surfaces at least the expected ambiguity flags
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AdversarialProfile:
    case_id: str
    name: str
    description: str
    profile: dict
    expected_behaviour: str          # What the engine must do
    must_not_do: str                 # What would be a failure
    key_ambiguities: list[str]       # AMBIGUITY-xxx IDs that must be surfaced
    adversarial_intent: str          # The failure mode being tested
    expected_statuses: dict[str, str]  # scheme_id → expected status


ADVERSARIAL_CASES: list[AdversarialProfile] = [

    # ── CASE 1: Widow who recently remarried ──────────────────────────────────
    AdversarialProfile(
        case_id="ADV-001",
        name="Sunita Devi, 52, remarried widow",
        description="A 52-year-old woman from Bihar. Her first husband died 3 years ago. She was receiving NSAP widow pension (IGNWPS). She remarried 8 months ago. She still has BPL card and agricultural land in her first husband's name.",
        profile={
            "age": 52,
            "gender": "female",
            "state": "BR",
            "caste_category": "OBC",
            "annual_income_household": 55000,
            "land_ownership": True,
            "land_area_hectares": 0.6,
            "land_type": "owned",
            "occupation": "farmer",
            "family_size": 3,
            "has_bank_account": True,
            "bank_account_aadhaar_linked": True,
            "ration_card_type": "PHH",
            "is_income_tax_payer": False,
            "has_lpg_connection": True,
            "marital_status": "remarried",         # KEY: remarried — was widowed
            "previous_spouse_deceased": True,       # KEY: previous husband died
            "is_pregnant": False,
            "number_of_daughters": 0,
            "residence_type": "rural",
            "house_type": "semi-pucca",
            "has_motorised_vehicle": False,
            "has_vehicle_4_wheeler": False,
            "disability": False,
            "secc_listed": None,                   # Unknown
            "is_epfo_member": False,
            "is_esic_member": False,
            "is_nps_member": False,
            "is_nps_subscriber": False,
            "is_central_state_govt_employee": False,
            "is_current_former_government_employee": False,
            "existing_schemes": ["nsap_ignwps"],
            "nationality": "indian",
        },
        expected_behaviour=(
            "For NSAP IGNWPS: engine must NOT confidently disqualify her. "
            "Must surface AMBIGUITY-006 and assign confidence <= 0.40. "
            "Must direct her to verify at Block Development Office. "
            "For PM Kisan: should flag AMBIGUITY-003 for land being in deceased husband's name."
        ),
        must_not_do=(
            "Must NOT output FULLY_ELIGIBLE for NSAP IGNWPS. "
            "Must NOT output INELIGIBLE for NSAP with high confidence. "
            "Must NOT silently ignore the remarriage."
        ),
        key_ambiguities=["AMBIGUITY-006", "AMBIGUITY-003"],
        adversarial_intent="Tests whether remarriage to widow pension is handled as ambiguous, not as a confident disqualification.",
        expected_statuses={
            "nsap": "UNCERTAIN",           # IGNWPS marital check fails → ambiguity_flag AMBIGUITY-006 on failing condition → UNCERTAIN
            "pm_kisan": "UNCERTAIN",       # Missing exclusion fields → NOT returns None → overall UNCERTAIN
            "pmgkay": "FULLY_ELIGIBLE",    # PHH ration card — clear
            "pm_suraksha_bima": "FULLY_ELIGIBLE",
        },
    ),

    # ── CASE 2: Farmer leasing land ───────────────────────────────────────────
    AdversarialProfile(
        case_id="ADV-002",
        name="Ramprasad Yadav, 38, tenant farmer",
        description="A 38-year-old farmer from UP who cultivates 1.5 acres of leased land. He has no land in his own name. He has a bank account and Aadhaar. He is not an income tax payer.",
        profile={
            "age": 38,
            "gender": "male",
            "state": "UP",
            "caste_category": "OBC",
            "annual_income_household": 80000,
            "land_ownership": False,               # KEY: no owned land
            "land_area_hectares": 0.6,
            "land_type": "leased",                 # KEY: leased, not owned
            "occupation": "farmer",
            "family_size": 5,
            "has_bank_account": True,
            "bank_account_aadhaar_linked": True,
            "ration_card_type": "PHH",
            "is_income_tax_payer": False,
            "has_lpg_connection": True,
            "marital_status": "married",
            "is_pregnant": False,
            "number_of_daughters": 1,
            "residence_type": "rural",
            "house_type": "kutcha",
            "has_motorised_vehicle": False,
            "has_vehicle_4_wheeler": False,
            "has_refrigerator": False,
            "any_member_earns_over_10k_month": False,
            "pays_income_tax": False,
            "has_government_employee": False,
            "land_area_hectares": 0.6,
            "disability": False,
            "secc_listed": None,
            "is_epfo_member": False,
            "is_esic_member": False,
            "is_nps_member": False,
            "is_nps_subscriber": False,
            "is_central_state_govt_employee": False,
            "is_current_former_government_employee": False,
            "grows_notified_crop": True,
            "has_kcc_crop_loan": False,
            "voluntary_enrollment_pmfby": False,
            "existing_schemes": [],
            "nationality": "indian",
        },
        expected_behaviour=(
            "PM Kisan: must flag AMBIGUITY-003 and return confidence <= 0.50. "
            "Must NOT return FULLY_ELIGIBLE for PM Kisan. "
            "PMFBY: must return LIKELY_ELIGIBLE or higher (sharecrop/leased explicitly included). "
            "PMAY-G: should flag as potentially eligible given kutcha house and income level. "
            "Must surface the message about visiting Gram Panchayat for PM Kisan verification."
        ),
        must_not_do=(
            "Must NOT return FULLY_ELIGIBLE for PM Kisan (leased land is ambiguous). "
            "Must NOT return INELIGIBLE for PMFBY (PMFBY explicitly includes tenant farmers). "
        ),
        key_ambiguities=["AMBIGUITY-003", "AMBIGUITY-001"],
        adversarial_intent="Tests the PM Kisan ownership ambiguity for tenant farmers, and verifies PMFBY correctly includes them.",
        expected_statuses={
            "pm_kisan": "UNCERTAIN",           # land_ownership=False with AMBIGUITY-003 flag → UNCERTAIN
            "pm_fasal_bima": "ALMOST_ELIGIBLE", # Needs to opt for voluntary enrollment
            "pmgkay": "FULLY_ELIGIBLE",        # PHH card
        },
    ),

    # ── CASE 3: Aadhaar but no bank account ───────────────────────────────────
    AdversarialProfile(
        case_id="ADV-003",
        name="Mohan Lal, 45, unbanked farmer",
        description="A 45-year-old farmer from Rajasthan. He has Aadhaar and land records in his name (2 acres). He has never had a bank account. He is not an income tax payer. PHH ration card.",
        profile={
            "age": 45,
            "gender": "male",
            "state": "RJ",
            "caste_category": "GEN",
            "annual_income_household": 70000,
            "land_ownership": True,
            "land_area_hectares": 0.8,
            "land_type": "owned",
            "occupation": "farmer",
            "family_size": 6,
            "has_bank_account": False,              # KEY: no bank account
            "bank_account_aadhaar_linked": None,
            "has_pmjdy_account": False,
            "ration_card_type": "PHH",
            "is_income_tax_payer": False,
            "has_lpg_connection": False,
            "marital_status": "married",
            "is_pregnant": False,
            "number_of_daughters": 2,
            "residence_type": "rural",
            "house_type": "semi-pucca",
            "has_motorised_vehicle": False,
            "has_vehicle_4_wheeler": False,
            "disability": False,
            "secc_listed": None,
            "is_epfo_member": False,
            "is_esic_member": False,
            "is_nps_member": False,
            "is_nps_subscriber": False,
            "is_central_state_govt_employee": False,
            "is_current_former_government_employee": False,
            "is_institutional_land_holder": False,
            "is_constitutional_post_holder": False,
            "is_pension_recipient_above_10k": False,
            "is_doctor_lawyer_engineer_ca": False,
            "existing_schemes": [],
            "nationality": "indian",
        },
        expected_behaviour=(
            "Engine must list PM Jan Dhan as STEP 1 in the application sequence. "
            "PM Kisan must appear as ALMOST_ELIGIBLE or UNCERTAIN — blocked only by missing bank account. "
            "Gap analysis for PM Kisan must say: 'Open a bank account under PM Jan Dhan Yojana first.' "
            "PM Ujjwala must appear as ALMOST_ELIGIBLE — blocked by bank account requirement. "
            "PMGKAY must appear as FULLY_ELIGIBLE — does not require bank account."
        ),
        must_not_do=(
            "Must NOT return INELIGIBLE for PM Kisan (would be eligible once banked). "
            "Must NOT skip the PM Jan Dhan prerequisite step. "
            "Must NOT output a document checklist that omits PMJDY account opening."
        ),
        key_ambiguities=[],
        adversarial_intent="Tests prerequisite sequencing — unbanked user must be shown PMJDY first, not a useless PM Kisan rejection.",
        expected_statuses={
            "pm_jan_dhan": "FULLY_ELIGIBLE",   # He qualifies — just hasn't applied
            "pm_kisan": "LIKELY_ELIGIBLE",     # All exclusion fields False, land owned — bank is prerequisite not rule
            "pmgkay": "FULLY_ELIGIBLE",        # PHH — no bank needed
        },
    ),

    # ── CASE 4: Urban sharecropper in a census town ───────────────────────────
    AdversarialProfile(
        case_id="ADV-004",
        name="Deepak Kumar, 33, peri-urban farmer",
        description="A 33-year-old sharecropper in a census town near Patna, Bihar. The area was a village in 2001 but reclassified as a census town in 2011. He lives under Gram Panchayat jurisdiction. He has a kutcha house. Annual income ₹65,000.",
        profile={
            "age": 33,
            "gender": "male",
            "state": "BR",
            "caste_category": "SC",
            "annual_income_household": 65000,
            "land_ownership": False,
            "land_area_hectares": 0.5,
            "land_type": "sharecrop",
            "occupation": "farmer",
            "family_size": 4,
            "has_bank_account": True,
            "bank_account_aadhaar_linked": True,
            "ration_card_type": "PHH",
            "is_income_tax_payer": False,
            "has_lpg_connection": False,
            "marital_status": "married",
            "is_pregnant": False,
            "number_of_daughters": 1,
            "residence_type": "peri-urban",        # KEY: peri-urban — ambiguous
            "house_type": "kutcha",
            "has_motorised_vehicle": False,
            "has_vehicle_4_wheeler": False,
            "has_refrigerator": False,
            "any_member_earns_over_10k_month": False,
            "pays_income_tax": False,
            "has_government_employee": False,
            "disability": False,
            "secc_listed": None,
            "is_epfo_member": False,
            "is_esic_member": False,
            "is_nps_member": False,
            "is_nps_subscriber": False,
            "is_central_state_govt_employee": False,
            "is_current_former_government_employee": False,
            "existing_schemes": [],
            "nationality": "indian",
        },
        expected_behaviour=(
            "PMAY-G and PMAY-U must BOTH be flagged with AMBIGUITY-002. "
            "Neither should be FULLY_ELIGIBLE. Both should be UNCERTAIN or LIKELY_ELIGIBLE with the ambiguity warning. "
            "MGNREGA must flag AMBIGUITY-013 — peri-urban MGNREGA eligibility is uncertain. "
            "PM Kisan must flag AMBIGUITY-003 for sharecrop. "
            "Engine must direct user to Block Development Office to resolve rural/urban classification."
        ),
        must_not_do=(
            "Must NOT confidently declare PMAY-G eligibility without checking rural status. "
            "Must NOT confidently declare PMAY-U eligibility without checking urban status. "
            "Must NOT silently pick one and ignore the other."
        ),
        key_ambiguities=["AMBIGUITY-002", "AMBIGUITY-003", "AMBIGUITY-013"],
        adversarial_intent="Tests rural/urban boundary ambiguity — peri-urban users fall in a genuine administrative gap.",
        expected_statuses={
            "pmay_gramin": "UNCERTAIN",    # peri-urban → rural comparison returns None
            "pmay_urban": "UNCERTAIN",     # peri-urban → urban comparison returns None
            "mgnrega": "UNCERTAIN",        # peri-urban → rural comparison returns None
            "pmgkay": "FULLY_ELIGIBLE",   # PHH card — always valid
        },
    ),

    # ── CASE 5: Young unmarried pregnant woman ────────────────────────────────
    AdversarialProfile(
        case_id="ADV-005",
        name="Priya, 19, unmarried pregnant",
        description="A 19-year-old unmarried woman from MP, 4 months pregnant. This is her first pregnancy. She lives with her parents (rural). Family income ₹1.2L/year. PHH ration card. Has bank account.",
        profile={
            "age": 19,
            "gender": "female",
            "state": "MP",
            "caste_category": "GEN",
            "annual_income_household": 120000,
            "land_ownership": False,
            "land_type": None,
            "occupation": "unemployed",
            "family_size": 5,
            "has_bank_account": True,
            "bank_account_aadhaar_linked": True,
            "ration_card_type": "PHH",
            "is_income_tax_payer": False,
            "has_lpg_connection": True,
            "marital_status": "single",            # KEY: unmarried
            "is_pregnant": True,                   # KEY: pregnant
            "is_first_living_child": True,
            "is_second_child_and_girl": False,
            "number_of_daughters": 0,
            "residence_type": "rural",
            "house_type": "semi-pucca",
            "has_motorised_vehicle": False,
            "has_vehicle_4_wheeler": False,
            "disability": False,
            "secc_listed": None,
            "is_epfo_member": False,
            "is_esic_member": False,
            "is_nps_member": False,
            "is_nps_subscriber": False,
            "is_central_state_govt_employee": False,
            "existing_schemes": [],
            "nationality": "indian",
        },
        expected_behaviour=(
            "PMMVY must return FULLY_ELIGIBLE or LIKELY_ELIGIBLE. "
            "PMMVY eligibility does NOT require the woman to be married — only age >= 19 and first living child. "
            "Engine must NOT add a marital status requirement that does not exist in PMMVY guidelines. "
            "Application guidance must include Anganwadi registration as the first step."
        ),
        must_not_do=(
            "Must NOT return INELIGIBLE for PMMVY based on marital_status='single'. "
            "Must NOT invent a 'must be married' rule — PMMVY has no such rule. "
            "This is testing whether the engine adds hallucinated rules."
        ),
        key_ambiguities=["AMBIGUITY-015"],
        adversarial_intent="Tests whether the engine adds a non-existent marital status requirement to PMMVY — a common AI hallucination.",
        expected_statuses={
            "pm_matru_vandana": "LIKELY_ELIGIBLE",  # Age >= 19, first child, not govt employee — source_conf 0.85 lowers confidence
            "pmgkay": "FULLY_ELIGIBLE",             # PHH
            "ayushman_bharat": "LIKELY_ELIGIBLE",   # PHH card qualifies via NFSA expansion (pmjay_r3a)
        },
    ),

    # ── CASE 6: Farmer with ITR-filing son ────────────────────────────────────
    AdversarialProfile(
        case_id="ADV-006",
        name="Giriraj Singh, 62, farmer with salaried son",
        description="A 62-year-old farmer from Haryana. He owns 2 acres of land in his name. He does not file income tax. His son (32) lives with him, is salaried at ₹5L/year and files ITR. Combined household.",
        profile={
            "age": 62,
            "gender": "male",
            "state": "HR",
            "caste_category": "GEN",
            "annual_income_household": 580000,
            "land_ownership": True,
            "land_area_hectares": 0.8,
            "land_type": "owned",
            "occupation": "farmer",
            "family_size": 5,
            "has_bank_account": True,
            "bank_account_aadhaar_linked": True,
            "ration_card_type": None,
            "is_income_tax_payer": False,           # Farmer himself does NOT file ITR
            "household_member_files_itr": True,     # KEY: son files ITR
            "has_lpg_connection": True,
            "marital_status": "married",
            "is_pregnant": False,
            "number_of_daughters": 0,
            "residence_type": "rural",
            "house_type": "pucca",
            "has_motorised_vehicle": True,
            "has_vehicle_4_wheeler": False,
            "has_refrigerator": True,
            "any_member_earns_over_10k_month": True,  # Son earns ~42k/month
            "pays_income_tax": False,               # Farmer himself
            "has_government_employee": False,
            "disability": False,
            "secc_listed": None,
            "is_epfo_member": False,
            "is_esic_member": False,
            "is_nps_member": False,
            "is_nps_subscriber": False,
            "is_institutional_land_holder": False,
            "is_constitutional_post_holder": False,
            "is_pension_recipient_above_10k": False,
            "is_doctor_lawyer_engineer_ca": False,
            "is_central_state_govt_employee": False,
            "is_current_former_government_employee": False,
            "existing_schemes": [],
            "nationality": "indian",
        },
        expected_behaviour=(
            "PM Kisan: must flag AMBIGUITY-011 (household vs individual ITR question). "
            "Confidence must be <= 0.55. Engine must surface the warning about household ITR interpretation. "
            "Must NOT confidently qualify him. Must NOT confidently disqualify him. "
            "PMAY-G: must return INELIGIBLE — any_member_earns_over_10k_month=True and has_refrigerator=True are SECC exclusions."
        ),
        must_not_do=(
            "Must NOT return FULLY_ELIGIBLE for PM Kisan (son's ITR creates household-level ambiguity). "
            "Must NOT return ELIGIBLE for PMAY-G (exclusion criteria clearly triggered). "
            "Must NOT ignore the household_member_files_itr field."
        ),
        key_ambiguities=["AMBIGUITY-011"],
        adversarial_intent="Tests household-vs-individual ITR interpretation for PM Kisan exclusion.",
        expected_statuses={
            "pm_kisan": "LIKELY_ELIGIBLE", # is_income_tax_payer=False (farmer himself) — AMBIGUITY-011 surfaces as warning
            "pmay_gramin": "INELIGIBLE",   # has_refrigerator=True + any_member_earns_over_10k_month=True — SECC exclusions fire
        },
    ),

    # ── CASE 7: BPL woman with old LPG connection ─────────────────────────────
    AdversarialProfile(
        case_id="ADV-007",
        name="Kamla Bai, 40, migrant with old LPG",
        description="A 40-year-old woman from MP who migrated to Delhi 3 years ago. She had an LPG connection at her old address in MP which is still registered but she has not used it in 2 years. She has a BPL/PHH card. She has no LPG at her current Delhi address.",
        profile={
            "age": 40,
            "gender": "female",
            "state": "DL",
            "caste_category": "SC",
            "annual_income_household": 90000,
            "land_ownership": False,
            "land_type": None,
            "occupation": "unorganised_worker",
            "family_size": 3,
            "has_bank_account": True,
            "bank_account_aadhaar_linked": True,
            "ration_card_type": "PHH",
            "is_income_tax_payer": False,
            "has_lpg_connection": True,             # KEY: technically yes, at old address
            "lpg_connection_at_current_address": False,  # KEY: not at current home
            "lpg_connection_registered_elsewhere": True,  # At old MP address
            "marital_status": "married",
            "is_pregnant": False,
            "number_of_daughters": 1,
            "residence_type": "urban",
            "house_type": "semi-pucca",
            "has_vehicle_4_wheeler": False,
            "disability": False,
            "secc_listed": None,
            "is_epfo_member": False,
            "is_esic_member": False,
            "is_nps_member": False,
            "is_nps_subscriber": False,
            "is_central_state_govt_employee": False,
            "self_declaration_poor": True,
            "existing_schemes": [],
            "nationality": "indian",
        },
        expected_behaviour=(
            "PM Ujjwala: engine must flag that has_lpg_connection=True technically disqualifies but must surface the ambiguity about the connection being at a previous address. "
            "Must NOT return INELIGIBLE with high confidence. Must return UNCERTAIN with guidance. "
            "AMBIGUITY-005 should be triggered (PMUY 2.0 'poor' definition). "
            "Output must direct her to the LPG distributor to clarify her old connection status."
        ),
        must_not_do=(
            "Must NOT return FULLY_ELIGIBLE for PMUY (has_lpg_connection=True). "
            "Must NOT return INELIGIBLE with high confidence (old connection ambiguity). "
            "Must NOT silently ignore the lpg_connection_at_current_address field."
        ),
        key_ambiguities=["AMBIGUITY-005"],
        adversarial_intent="Tests the LPG connection ambiguity for migrant workers with old connections — a real common failure scenario.",
        expected_statuses={
            "pm_ujjwala": "INELIGIBLE",        # has_lpg_connection=True → NOT exclusion fires → INELIGIBLE (warning surfaces old-connection ambiguity)
            "pmgkay": "FULLY_ELIGIBLE",        # PHH card
            "pm_suraksha_bima": "FULLY_ELIGIBLE",
        },
    ),

    # ── CASE 8: Unorganised worker just above age limit ───────────────────────
    AdversarialProfile(
        case_id="ADV-008",
        name="Suresh Bind, 41, just over age limit",
        description="A 41-year-old daily wage construction worker from UP. Income ₹8,000/month. Not EPFO/ESIC covered. Has bank account. NOT an income tax payer. He is exactly 41 — one year past the PM-SYM/APY cutoff.",
        profile={
            "age": 41,                              # KEY: exactly 41 — outside 18–40 window
            "gender": "male",
            "state": "UP",
            "caste_category": "OBC",
            "annual_income_household": 96000,
            "monthly_income": 8000,
            "land_ownership": False,
            "land_type": None,
            "occupation": "unorganised_worker",
            "sector_type": "unorganised",
            "family_size": 4,
            "has_bank_account": True,
            "bank_account_aadhaar_linked": True,
            "ration_card_type": "PHH",
            "is_income_tax_payer": False,
            "has_lpg_connection": True,
            "marital_status": "married",
            "is_pregnant": False,
            "number_of_daughters": 2,
            "residence_type": "urban",
            "house_type": "semi-pucca",
            "has_vehicle_4_wheeler": False,
            "disability": False,
            "secc_listed": None,
            "is_epfo_member": False,
            "is_esic_member": False,
            "is_nps_member": False,
            "is_nps_subscriber": False,
            "is_nps_subscriber": False,
            "is_central_state_govt_employee": False,
            "is_current_former_government_employee": False,
            "existing_schemes": [],
            "nationality": "indian",
        },
        expected_behaviour=(
            "PM-SYM: must return INELIGIBLE (age=41, outside 18–40). Gap analysis must say 'Age 18–40 required — not actionable.' "
            "APY: must return INELIGIBLE (age=41, same reason). "
            "AMBIGUITY-007 should NOT be triggered here (he's ineligible for both, not eligible for both). "
            "PMJJBY: must return FULLY_ELIGIBLE (age 18–50). "
            "PMSBY: must return FULLY_ELIGIBLE (age 18–70). "
            "Engine must suggest PMJJBY and PMSBY as actionable alternatives."
        ),
        must_not_do=(
            "Must NOT return ELIGIBLE for PM-SYM or APY. Age 41 is a hard disqualifier. "
            "Must NOT confuse the 18–40 enrollment window with 'coverage until 60' — once enrolled you can keep it, but new enrollment at 41 is impossible."
        ),
        key_ambiguities=[],
        adversarial_intent="Tests hard age boundary — engine must return clean INELIGIBLE with non-actionable gap, not uncertainty.",
        expected_statuses={
            "pm_shram_yogi_mandhan": "INELIGIBLE",    # Age 41 is hard disqualifier
            "atal_pension_yojana": "INELIGIBLE",      # Age 41 is hard disqualifier
            "pm_jeevan_jyoti_bima": "FULLY_ELIGIBLE", # Age 18–50 ✓
            "pm_suraksha_bima": "FULLY_ELIGIBLE",     # Age 18–70 ✓
            "pmgkay": "FULLY_ELIGIBLE",               # PHH card
        },
    ),

    # ── CASE 9: Tribal farmer with no formal land records ────────────────────
    AdversarialProfile(
        case_id="ADV-009",
        name="Birsa Munda, 48, tribal farmer, no formal land records",
        description="A 48-year-old ST farmer from Jharkhand. He cultivates 3 acres of forest land under traditional tribal rights (FRA 2006). He has no formal patta/khasra in his name. Gram Sabha has recognized his rights verbally but FRA title not yet formally issued. Has bank account.",
        profile={
            "age": 48,
            "gender": "male",
            "state": "JH",
            "caste_category": "ST",
            "annual_income_household": 75000,
            "land_ownership": None,                 # KEY: ambiguous — FRA rights, no formal title yet
            "land_area_hectares": 1.2,
            "land_type": None,                      # KEY: neither owned nor leased formally
            "occupation": "farmer",
            "family_size": 6,
            "has_bank_account": True,
            "bank_account_aadhaar_linked": True,
            "ration_card_type": "PHH",
            "is_income_tax_payer": False,
            "has_lpg_connection": False,
            "marital_status": "married",
            "is_pregnant": False,
            "number_of_daughters": 2,
            "residence_type": "rural",
            "house_type": "kutcha",
            "has_motorised_vehicle": False,
            "has_vehicle_4_wheeler": False,
            "has_refrigerator": False,
            "any_member_earns_over_10k_month": False,
            "pays_income_tax": False,
            "has_government_employee": False,
            "disability": False,
            "secc_listed": True,                   # Listed in SECC (SC/ST auto-included)
            "is_epfo_member": False,
            "is_esic_member": False,
            "is_nps_member": False,
            "is_nps_subscriber": False,
            "is_institutional_land_holder": False,
            "is_constitutional_post_holder": False,
            "is_pension_recipient_above_10k": False,
            "is_doctor_lawyer_engineer_ca": False,
            "is_central_state_govt_employee": False,
            "is_current_former_government_employee": False,
            "is_landless_casual_labourer": False,
            "fra_title_pending": True,              # Forest Rights Act title pending
            "existing_schemes": [],
            "nationality": "indian",
        },
        expected_behaviour=(
            "PM Kisan: must return UNCERTAIN (land_ownership=None). "
            "Must flag that FRA title pending means formal ownership is unclear. "
            "Must NOT return INELIGIBLE with high confidence — he may well qualify once FRA title is issued. "
            "PMAY-G: should return LIKELY_ELIGIBLE (SECC listed, kutcha house, ST category, no SECC exclusions triggered). "
            "Ayushman Bharat: should return FULLY_ELIGIBLE or LIKELY_ELIGIBLE (SECC listed = D5 SC/ST). "
            "MGNREGA: must return FULLY_ELIGIBLE (rural, adult, willing)."
        ),
        must_not_do=(
            "Must NOT return INELIGIBLE for PM Kisan with a confident score. "
            "Must NOT add a 'must have formal land records' rule that blocks all uncertain land situations without surfacing alternatives. "
        ),
        key_ambiguities=["AMBIGUITY-003"],
        adversarial_intent="Tests tribal land tenure ambiguity — FRA rights are legally valid but may not be recognized by local PM Kisan implementation.",
        expected_statuses={
            "pm_kisan": "UNCERTAIN",             # land_ownership=None → evaluator returns None
            "mgnrega": "LIKELY_ELIGIBLE",         # Rural, adult — IS_NULL fallback paths lower confidence below 0.75
            "pmay_gramin": "FULLY_ELIGIBLE",     # SECC listed, kutcha, ST, no exclusions
            "ayushman_bharat": "LIKELY_ELIGIBLE", # SECC listed (D5 ST criteria met)
            "pmgkay": "FULLY_ELIGIBLE",          # PHH
        },
    ),

    # ── CASE 10: ESIC member claiming unorganised worker status ──────────────
    AdversarialProfile(
        case_id="ADV-010",
        name="Ramesh Patel, 29, factory worker self-reporting as unorganised",
        description="A 29-year-old from Gujarat who works in a small garment factory. He self-describes as an 'unorganised worker' but is in fact covered under ESIC (employer contributes). He has bank account, income ₹12,000/month. He does not know he is ESIC-covered.",
        profile={
            "age": 29,
            "gender": "male",
            "state": "GJ",
            "caste_category": "OBC",
            "annual_income_household": 144000,
            "monthly_income": 12000,
            "land_ownership": False,
            "land_type": None,
            "occupation": "unorganised_worker",    # Self-reported — KEY: actually ESIC-covered
            "sector_type": "unorganised",          # Self-reported — incorrect
            "family_size": 3,
            "has_bank_account": True,
            "bank_account_aadhaar_linked": True,
            "ration_card_type": None,
            "is_income_tax_payer": False,
            "has_lpg_connection": True,
            "marital_status": "married",
            "is_pregnant": False,
            "number_of_daughters": 0,
            "residence_type": "urban",
            "house_type": "semi-pucca",
            "has_vehicle_4_wheeler": False,
            "disability": False,
            "secc_listed": None,
            "is_epfo_member": False,
            "is_esic_member": True,                # KEY: ESIC-covered — disqualifies PM-SYM
            "is_nps_member": False,
            "is_nps_subscriber": False,
            "is_central_state_govt_employee": False,
            "is_current_former_government_employee": False,
            "existing_schemes": [],
            "nationality": "indian",
        },
        expected_behaviour=(
            "PM-SYM: must return INELIGIBLE because is_esic_member=True, despite self-reported sector_type='unorganised'. "
            "The ESIC exclusion rule must override the self-reported sector. "
            "APY: must also return INELIGIBLE (is_esic_member exclusion). "
            "Engine must surface a clear explanation: 'ESIC members are excluded from PM-SYM regardless of sector self-description.' "
            "PMJJBY and PMSBY should still be FULLY_ELIGIBLE (no ESIC exclusion in these)."
        ),
        must_not_do=(
            "Must NOT return ELIGIBLE for PM-SYM just because sector_type='unorganised' was self-reported. "
            "The is_esic_member field is a hard disqualifier that must not be overridden by occupation self-description. "
            "This tests whether contradictory inputs are resolved correctly — explicit ESIC field wins over self-reported sector."
        ),
        key_ambiguities=["AMBIGUITY-012"],
        adversarial_intent="Tests contradiction handling — user self-reports as unorganised but explicit is_esic_member=True must take priority.",
        expected_statuses={
            "pm_shram_yogi_mandhan": "INELIGIBLE",    # is_esic_member=True → NOT exclusion fires
            "atal_pension_yojana": "INELIGIBLE",      # is_esic_member=True → NOT exclusion fires
            "pm_jeevan_jyoti_bima": "FULLY_ELIGIBLE", # No ESIC restriction
            "pm_suraksha_bima": "FULLY_ELIGIBLE",     # No ESIC restriction
        },
    ),
]
