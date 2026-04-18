"""
interface/contradiction_detector.py

Detects logical contradictions in the collected user profile.

When a contradiction is found, the engine does NOT pick one answer and
move on. It surfaces the contradiction as a clarifying question and holds
both values in uncertainty until the user resolves it.

Design principle: contradictions are surfaced, not silently resolved.
The user's dignity and autonomy are respected — we assume they gave us
genuine information and ask them to help us understand.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Contradiction:
    field_a: str
    value_a: object
    field_b: str
    value_b: object
    description_hinglish: str
    description_english: str
    clarification_question: str    # What to ask the user to resolve it
    resolution_hint: str           # How to interpret each possible answer


# ── Contradiction rules ────────────────────────────────────────────────────────

def detect_contradictions(profile: dict) -> list[Contradiction]:
    """
    Check profile for internal contradictions.
    Returns a list of Contradiction objects (empty if none found).
    """
    contradictions = []

    for rule in CONTRADICTION_RULES:
        result = rule(profile)
        if result:
            contradictions.append(result)

    return contradictions


def _check_income_vs_bpl(profile: dict) -> Optional[Contradiction]:
    """
    High income + BPL/AAY ration card is suspicious.
    Income > ₹3L/year + AAY card is almost certainly wrong.
    """
    income = profile.get("annual_income_household")
    ration = profile.get("ration_card_type")

    if income and ration == "AAY" and income > 500000:
        return Contradiction(
            field_a="annual_income_household",
            value_a=income,
            field_b="ration_card_type",
            value_b=ration,
            description_hinglish=(
                f"Aapne bataya ki ghar ki income ₹{income:,}/saal hai, "
                "lekin aapke paas Antyodaya (AAY) ration card bhi hai. "
                "AAY card sabse gareeb parivaron ko milta hai — "
                "yeh dono baatein ek saath thodi alag lagti hain."
            ),
            description_english=(
                f"You mentioned a household income of ₹{income:,}/year, "
                "but also hold an AAY (Antyodaya) ration card. "
                "AAY cards are issued to the poorest households — "
                "these two details seem inconsistent."
            ),
            clarification_question=(
                "Kya aap clarify kar sakte hain — "
                "aapki income abhi kitni hai, aur ration card kab se hai? "
                "(Could you clarify your current income and when the ration card was issued?)"
            ),
            resolution_hint=(
                "If income recently increased: ration card status may now be outdated — "
                "eligibility may have changed. "
                "If income is correct and card is old: use income figure for matching."
            ),
        )

    if income and ration == "PHH" and income > 1500000:
        return Contradiction(
            field_a="annual_income_household",
            value_a=income,
            field_b="ration_card_type",
            value_b=ration,
            description_hinglish=(
                f"Aapne bataya ki income ₹{income:,}/saal hai, "
                "lekin PHH ration card bhi hai. "
                "PHH cards gareeb parivaron ke liye hote hain — "
                "kuch poochna tha."
            ),
            description_english=(
                f"Income of ₹{income:,}/year with a PHH ration card seems inconsistent. "
                "PHH is for households below a certain income threshold."
            ),
            clarification_question=(
                "Kya yeh income sabhi family members ki milake hai? "
                "Ya aapka ration card bahut pehle ka hai?"
            ),
            resolution_hint=(
                "Combined household income may include multiple earning members. "
                "Or ration card may predate income changes."
            ),
        )

    return None


def _check_farmer_no_land(profile: dict) -> Optional[Contradiction]:
    """
    Farmer with explicit land_ownership=False and no land_type.
    This is actually valid (agricultural labourer) but needs clarification.
    """
    occ = profile.get("occupation")
    owns = profile.get("land_ownership")
    land_type = profile.get("land_type")

    if occ == "farmer" and owns is False and land_type is None:
        return Contradiction(
            field_a="occupation",
            value_a="farmer",
            field_b="land_ownership",
            value_b=False,
            description_hinglish=(
                "Aapne bataya ki aap kisan hain, "
                "lekin yeh bhi bataya ki aapke naam par zameen nahi hai. "
                "Kya aap kisi ki zameen par kaam karte hain?"
            ),
            description_english=(
                "You mentioned being a farmer but said you don't own land. "
                "This could mean you're a tenant farmer, sharecropper, or agricultural labourer."
            ),
            clarification_question=(
                "Thoda aur batao — kya aap:\n"
                "  (a) Kisi ki zameen lease par lete hain? (Tenant farmer)\n"
                "  (b) Batai par kaam karte hain? (Sharecropper)\n"
                "  (c) Kisi ke khet mein mazdoori karte hain? (Agricultural labourer)\n"
                "Yeh jaanna important hai — alag alag schemes ke liye alag eligibility hai."
            ),
            resolution_hint=(
                "(a) Leased: eligible for PMFBY and KCC with NOC, NOT clearly eligible for PM Kisan. "
                "(b) Sharecrop: eligible for PMFBY, NOT clearly eligible for PM Kisan. "
                "(c) Labourer: eligible for MGNREGA, NOT eligible for PM Kisan."
            ),
        )

    return None


def _check_age_vs_pregnancy(profile: dict) -> Optional[Contradiction]:
    """Age too low or too high for pregnancy to be plausible."""
    age = profile.get("age")
    pregnant = profile.get("is_pregnant")

    if pregnant and age and (age < 15 or age > 50):
        return Contradiction(
            field_a="age",
            value_a=age,
            field_b="is_pregnant",
            value_b=True,
            description_hinglish=f"Aapne bataya ki aap {age} saal ke hain aur pregnant hain — kya yeh sahi hai?",
            description_english=f"You mentioned being {age} years old and pregnant — is this correct?",
            clarification_question="Kya aap apni umar dobara confirm kar sakte hain?",
            resolution_hint="If age is correct and pregnancy is reported for a family member, clarify it is for the family member.",
        )

    return None


def _check_male_pregnancy(profile: dict) -> Optional[Contradiction]:
    """Male self-reporting as pregnant."""
    gender = profile.get("gender")
    pregnant = profile.get("is_pregnant")

    if gender == "male" and pregnant:
        return Contradiction(
            field_a="gender",
            value_a="male",
            field_b="is_pregnant",
            value_b=True,
            description_hinglish="Aapne bataya ki aap purush hain aur pregnant bhi hain — kya aap apni patni ke baare mein baat kar rahe hain?",
            description_english="You said you are male and also pregnant — are you referring to your wife/partner?",
            clarification_question="Kya yeh pregnancy aapki patni / ghar ki kisi mahila ke liye hai?",
            resolution_hint="If the pregnant person is a family member, use their profile, not yours, for PMMVY matching.",
        )

    return None


def _check_epfo_and_unorganised(profile: dict) -> Optional[Contradiction]:
    """EPFO/ESIC member self-describing as unorganised worker."""
    is_epfo = profile.get("is_epfo_member")
    is_esic = profile.get("is_esic_member")
    sector = profile.get("sector_type")
    occupation = profile.get("occupation")

    if (is_epfo or is_esic) and (sector == "unorganised" or occupation == "unorganised_worker"):
        covered = "EPFO" if is_epfo else "ESIC"
        return Contradiction(
            field_a="is_epfo_member" if is_epfo else "is_esic_member",
            value_a=True,
            field_b="sector_type",
            value_b=sector or occupation,
            description_hinglish=(
                f"Aapne bataya ki aap {covered} mein covered hain, "
                "lekin aapne yeh bhi kaha ki aap asangathit kaamgaar hain. "
                f"{covered} organised sector ka hissa hai."
            ),
            description_english=(
                f"You mentioned being covered under {covered} "
                "but also described yourself as an unorganised worker. "
                f"{covered} membership means you are in the organised sector."
            ),
            clarification_question=(
                f"Ek cheez confirm karein — kya aapke employer ne aapko {covered} mein enroll kiya hai? "
                "Ya aap soch rahe the ki yeh koi alag cheez hai?"
            ),
            resolution_hint=(
                f"If {covered} is confirmed: you are organised sector. "
                "PM-SYM and APY require NOT being EPFO/ESIC covered. "
                "PMJJBY and PMSBY are still available."
            ),
        )

    return None


def _check_itr_and_bpl(profile: dict) -> Optional[Contradiction]:
    """Income tax filer with BPL ration card."""
    itr = profile.get("is_income_tax_payer")
    ration = profile.get("ration_card_type")

    if itr and ration in ("AAY", "PHH"):
        return Contradiction(
            field_a="is_income_tax_payer",
            value_a=True,
            field_b="ration_card_type",
            value_b=ration,
            description_hinglish=(
                "Aapne bataya ki aap income tax bharte hain, "
                "aur saath mein BPL ration card bhi hai. "
                "Yeh dono aam taur par saath nahi hote."
            ),
            description_english=(
                "You mentioned filing income tax and also holding a BPL ration card. "
                "These are typically inconsistent."
            ),
            clarification_question=(
                "Kya aap batayenge — income tax file karne wala ghar mein koi aur hai, "
                "ya ration card bahut pehle ka bana tha?"
            ),
            resolution_hint=(
                "If ITR is filed by another family member: ITR-filer's income disqualifies from PM Kisan. "
                "If ration card is old and income has grown: schemes based on BPL may no longer apply."
            ),
        )

    return None


def _check_age_and_pension_scheme(profile: dict) -> Optional[Contradiction]:
    """
    User says they want PM-SYM but is over 40, or is already 60+.
    Informational contradiction — not a data error, just highlight.
    """
    age = profile.get("age")

    # This is more of an informational nudge — not a true contradiction
    # Don't flag it as a contradiction to avoid over-asking
    return None


# ── Rule list ─────────────────────────────────────────────────────────────────

CONTRADICTION_RULES = [
    _check_income_vs_bpl,
    _check_farmer_no_land,
    _check_age_vs_pregnancy,
    _check_male_pregnancy,
    _check_epfo_and_unorganised,
    _check_itr_and_bpl,
]


# ── Renderer ──────────────────────────────────────────────────────────────────

def format_contradiction_for_cli(c: Contradiction) -> str:
    """Format a contradiction as a CLI message."""
    lines = [
        "┌─ Ek baat thodi confusing lag rahi hai ────────────────",
        f"│ {c.description_hinglish}",
        "│",
        f"│ {c.clarification_question}",
        "└──────────────────────────────────────────────────────",
    ]
    return "\n".join(lines)
