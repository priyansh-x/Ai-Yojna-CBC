"""
interface/question_generator.py

Generates intelligent follow-up questions based on which profile fields
are still missing and which schemes are potentially relevant.

Logic:
  1. Run a quick partial match to see which schemes are potentially in play
  2. Identify which missing fields would most change the outcome
  3. Ask about those fields first — high-impact questions before low-impact ones
  4. Questions are in Hinglish — natural, conversational, not bureaucratic

Never asks about a field that:
  - Is already answered in the profile
  - Cannot affect any remaining uncertain scheme
  - Is obviously inapplicable given what we know (e.g., asking about daughters to a 70-year-old man)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Question:
    field: str                   # Profile field this question fills
    text_hinglish: str           # The question text (Hinglish)
    text_english: str            # English fallback
    expected_type: str           # "yes_no" | "number" | "choice" | "text"
    choices: Optional[list[str]] # For "choice" type
    impact_score: int            # 1–10: how many schemes this unlocks
    skip_if: dict                # Skip this question if these profile conditions are met


# ── Question bank ─────────────────────────────────────────────────────────────

ALL_QUESTIONS: list[Question] = [

    # ── Tier 1: Foundational (unlocks many schemes) ───────────────────────────

    Question(
        field="age",
        text_hinglish="Aapki umar kitni hai?",
        text_english="What is your age?",
        expected_type="number",
        choices=None,
        impact_score=10,
        skip_if={},
    ),
    Question(
        field="gender",
        text_hinglish="Aap mahila hain ya purush? (Are you female or male?)",
        text_english="What is your gender?",
        expected_type="choice",
        choices=["Mahila (Female)", "Purush (Male)", "Anya (Other)"],
        impact_score=9,
        skip_if={},
    ),
    Question(
        field="state",
        text_hinglish="Aap kis state mein rehte hain? (Which state do you live in?)",
        text_english="Which state do you live in?",
        expected_type="text",
        choices=None,
        impact_score=9,
        skip_if={},
    ),
    Question(
        field="residence_type",
        text_hinglish="Aap gaon mein rehte hain ya shehar mein? (Village or city?)",
        text_english="Do you live in a rural area (village) or urban area (city/town)?",
        expected_type="choice",
        choices=["Gaon (Rural)", "Shehar (Urban)", "Beech mein — census town ya outskirts (Peri-urban)"],
        impact_score=9,
        skip_if={},
    ),
    Question(
        field="occupation",
        text_hinglish="Aap kya kaam karte hain? (What is your main occupation?)",
        text_english="What is your main occupation?",
        expected_type="choice",
        choices=[
            "Kisan (Farmer — own/lease/sharecrop land)",
            "Khet mazdoor (Agricultural labourer — work on others' land)",
            "Asangathit kaamgaar (Unorganised worker — construction, domestic, etc.)",
            "Naukri (Salaried/Government employee)",
            "Vyavsay (Business owner)",
            "Ghar ka kaam (Homemaker)",
            "Berozgaar (Unemployed)",
        ],
        impact_score=9,
        skip_if={},
    ),
    Question(
        field="annual_income_household",
        text_hinglish="Aapke poore parivaar ki saal bhar ki kamai kitni hai? (Pura ghar milake) (Approximate annual household income?)",
        text_english="What is your approximate total household income per year (all members combined)?",
        expected_type="number",
        choices=None,
        impact_score=8,
        skip_if={},
    ),
    Question(
        field="caste_category",
        text_hinglish="Aap kaun si category mein aate hain? (General / OBC / SC / ST?)",
        text_english="What is your caste category?",
        expected_type="choice",
        choices=["General (Samanya)", "OBC (Pichhda Varg)", "SC (Anusuchit Jati)", "ST (Anusuchit Janjati)"],
        impact_score=7,
        skip_if={},
    ),
    Question(
        field="family_size",
        text_hinglish="Aapke ghar mein kitne log hain? (How many people in your household?)",
        text_english="How many people live in your household?",
        expected_type="number",
        choices=None,
        impact_score=6,
        skip_if={},
    ),

    # ── Tier 2: Banking & Documents ───────────────────────────────────────────

    Question(
        field="has_bank_account",
        text_hinglish="Kya aapka bank account hai? (Do you have a bank account?)",
        text_english="Do you have a bank account?",
        expected_type="yes_no",
        choices=None,
        impact_score=8,
        skip_if={},
    ),
    Question(
        field="bank_account_aadhaar_linked",
        text_hinglish="Kya aapka bank account Aadhaar se linked hai? (Is your bank account linked to Aadhaar?)",
        text_english="Is your bank account linked to your Aadhaar?",
        expected_type="yes_no",
        choices=None,
        impact_score=5,
        skip_if={"has_bank_account": False},
    ),
    Question(
        field="ration_card_type",
        text_hinglish="Kya aapke paas ration card hai? Kaun sa — BPL (PHH), Antyodaya (AAY), ya nahi hai?",
        text_english="Do you have a ration card? What type — BPL/PHH, Antyodaya (AAY), or none?",
        expected_type="choice",
        choices=["Antyodaya (AAY) — sabse gareeb", "BPL / PHH — priority household", "Ration card nahi hai"],
        impact_score=7,
        skip_if={},
    ),

    # ── Tier 3: Land & Farming ────────────────────────────────────────────────

    Question(
        field="land_ownership",
        text_hinglish="Kya aapke naam par koi zameen hai? (Do you own agricultural land in your name?)",
        text_english="Do you own agricultural land registered in your name?",
        expected_type="yes_no",
        choices=None,
        impact_score=8,
        skip_if={"occupation": "salaried"},
    ),
    Question(
        field="land_type",
        text_hinglish="Zameen ka kya haal hai — khud ki hai, leased hai, ya batai (sharecrop) par kaam karte hain?",
        text_english="Is the land you farm owned by you, leased, or under sharecrop arrangement?",
        expected_type="choice",
        choices=["Apni zameen (Owned)", "Leased / Kiraye par li hui", "Batai / Sharecrop"],
        impact_score=7,
        skip_if={"occupation": "salaried"},
    ),
    Question(
        field="land_area_hectares",
        text_hinglish="Kitni zameen hai? (Acres ya hectares mein bataiye)",
        text_english="How much land? (in acres or hectares)",
        expected_type="number",
        choices=None,
        impact_score=4,
        skip_if={"land_ownership": False},
    ),

    # ── Tier 4: Housing ────────────────────────────────────────────────────────

    Question(
        field="house_type",
        text_hinglish="Aapka ghar kaisa hai? (What kind of house do you have?)",
        text_english="What type of house do you live in?",
        expected_type="choice",
        choices=[
            "Pakka ghar (Pucca — concrete/brick)",
            "Adha pakka (Semi-pucca — mixed material)",
            "Kaccha ghar (Kutcha — mud/thatch)",
            "Ghar nahi hai (Houseless)",
        ],
        impact_score=6,
        skip_if={},
    ),

    # ── Tier 5: Family-specific ────────────────────────────────────────────────

    Question(
        field="marital_status",
        text_hinglish="Aapki vaivahik sthiti kya hai? (What is your marital status?)",
        text_english="What is your marital status?",
        expected_type="choice",
        choices=["Vivahit (Married)", "Kumari/Kumaara (Single)", "Vidhwa/Vidhur (Widowed)", "Punah Vivahit (Remarried)"],
        impact_score=5,
        skip_if={},
    ),
    Question(
        field="is_pregnant",
        text_hinglish="Kya aap abhi pregnant hain ya haaal hi mein maa bani hain?",
        text_english="Are you currently pregnant or a recent mother?",
        expected_type="yes_no",
        choices=None,
        impact_score=7,
        skip_if={"gender": "male"},  # Skip for males
    ),
    Question(
        field="number_of_daughters",
        text_hinglish="Aapki kitni betiyaan hain? (How many daughters do you have?)",
        text_english="How many daughters do you have?",
        expected_type="number",
        choices=None,
        impact_score=5,
        skip_if={"gender": "male"},
    ),
    Question(
        field="disability",
        text_hinglish="Kya aap ya aapke ghar mein koi viklang hain? (Any disability in the household?)",
        text_english="Do you or any household member have a disability?",
        expected_type="yes_no",
        choices=None,
        impact_score=5,
        skip_if={},
    ),

    # ── Tier 6: Employment & Social Security ──────────────────────────────────

    Question(
        field="is_income_tax_payer",
        text_hinglish="Kya aap ya aapke ghar ka koi sadasya income tax bharta hai? (ITR file karta hai?)",
        text_english="Does anyone in your household file income tax returns (ITR)?",
        expected_type="yes_no",
        choices=None,
        impact_score=6,
        skip_if={},
    ),
    Question(
        field="is_epfo_member",
        text_hinglish="Kya aap EPFO mein registered hain ya aapka PF kata hai? (Do you have Provident Fund deducted from salary?)",
        text_english="Are you an EPFO member / do you have PF deducted from your salary?",
        expected_type="yes_no",
        choices=None,
        impact_score=5,
        skip_if={"occupation": "farmer", "residence_type": "rural"},
    ),
    Question(
        field="is_esic_member",
        text_hinglish="Kya aapke paas ESIC card hai ya niyokta ESIC contribute karta hai?",
        text_english="Are you covered under ESIC (Employee State Insurance)?",
        expected_type="yes_no",
        choices=None,
        impact_score=5,
        skip_if={"occupation": "farmer", "residence_type": "rural"},
    ),
    Question(
        field="monthly_income",
        text_hinglish="Aapki khud ki mahine ki kamai kitni hai? (Your personal monthly income?)",
        text_english="What is your personal monthly income?",
        expected_type="number",
        choices=None,
        impact_score=6,
        skip_if={"occupation": "farmer"},  # Ask annual for farmers
    ),
    Question(
        field="has_lpg_connection",
        text_hinglish="Kya aapke ghar mein LPG gas connection hai? (Do you have an LPG cylinder connection?)",
        text_english="Do you have an LPG (cooking gas) connection at home?",
        expected_type="yes_no",
        choices=None,
        impact_score=6,
        skip_if={"gender": "male"},  # PM Ujjwala only for women
    ),
]


# ── Prioritization engine ─────────────────────────────────────────────────────

def get_next_questions(
    profile: dict,
    max_questions: int = 3,
    potentially_eligible_schemes: Optional[list[str]] = None,
) -> list[Question]:
    """
    Return the highest-impact unanswered questions.

    Args:
        profile: Current collected profile (fields may be absent or None)
        max_questions: How many questions to return at once
        potentially_eligible_schemes: Scheme IDs still in play (UNCERTAIN or ELIGIBLE)

    Returns:
        List of Question objects, sorted by impact.
    """
    unanswered = []

    for q in ALL_QUESTIONS:
        # Skip if already in profile
        if q.field in profile and profile[q.field] is not None:
            continue

        # Skip if skip_if conditions are met
        if _should_skip(q, profile):
            continue

        # Adjust impact based on currently relevant schemes
        impact = q.impact_score
        if potentially_eligible_schemes:
            impact = _adjust_impact(q, potentially_eligible_schemes, impact)

        unanswered.append((impact, q))

    unanswered.sort(key=lambda x: -x[0])
    return [q for _, q in unanswered[:max_questions]]


def _should_skip(q: Question, profile: dict) -> bool:
    """Check if skip_if conditions are met."""
    for field, value in q.skip_if.items():
        if profile.get(field) == value:
            return True
    return False


def _adjust_impact(q: Question, scheme_ids: list[str], base_impact: int) -> int:
    """
    Boost impact score if this field is critical for currently uncertain schemes.
    """
    # Field → schemes that need it most
    CRITICAL_FIELDS_FOR_SCHEMES = {
        "land_ownership": ["pm_kisan", "pmay_gramin", "pm_fasal_bima"],
        "land_type": ["pm_kisan", "pm_fasal_bima"],
        "has_bank_account": ["pm_kisan", "pm_ujjwala", "pm_matru_vandana", "nsap"],
        "ration_card_type": ["pmgkay", "ayushman_bharat", "pm_ujjwala"],
        "marital_status": ["nsap", "pm_matru_vandana"],
        "is_pregnant": ["pm_matru_vandana"],
        "house_type": ["pmay_gramin", "pmay_urban"],
        "monthly_income": ["pm_shram_yogi_mandhan", "atal_pension_yojana"],
        "is_esic_member": ["pm_shram_yogi_mandhan", "atal_pension_yojana"],
        "is_epfo_member": ["pm_shram_yogi_mandhan", "atal_pension_yojana"],
        "has_lpg_connection": ["pm_ujjwala"],
        "disability": ["nsap"],
        "number_of_daughters": ["sukanya_samriddhi"],
        "is_income_tax_payer": ["pm_kisan", "atal_pension_yojana"],
    }

    relevant = CRITICAL_FIELDS_FOR_SCHEMES.get(q.field, [])
    boost = sum(1 for s in relevant if s in scheme_ids)
    return base_impact + boost


# ── Completeness check ────────────────────────────────────────────────────────

MINIMUM_FIELDS_FOR_MATCH = {
    "age", "gender", "state", "residence_type", "occupation", "has_bank_account"
}

GOOD_FIELDS_FOR_MATCH = MINIMUM_FIELDS_FOR_MATCH | {
    "annual_income_household", "caste_category", "family_size", "ration_card_type"
}


def has_minimum_profile(profile: dict) -> bool:
    """True if we have enough to run a meaningful first match."""
    filled = {f for f in MINIMUM_FIELDS_FOR_MATCH if profile.get(f) is not None}
    return len(filled) >= 4  # At least 4 of the 6 minimum fields


def has_good_profile(profile: dict) -> bool:
    """True if we have enough for a high-quality match with few UNCERTAIN results."""
    filled = {f for f in GOOD_FIELDS_FOR_MATCH if profile.get(f) is not None}
    return len(filled) >= 7


def profile_completeness_pct(profile: dict) -> int:
    """Return completeness as a percentage (0–100)."""
    all_key_fields = {q.field for q in ALL_QUESTIONS}
    filled = sum(1 for f in all_key_fields if profile.get(f) is not None)
    return int((filled / len(all_key_fields)) * 100)
