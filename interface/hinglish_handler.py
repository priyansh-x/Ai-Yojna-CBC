"""
interface/hinglish_handler.py

Uses the Claude API to extract structured profile fields from free-form
Hinglish (Hindi + English mix) user input.

Design contract:
  - NEVER guess or infer a field that was not mentioned.
  - Return null for any field not explicitly stated or clearly implied.
  - Handles Devanagari, Latin-script Hindi, English, and mixed Hinglish.
  - The extracted dict is merged into the running profile dict by the CLI.

Anti-hallucination rules baked into the extraction prompt:
  1. "If the user did not mention it, return null."
  2. "Do not infer income from occupation."
  3. "Do not infer land ownership from being a farmer."
  4. "Do not infer caste from state or name."
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional


# ── Field definitions ─────────────────────────────────────────────────────────

# Every extractable field with its type hint and valid values
EXTRACTABLE_FIELDS = {
    "age": "integer (years)",
    "gender": "string: 'male' | 'female' | 'other'",
    "state": "string: 2-letter Indian state code (e.g. 'UP', 'MP', 'MH', 'RJ', 'BR', 'HR', 'PB', 'GJ', 'WB', 'OR', 'TN', 'AP', 'TS', 'KL', 'KA', 'AS', 'JH', 'CG', 'HP', 'UK', 'DL', 'GA')",
    "residence_type": "string: 'rural' | 'urban' | 'peri-urban'",
    "caste_category": "string: 'GEN' | 'OBC' | 'SC' | 'ST'",
    "annual_income_household": "integer (INR per year for entire household)",
    "monthly_income": "integer (INR per month — personal income)",
    "occupation": "string: 'farmer' | 'cultivator' | 'agricultural_labourer' | 'sharecropper' | 'tenant_farmer' | 'unorganised_worker' | 'salaried' | 'business' | 'unemployed' | 'homemaker' | 'student' | 'gig_worker'",
    "land_ownership": "boolean: true if land is in user's name",
    "land_type": "string: 'owned' | 'leased' | 'sharecrop' | null",
    "land_area_hectares": "float (hectares)",
    "family_size": "integer (total household members)",
    "has_bank_account": "boolean",
    "has_pmjdy_account": "boolean: true if specifically a PMJDY/Jan Dhan account",
    "bank_account_aadhaar_linked": "boolean",
    "ration_card_type": "string: 'AAY' | 'PHH' | null (null if no ration card or unknown)",
    "is_income_tax_payer": "boolean: true if user or immediate family member files ITR",
    "has_lpg_connection": "boolean",
    "marital_status": "string: 'single' | 'married' | 'widowed' | 'divorced' | 'remarried'",
    "previous_spouse_deceased": "boolean: true if previously widowed",
    "is_pregnant": "boolean",
    "is_first_living_child": "boolean: true if this is the first living child",
    "number_of_daughters": "integer",
    "girl_child_age_at_opening": "integer (youngest daughter's age, if relevant for SSY)",
    "house_type": "string: 'pucca' | 'semi-pucca' | 'kutcha' | 'houseless'",
    "disability": "boolean",
    "disability_percentage": "integer (0-100)",
    "secc_listed": "boolean: true if listed in SECC 2011 — only set if user explicitly knows",
    "is_epfo_member": "boolean",
    "is_esic_member": "boolean",
    "is_nps_member": "boolean",
    "is_nps_subscriber": "boolean",
    "is_central_state_govt_employee": "boolean",
    "is_current_former_government_employee": "boolean",
    "is_institutional_land_holder": "boolean",
    "is_constitutional_post_holder": "boolean",
    "is_pension_recipient_above_10k": "boolean",
    "is_doctor_lawyer_engineer_ca": "boolean",
    "sector_type": "string: 'organised' | 'unorganised'",
    "has_vehicle_4_wheeler": "boolean",
    "has_motorised_vehicle": "boolean",
    "has_refrigerator": "boolean",
    "any_member_earns_over_10k_month": "boolean",
    "household_member_files_itr": "boolean",
    "nationality": "string: always 'indian' if person is in India",
    "grows_notified_crop": "boolean",
    "has_kcc_crop_loan": "boolean",
    "is_wilful_defaulter": "boolean",
    "business_type": "string: 'manufacturing' | 'trading' | 'services' | 'allied_agricultural_activities' | null",
    "loan_amount_required": "integer (INR)",
    "self_declaration_poor": "boolean",
    "is_pmay_g_beneficiary": "boolean",
    "fra_title_pending": "boolean: true if Forest Rights Act title is pending",
    "urban_occupation_category": "string: one of SECC urban categories if applicable",
}


# ── System prompt for extraction ──────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are a field extractor for an Indian government welfare scheme eligibility system.

Your job: Extract structured profile fields from the user's message. The user may write in Hindi, English, or Hinglish (a mix of Hindi and English using Latin or Devanagari script).

STRICT RULES — follow these exactly:
1. ONLY extract fields that the user explicitly mentioned or clearly stated.
2. If a field was NOT mentioned, return null for it. Never guess.
3. Do NOT infer income from occupation (a farmer's income varies enormously).
4. Do NOT infer land ownership from being a farmer (they may be a labourer or tenant).
5. Do NOT infer caste from name, state, or occupation.
6. Do NOT infer bank account status from anything except explicit mention.
7. If the user says something ambiguous, return null rather than guessing.
8. "Gaon mein rehta hoon" = rural. "Shehar mein" = urban.
9. "Kisan hoon" = occupation: farmer. But does NOT imply land_ownership=true.
10. "2 acre zameen hai mere naam pe" = land_ownership: true, land_area_hectares: 0.8 (approx).
11. Acre to hectare: 1 acre ≈ 0.4 hectares. Convert automatically.
12. "BPL card hai" = ration_card_type: "PHH" (most BPL cards are PHH; AAY is specifically "antyodaya").
13. "Jan Dhan account" or "zero balance account" = has_pmjdy_account: true, has_bank_account: true.
14. "Aadhaar linked hai" = bank_account_aadhaar_linked: true.
15. "Pension nahi milti" does NOT mean they are ineligible — it means they don't currently receive it.
16. Age expressions: "pachpan saal" = 55 years. "40 ke aaspaas" = age: 40 (approximate).
17. nationality: always set to "indian" if the conversation is clearly about an Indian citizen.

Return ONLY a valid JSON object with the extracted fields. Omit fields entirely if null — do not include them with null values. Do not include explanations, just the JSON."""


# ── Extractor ─────────────────────────────────────────────────────────────────

def extract_fields_from_text(
    user_text: str,
    conversation_history: list[dict],
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """
    Extract structured profile fields from Hinglish user text.

    Args:
        user_text: The user's message (Hindi/English/Hinglish)
        conversation_history: Prior turns [{"role": "user"|"assistant", "content": str}]
        api_key: Google Gemini API key (falls back to GEMINI_API_KEY env var)

    Returns:
        Dict of extracted fields (only fields that were mentioned).
        Missing fields are absent (not None) — caller merges with running profile.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY", "")

    if not key:
        # Graceful fallback — regex demo extractor (no API key required)
        return _demo_extract(user_text)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        # Build the message with context from conversation history
        context_summary = ""
        if conversation_history:
            recent = conversation_history[-4:]  # Last 4 turns for context
            context_summary = "\n".join(
                f"[{t['role'].upper()}]: {t['content']}" for t in recent
            )
            context_summary = f"\n\nPrevious conversation:\n{context_summary}\n\n"

        user_message = f"""{context_summary}Current user message to extract from:
\"{user_text}\"

Extract fields from this message only (not from previous turns — those are already captured).
Return a JSON object. Omit fields not mentioned in the current message."""

        import time

        # gemini-2.5-flash is the model available on this key (confirmed via ListModels)
        MODEL = "gemini-2.5-flash"

        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=EXTRACTION_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        max_output_tokens=512,
                        temperature=0.0,
                    ),
                )
                raw = response.text.strip()
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
                extracted = json.loads(raw)
                return _validate_extracted(extracted)

            except Exception as e:
                err_str = str(e)
                if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < 2:
                    time.sleep(7)
                    continue
                raise

    except Exception as e:
        # Never crash the CLI due to extraction failure — return empty
        return {"_extraction_error": str(e)}


def _validate_extracted(data: dict) -> dict:
    """
    Validate and clean extracted data.
    Remove keys not in our known field list. Coerce types where possible.
    """
    valid = {}
    for key, value in data.items():
        if key.startswith("_"):
            valid[key] = value
            continue
        if key not in EXTRACTABLE_FIELDS:
            continue  # Unknown field — discard
        if value is None:
            continue  # Don't include null values
        valid[key] = _coerce(key, value)
    return valid


def _coerce(field: str, value: Any) -> Any:
    """Type coercion for common extraction artifacts."""
    # Boolean coercion
    if field in {
        "land_ownership", "has_bank_account", "has_pmjdy_account",
        "bank_account_aadhaar_linked", "is_income_tax_payer", "has_lpg_connection",
        "is_pregnant", "is_first_living_child", "disability", "secc_listed",
        "is_epfo_member", "is_esic_member", "is_nps_member", "is_nps_subscriber",
        "is_central_state_govt_employee", "is_current_former_government_employee",
        "household_member_files_itr", "is_wilful_defaulter", "has_kcc_crop_loan",
        "has_motorised_vehicle", "has_vehicle_4_wheeler", "has_refrigerator",
        "any_member_earns_over_10k_month", "self_declaration_poor",
        "is_doctor_lawyer_engineer_ca", "is_institutional_land_holder",
        "is_constitutional_post_holder", "is_pension_recipient_above_10k",
        "previous_spouse_deceased", "fra_title_pending", "grows_notified_crop",
        "is_pmay_g_beneficiary",
    }:
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "haan", "ha", "1")
        return bool(value)

    # Integer coercion
    if field in {"age", "family_size", "disability_percentage", "number_of_daughters",
                 "girl_child_age_at_opening", "annual_income_household", "monthly_income",
                 "loan_amount_required"}:
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return value

    # Float coercion
    if field in {"land_area_hectares"}:
        try:
            return float(str(value))
        except (ValueError, TypeError):
            return value

    return value


# ── Demo mode (no API key) ────────────────────────────────────────────────────

def _demo_extract(text: str) -> dict:
    """
    Regex-based fallback extractor for demo mode (no API key).
    Only captures the most common patterns — not for production use.
    """
    text_lower = text.lower()
    fields = {}

    # Age
    age_match = re.search(r"(\d{1,3})\s*(?:saal|sal|year|years|varsh|वर्ष)", text_lower)
    if age_match:
        fields["age"] = int(age_match.group(1))

    # Nationality default
    fields["nationality"] = "indian"

    # Gender
    if any(w in text_lower for w in ["main ek aurat", "main mahila", "woman", "female", "mai ek aurat"]):
        fields["gender"] = "female"
    elif any(w in text_lower for w in ["main ek aadmi", "man", "male", "mard"]):
        fields["gender"] = "male"

    # Residence
    if any(w in text_lower for w in ["gaon", "gram", "village", "rural", "gramin"]):
        fields["residence_type"] = "rural"
    elif any(w in text_lower for w in ["shehar", "city", "urban", "nagar"]):
        fields["residence_type"] = "urban"

    # Occupation
    if any(w in text_lower for w in ["kisan", "farmer", "kheti", "kisaan", "fasal"]):
        fields["occupation"] = "farmer"
    elif any(w in text_lower for w in ["mazdoor", "labourer", "labor", "daily wage"]):
        fields["occupation"] = "agricultural_labourer"
    elif any(w in text_lower for w in ["naukri", "job", "salaried", "employee"]):
        fields["occupation"] = "salaried"

    # Land
    if re.search(r"zameen.*mere naam|land.*my name|meri zameen", text_lower):
        fields["land_ownership"] = True
        fields["land_type"] = "owned"
    acre_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:acre|एकड़)", text_lower)
    if acre_m:
        fields["land_area_hectares"] = round(float(acre_m.group(1)) * 0.4047, 2)

    # Bank account
    if any(w in text_lower for w in ["jan dhan", "jandhan", "zero balance", "bank account hai"]):
        fields["has_bank_account"] = True
    if any(w in text_lower for w in ["bank account nahi", "no bank", "account nahi"]):
        fields["has_bank_account"] = False

    # Ration card
    if "aay" in text_lower or "antyodaya" in text_lower:
        fields["ration_card_type"] = "AAY"
    elif any(w in text_lower for w in ["phh", "bpl", "ration card hai"]):
        fields["ration_card_type"] = "PHH"

    # Income
    income_match = re.search(r"(\d+)\s*(?:lakh|lac|लाख)\s*(?:per year|saal|annual)?", text_lower)
    if income_match:
        fields["annual_income_household"] = int(income_match.group(1)) * 100000
    thousand_match = re.search(r"(\d+)\s*(?:hazaar|hazar|thousand|हज़ार)\s*(?:per month|mahine)", text_lower)
    if thousand_match:
        fields["monthly_income"] = int(thousand_match.group(1)) * 1000

    # LPG
    if any(w in text_lower for w in ["gas connection nahi", "lpg nahi", "chulha", "no gas"]):
        fields["has_lpg_connection"] = False
    elif any(w in text_lower for w in ["gas connection hai", "lpg hai"]):
        fields["has_lpg_connection"] = True

    # Marital status
    if any(w in text_lower for w in ["vidhwa", "widow", "pati ki maut", "husband died", "pati guzar"]):
        fields["marital_status"] = "widowed"
        fields["previous_spouse_deceased"] = True
    elif any(w in text_lower for w in ["shaadi", "married", "vivahit", "wife", "husband"]):
        fields["marital_status"] = "married"

    # Pregnancy
    if any(w in text_lower for w in ["pregnant", "garbhvati", "pregnancy", "bache wali"]):
        fields["is_pregnant"] = True

    # Caste
    if any(w in text_lower for w in [" sc ", "scheduled caste", "dalit"]):
        fields["caste_category"] = "SC"
    elif any(w in text_lower for w in [" st ", "scheduled tribe", "adivasi", "tribal"]):
        fields["caste_category"] = "ST"
    elif any(w in text_lower for w in ["obc", "other backward"]):
        fields["caste_category"] = "OBC"

    return fields
