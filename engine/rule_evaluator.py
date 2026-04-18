"""
engine/rule_evaluator.py

Three-valued logic rule evaluator for welfare scheme eligibility.

Return values for every evaluation:
  - True  = condition met
  - False = condition not met
  - None  = cannot determine (data missing or ambiguous)

Design principle: NEVER collapse None to True or False. Uncertainty must
propagate upward. The caller (matcher.py) is responsible for deciding how
to present uncertain results to the user.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class EvaluationResult:
    """
    Result of evaluating a single rule condition against a user profile.
    """
    matched: Optional[bool]     # True | False | None (unknown)
    confidence: float           # 0.0–1.0. Product of rule confidence × certainty.
    explanation: str            # Human-readable reason
    ambiguity_flags: list[str]  # AMBIGUITY-xxx IDs triggered
    rule_id: Optional[str] = None
    field_missing: bool = False # True if matched=None because field was not provided


def _get_field(profile: dict, field_name: str) -> tuple[Any, bool]:
    """
    Returns (value, is_present).
    is_present = False means the field was absent or explicitly None.
    """
    if field_name not in profile:
        return (None, False)
    val = profile[field_name]
    return (val, val is not None)


def evaluate_condition(condition: dict, profile: dict) -> EvaluationResult:
    """
    Recursively evaluate a condition node against a user profile.

    Condition node shapes:
      Composite:  {"operator": "AND"|"OR"|"NOT", "conditions": [...]}
      Leaf:       {"operator": "EQ"|"NEQ"|"IN"|"NOT_IN"|"GT"|"GTE"|"LT"|"LTE"|"BETWEEN"|"IS_NULL"|"IS_NOT_NULL",
                   "field": "...", "value": ..., "confidence": float, "source": "...", ...}
    """
    op = condition.get("operator", "").upper()

    # ── Composite operators ──────────────────────────────────────────────────

    if op == "AND":
        return _eval_and(condition, profile)

    if op == "OR":
        return _eval_or(condition, profile)

    if op == "NOT":
        return _eval_not(condition, profile)

    # ── Leaf operators ───────────────────────────────────────────────────────

    return _eval_leaf(condition, profile)


# ── AND ──────────────────────────────────────────────────────────────────────

def _eval_and(condition: dict, profile: dict) -> EvaluationResult:
    """
    AND truth table with None:
      True  AND True  = True
      True  AND False = False
      True  AND None  = None
      False AND *     = False   (short-circuit)
      None  AND False = False
      None  AND None  = None
    """
    sub_conditions = condition.get("conditions", [])
    results = [evaluate_condition(c, profile) for c in sub_conditions]

    has_false = any(r.matched is False for r in results)
    has_none  = any(r.matched is None  for r in results)

    all_flags = []
    for r in results:
        all_flags.extend(r.ambiguity_flags)

    rule_id = condition.get("rule_id")
    description = condition.get("description", "AND group")

    if has_false:
        failing = [r for r in results if r.matched is False]
        min_conf = min(r.confidence for r in failing)
        return EvaluationResult(
            matched=False,
            confidence=min_conf,
            explanation=f"{description}: failed — {'; '.join(r.explanation for r in failing)}",
            ambiguity_flags=list(set(all_flags)),
            rule_id=rule_id,
        )

    if has_none:
        none_results = [r for r in results if r.matched is None]
        avg_conf = sum(r.confidence for r in results) / len(results)
        return EvaluationResult(
            matched=None,
            confidence=avg_conf * 0.5,  # halve confidence when uncertain
            explanation=f"{description}: uncertain — cannot determine: {'; '.join(r.explanation for r in none_results)}",
            ambiguity_flags=list(set(all_flags)),
            rule_id=rule_id,
            field_missing=any(r.field_missing for r in none_results),
        )

    # All True
    avg_conf = sum(r.confidence for r in results) / len(results) if results else 1.0
    return EvaluationResult(
        matched=True,
        confidence=avg_conf,
        explanation=f"{description}: all conditions met",
        ambiguity_flags=list(set(all_flags)),
        rule_id=rule_id,
    )


# ── OR ───────────────────────────────────────────────────────────────────────

def _eval_or(condition: dict, profile: dict) -> EvaluationResult:
    """
    OR truth table with None:
      True  OR *     = True   (short-circuit)
      False OR True  = True
      False OR None  = None
      False OR False = False
      None  OR None  = None
    """
    sub_conditions = condition.get("conditions", [])
    results = [evaluate_condition(c, profile) for c in sub_conditions]

    has_true = any(r.matched is True for r in results)
    has_none = any(r.matched is None for r in results)

    all_flags = []
    for r in results:
        all_flags.extend(r.ambiguity_flags)

    rule_id = condition.get("rule_id")
    description = condition.get("description", "OR group")

    if has_true:
        passing = [r for r in results if r.matched is True]
        max_conf = max(r.confidence for r in passing)
        return EvaluationResult(
            matched=True,
            confidence=max_conf,
            explanation=f"{description}: met via — {'; '.join(r.explanation for r in passing)}",
            ambiguity_flags=list(set(all_flags)),
            rule_id=rule_id,
        )

    if has_none:
        avg_conf = sum(r.confidence for r in results) / len(results)
        return EvaluationResult(
            matched=None,
            confidence=avg_conf * 0.5,
            explanation=f"{description}: uncertain — no confirmed match; some conditions could not be evaluated",
            ambiguity_flags=list(set(all_flags)),
            rule_id=rule_id,
            field_missing=any(r.field_missing for r in results),
        )

    # All False
    avg_conf = sum(r.confidence for r in results) / len(results) if results else 1.0
    return EvaluationResult(
        matched=False,
        confidence=avg_conf,
        explanation=f"{description}: no conditions met",
        ambiguity_flags=list(set(all_flags)),
        rule_id=rule_id,
    )


# ── NOT ──────────────────────────────────────────────────────────────────────

def _eval_not(condition: dict, profile: dict) -> EvaluationResult:
    """
    NOT truth table with None:
      NOT True  = False
      NOT False = True
      NOT None  = None  (we cannot confirm absence of disqualifier either)
    """
    sub_conditions = condition.get("conditions", [])
    if not sub_conditions:
        raise ValueError("NOT operator requires exactly one child in 'conditions'")

    # NOT wraps a single child (which may itself be an OR/AND)
    # If conditions has multiple children, treat them as if wrapped in an OR
    if len(sub_conditions) == 1:
        inner = evaluate_condition(sub_conditions[0], profile)
    else:
        inner = _eval_or({"conditions": sub_conditions}, profile)

    rule_id = condition.get("rule_id")
    description = condition.get("description", "NOT group")
    flags = inner.ambiguity_flags

    if inner.matched is True:
        return EvaluationResult(
            matched=False,
            confidence=inner.confidence,
            explanation=f"{description}: disqualified — {inner.explanation}",
            ambiguity_flags=flags,
            rule_id=rule_id,
        )

    if inner.matched is False:
        return EvaluationResult(
            matched=True,
            confidence=inner.confidence,
            explanation=f"{description}: exclusion criterion not triggered",
            ambiguity_flags=flags,
            rule_id=rule_id,
        )

    # None — cannot determine if exclusion applies
    return EvaluationResult(
        matched=None,
        confidence=inner.confidence * 0.5,
        explanation=f"{description}: uncertain — cannot confirm absence of disqualifying condition",
        ambiguity_flags=flags,
        rule_id=rule_id,
        field_missing=inner.field_missing,
    )


# ── LEAF OPERATORS ───────────────────────────────────────────────────────────

def _eval_leaf(condition: dict, profile: dict) -> EvaluationResult:
    """
    Evaluate a single field comparison.
    """
    op         = condition.get("operator", "").upper()
    field_name = condition.get("field", "")
    expected   = condition.get("value")
    rule_conf  = float(condition.get("confidence", 1.0))
    source     = condition.get("source", "")
    rule_id    = condition.get("rule_id")
    ambiguity  = condition.get("ambiguity_flag", None)
    ambig_note = condition.get("ambiguity_note", "")
    description = condition.get("description", f"{field_name} {op} {expected}")

    flags = [ambiguity] if ambiguity else []

    actual, is_present = _get_field(profile, field_name)

    # Special case: IS_NULL / IS_NOT_NULL work on absent fields
    if op in ("IS_NULL", "IS_NOT_NULL"):
        result = _compare(op, actual if is_present else None, expected, field_name=field_name)
        return EvaluationResult(
            matched=result,
            confidence=float(condition.get("confidence", 0.80)),
            explanation=f"[{rule_id or op}] {description}: {'met' if result else 'not met'} (field {'absent' if not is_present else f'={actual!r}'})",
            ambiguity_flags=[ambiguity] if ambiguity else [],
            rule_id=rule_id,
        )

    # If field missing, return None (uncertain) — never default to True or False
    if not is_present:
        note = f" Note: {ambig_note}" if ambig_note else ""
        return EvaluationResult(
            matched=None,
            confidence=0.0,
            explanation=f"Cannot evaluate '{field_name}' — data not provided.{note}",
            ambiguity_flags=flags,
            rule_id=rule_id,
            field_missing=True,
        )

    # Ambiguity flag on a present field reduces confidence
    if ambiguity:
        rule_conf = min(rule_conf, 0.65)

    matched = _compare(op, actual, expected, field_name=field_name)

    if matched is None:
        return EvaluationResult(
            matched=None,
            confidence=0.0,
            explanation=f"Unknown operator '{op}' for field '{field_name}'",
            ambiguity_flags=flags,
            rule_id=rule_id,
        )

    status_word = "met" if matched else "not met"
    expl = f"[{rule_id or op}] {description}: {status_word} (actual={actual!r}, expected={expected!r})"
    if matched and ambig_note:
        expl += f" [AMBIGUOUS: {ambig_note}]"

    return EvaluationResult(
        matched=matched,
        confidence=rule_conf if matched else rule_conf,
        explanation=expl,
        ambiguity_flags=flags,
        rule_id=rule_id,
    )


def _compare(op: str, actual: Any, expected: Any, field_name: str = "") -> Optional[bool]:
    """
    Apply a comparison operator. Returns True/False/None.
    None only if operator is unrecognised OR result is genuinely ambiguous.

    Special case: residence_type comparisons where actual="peri-urban" vs
    expected "rural" or "urban" return None — jurisdiction is ambiguous.
    """
    # Peri-urban is neither definitively rural nor urban — return uncertain
    if field_name == "residence_type" and actual == "peri-urban":
        if op in ("EQ", "IN"):
            if expected in ("rural", "urban") or (isinstance(expected, list) and set(expected) & {"rural", "urban"}):
                return None  # Cannot determine — peri-urban is jurisdictionally ambiguous

    try:
        if op == "EQ":
            return actual == expected
        if op == "NEQ":
            return actual != expected
        if op == "IN":
            return actual in expected
        if op == "NOT_IN":
            return actual not in expected
        if op == "GT":
            return actual > expected
        if op == "GTE":
            return actual >= expected
        if op == "LT":
            return actual < expected
        if op == "LTE":
            return actual <= expected
        if op == "BETWEEN":
            lo, hi = expected
            return lo <= actual <= hi
        if op == "IS_NULL":
            return actual is None
        if op == "IS_NOT_NULL":
            return actual is not None
    except (TypeError, ValueError):
        return None

    return None  # Unknown operator


# ── SCHEME-LEVEL EVALUATION ──────────────────────────────────────────────────

def evaluate_scheme(scheme: dict, profile: dict) -> EvaluationResult:
    """
    Evaluate the top-level eligibility_rules for a scheme.
    Returns a single EvaluationResult representing the scheme-level outcome.
    Also applies a source_confidence penalty and any data-freshness penalties.
    """
    rules      = scheme.get("eligibility_rules", {})
    src_conf   = float(scheme.get("source_confidence", 1.0))

    base = evaluate_condition(rules, profile)

    # Apply source_confidence as a ceiling on confidence
    adjusted_conf = base.confidence * src_conf

    # Special penalty for SECC-2011-dependent schemes
    secc_dependent = "AMBIGUITY-004" in (scheme.get("ambiguity_flags", []) or [])
    if secc_dependent and profile.get("secc_listed") is None:
        adjusted_conf *= 0.75  # 25% penalty when SECC status unknown

    return EvaluationResult(
        matched=base.matched,
        confidence=round(adjusted_conf, 3),
        explanation=base.explanation,
        ambiguity_flags=base.ambiguity_flags,
        rule_id=base.rule_id,
        field_missing=base.field_missing,
    )
