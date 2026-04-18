"""
engine/gap_analyzer.py

Gap analysis for ALMOST_ELIGIBLE schemes.

For each top-level rule that failed, this module:
  1. Identifies what the user currently has vs. what is required
  2. Determines if the gap is actionable (can they realistically close it?)
  3. Provides a plain-language action hint

Gap types:
  - HARD_DISQUALIFIER: Cannot be changed (age, caste, etc.) → not actionable
  - DOCUMENT_GAP: They qualify but are missing a document → actionable
  - STATUS_GAP: They need to enroll in a prerequisite scheme first → actionable
  - CRITERIA_GAP: They don't meet a criterion that could change (income, occupation) → sometimes actionable
  - UNKNOWN_GAP: Cannot determine because field is missing → ask for field
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from engine.rule_evaluator import evaluate_condition, EvaluationResult
from engine.matcher import GapItem


# ── Gap classification logic ──────────────────────────────────────────────────

# Fields that represent immutable characteristics — gaps here are NEVER actionable
HARD_FIELDS = {"age", "gender", "caste_category", "nationality"}

# Fields where being missing = a document gap (user likely has it, just not provided)
DOCUMENT_FIELDS = {
    "has_bank_account": ("Open a bank account under PM Jan Dhan Yojana", "STATUS_GAP"),
    "bank_account_aadhaar_linked": ("Link your Aadhaar to your bank account at your bank branch", "DOCUMENT_GAP"),
    "has_lpg_connection": (None, "CRITERIA_GAP"),  # None = no action hint needed
    "has_job_card_or_applying": ("Apply for MGNREGA Job Card at your Gram Panchayat", "STATUS_GAP"),
    "land_ownership": ("Land records must be in your name — sharecrop/lease land is uncertain for PM Kisan", "CRITERIA_GAP"),
}


def analyze_gaps(scheme: dict, profile: dict) -> list[GapItem]:
    """
    For a scheme the user is almost-eligible for, identify exactly which
    conditions failed and what the user needs to do.

    Returns a list of GapItems, one per failed condition.
    """
    rules = scheme.get("eligibility_rules", {})

    if rules.get("operator", "").upper() != "AND":
        # Cannot decompose a non-AND top level
        return _analyze_single_condition(rules, profile, scheme)

    gap_items = []
    for condition in rules.get("conditions", []):
        res = evaluate_condition(condition, profile)
        if res.matched is False:
            items = _condition_to_gaps(condition, profile, res)
            gap_items.extend(items)

    return gap_items


def _analyze_single_condition(condition: dict, profile: dict, scheme: dict) -> list[GapItem]:
    res = evaluate_condition(condition, profile)
    if res.matched is False:
        return _condition_to_gaps(condition, profile, res)
    return []


def _condition_to_gaps(condition: dict, profile: dict, res: EvaluationResult) -> list[GapItem]:
    """
    Convert a failed condition into one or more GapItems.
    Drills into the condition to find the specific leaf that failed.
    """
    op = condition.get("operator", "").upper()

    # For NOT — the inner condition was True (disqualifier fired)
    if op == "NOT":
        return _gap_from_not(condition, profile)

    # For AND — find the failing child
    if op == "AND":
        items = []
        for child in condition.get("conditions", []):
            child_res = evaluate_condition(child, profile)
            if child_res.matched is False:
                items.extend(_condition_to_gaps(child, profile, child_res))
        return items if items else [_generic_gap(condition, res)]

    # For OR — the whole OR failed (no branch matched)
    if op == "OR":
        return _gap_from_or(condition, profile)

    # Leaf condition
    return [_gap_from_leaf(condition, profile)]


def _gap_from_leaf(condition: dict, profile: dict) -> GapItem:
    field_name   = condition.get("field", "unknown_field")
    op           = condition.get("operator", "")
    expected     = condition.get("value")
    description  = condition.get("description", f"Requires {field_name} {op} {expected}")
    rule_id      = condition.get("rule_id", "")

    actual = profile.get(field_name)

    # Is the gap actionable?
    if field_name in HARD_FIELDS:
        actionable = False
        action_hint = "This criterion cannot be changed."
    elif field_name in DOCUMENT_FIELDS:
        hint, gap_type = DOCUMENT_FIELDS[field_name]
        actionable = hint is not None
        action_hint = hint or "No direct action available."
    else:
        actionable = _is_likely_actionable(field_name, op, actual, expected)
        action_hint = _build_action_hint(field_name, op, actual, expected)

    required_desc = _build_required_description(op, expected, condition)

    return GapItem(
        rule_id=rule_id,
        rule_description=description,
        current_value=actual,
        required_description=required_desc,
        actionable=actionable,
        action_hint=action_hint,
    )


def _gap_from_not(condition: dict, profile: dict) -> list[GapItem]:
    """A NOT condition failed means the disqualifier IS present."""
    sub_conditions = condition.get("conditions", [])
    items = []
    for child in sub_conditions:
        child_res = evaluate_condition(child, profile)
        if child_res.matched is True:
            field_name = child.get("field", "unknown")
            description = child.get("description", f"Exclusion: {field_name}")
            rule_id = child.get("rule_id", "")
            actual = profile.get(field_name)

            # Exclusion criteria — check if the disqualifier can be removed
            actionable, action_hint = _exclusion_actionability(field_name, actual)

            items.append(GapItem(
                rule_id=rule_id,
                rule_description=f"Exclusion criterion triggered: {description}",
                current_value=actual,
                required_description=f"Must NOT have: {description}",
                actionable=actionable,
                action_hint=action_hint,
            ))
    return items


def _gap_from_or(condition: dict, profile: dict) -> list[GapItem]:
    """
    OR failed: present ALL branches as options the user could pursue.
    This surfaces as a single GapItem with a combined description.
    """
    description = condition.get("description", "Must meet at least one of the following")
    rule_id = condition.get("rule_id", "")

    branches = []
    for child in condition.get("conditions", []):
        branch_desc = child.get("description") or child.get("field", "option")
        branches.append(branch_desc)

    options_str = " | ".join(branches)
    return [GapItem(
        rule_id=rule_id,
        rule_description=description,
        current_value=None,
        required_description=f"Must qualify under at least one: {options_str}",
        actionable=True,
        action_hint="Review each option and pursue the one most applicable to your situation.",
    )]


def _generic_gap(condition: dict, res: EvaluationResult) -> GapItem:
    return GapItem(
        rule_id=condition.get("rule_id", ""),
        rule_description=condition.get("description", "Condition not met"),
        current_value=None,
        required_description=res.explanation,
        actionable=False,
        action_hint="Consult your nearest Jan Seva Kendra or Block Development Office.",
    )


# ── Actionability helpers ─────────────────────────────────────────────────────

def _is_likely_actionable(field: str, op: str, actual, expected) -> bool:
    """
    Heuristic: can the user realistically change this field value?
    """
    # Things they can change
    actionable_fields = {
        "has_bank_account", "bank_account_aadhaar_linked",
        "has_job_card_or_applying", "willing_to_do_manual_work",
        "voluntary_enrollment_pmfby", "self_declaration_poor",
        "has_pmjdy_account",
    }
    return field in actionable_fields


def _build_action_hint(field: str, op: str, actual, expected) -> str:
    hints = {
        "has_bank_account": "Open a zero-balance account under PM Jan Dhan Yojana at any bank branch.",
        "bank_account_aadhaar_linked": "Visit your bank branch with your Aadhaar to link it.",
        "has_job_card_or_applying": "Apply for MGNREGA Job Card at your Gram Panchayat.",
        "willing_to_do_manual_work": "Confirm willingness when applying for MGNREGA.",
        "voluntary_enrollment_pmfby": "Voluntarily enroll in PMFBY before the seasonal cut-off at your bank.",
        "self_declaration_poor": "Self-declare as a poor household at your LPG distributor under PMUY 2.0.",
        "has_pmjdy_account": "Open a PMJDY account at any bank to get full insurance benefits.",
    }
    return hints.get(field, "Consult your nearest Common Service Centre for guidance.")


def _build_required_description(op: str, expected, condition: dict) -> str:
    """Build a human-readable description of what value is required."""
    op_upper = op.upper()
    try:
        if op_upper == "IN":
            items = expected if isinstance(expected, (list, tuple)) else [expected]
            return f"Must be one of: {', '.join(str(v) for v in items)}"
        if op_upper == "NOT_IN":
            items = expected if isinstance(expected, (list, tuple)) else [expected]
            return f"Must not be any of: {', '.join(str(v) for v in items)}"
        if op_upper == "BETWEEN":
            parts = expected if isinstance(expected, (list, tuple)) and len(expected) == 2 else [expected, expected]
            return f"Must be between {parts[0]} and {parts[1]}"
    except (TypeError, IndexError):
        pass

    desc_map = {
        "EQ": f"Must be: {expected}",
        "NEQ": f"Must NOT be: {expected}",
        "GT": f"Must be greater than: {expected}",
        "GTE": f"Must be at least: {expected}",
        "LT": f"Must be less than: {expected}",
        "LTE": f"Must be at most: {expected}",
    }
    return desc_map.get(op_upper, f"Condition: {condition.get('description', str(expected))}")


def _exclusion_actionability(field: str, actual) -> tuple[bool, str]:
    """
    For exclusion criteria (NOT conditions that fired), determine if the
    disqualifying status can be changed.
    """
    non_actionable = {
        "is_constitutional_post_holder": "Constitutional post holder status cannot be changed.",
        "is_income_tax_payer": "If someone in your household pays income tax, PM Kisan eligibility is affected. This cannot be changed but verify household-level vs individual interpretation with your agriculture office.",
        "is_institutional_land_holder": "Institutional land holding disqualifies from PM Kisan — not actionable.",
    }
    if field in non_actionable:
        return (False, non_actionable[field])

    # Soft exclusions that might be contestable
    return (False, "This exclusion criterion disqualifies you. Consult a Jan Seva Kendra if you believe this is incorrectly applied.")
