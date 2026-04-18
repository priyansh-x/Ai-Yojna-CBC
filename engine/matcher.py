"""
engine/matcher.py

Main matching engine. Loads all scheme JSON files, evaluates each scheme
against a user profile, and returns a structured MatchResult for every scheme.

Status categories:
  FULLY_ELIGIBLE   — matched=True, confidence >= 0.75, no critical ambiguity flags
  LIKELY_ELIGIBLE  — matched=True, confidence 0.40–0.74 (ambiguity flags present)
  ALMOST_ELIGIBLE  — matched=False but only 1–2 rules failed with closable gaps
  INELIGIBLE       — matched=False with hard disqualifiers or many failures
  UNCERTAIN        — matched=None (critical fields missing)

Every output is explainable — confidence is traceable to specific rule evaluations.
No black boxes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from engine.rule_evaluator import evaluate_scheme, EvaluationResult


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class GapItem:
    rule_id: str
    rule_description: str
    current_value: object
    required_description: str
    actionable: bool           # Can the user realistically close this gap?
    action_hint: str           # What they would need to do


@dataclass
class DocumentItem:
    document: str
    mandatory: bool
    priority: int
    obtainable_from: str


@dataclass
class MatchResult:
    scheme_id: str
    scheme_name: str
    ministry: str
    benefit: str
    application_url: str

    status: str                        # FULLY_ELIGIBLE | LIKELY_ELIGIBLE | ALMOST_ELIGIBLE | INELIGIBLE | UNCERTAIN
    confidence: float                  # 0.0–1.0
    confidence_label: str              # Human label: HIGH / MEDIUM / LOW / UNKNOWN

    # Full traceable breakdown — every rule that contributed to the score
    rule_evaluations: list[dict]

    # Populated for ALMOST_ELIGIBLE
    gap_analysis: list[GapItem] = field(default_factory=list)

    # Documents needed (for eligible/almost-eligible schemes)
    document_checklist: list[DocumentItem] = field(default_factory=list)

    # Ambiguity warnings to surface to user
    warnings: list[str] = field(default_factory=list)

    # Fields that are missing and would change the result if provided
    missing_fields: list[str] = field(default_factory=list)


# ── Scheme loader ─────────────────────────────────────────────────────────────

def load_all_schemes(schemes_dir: str) -> list[dict]:
    """Load all scheme JSON files from the schemes directory."""
    schemes = []
    for fname in sorted(os.listdir(schemes_dir)):
        if fname.endswith(".json"):
            fpath = os.path.join(schemes_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                schemes.append(json.load(f))
    return schemes


def load_ambiguity_map(data_dir: str) -> dict:
    fpath = os.path.join(data_dir, "ambiguity_map.json")
    with open(fpath, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Status classification ─────────────────────────────────────────────────────

def _classify_status(result: EvaluationResult, scheme: dict, profile: dict) -> tuple[str, str]:
    """
    Returns (status, confidence_label).
    """
    if result.matched is None:
        return ("UNCERTAIN", "UNKNOWN")

    if result.matched is True:
        c = result.confidence
        if c >= 0.75:
            return ("FULLY_ELIGIBLE", "HIGH")
        elif c >= 0.45:
            return ("LIKELY_ELIGIBLE", "MEDIUM")
        else:
            return ("LIKELY_ELIGIBLE", "LOW")

    # matched is False — determine INELIGIBLE vs ALMOST_ELIGIBLE vs UNCERTAIN

    # Rule 1: If ANY top-level failure is a NOT condition (exclusion fired),
    # it's INELIGIBLE. Exclusion criteria are non-negotiable disqualifiers.
    if _has_not_failure(scheme, profile):
        return ("INELIGIBLE", "LOW")

    # Rule 2: Count top-level failures
    failing_conditions = _get_failing_top_level_conditions(scheme, profile)
    failing_count = len(failing_conditions)

    if failing_count == 0:
        return ("INELIGIBLE", "LOW")

    # Rule 3: If ANY failure involves a hard immutable field (age, gender, caste),
    # it's INELIGIBLE — gap is not actionable.
    if _any_failure_is_hard(failing_conditions, profile):
        return ("INELIGIBLE", "LOW")

    # Rule 4: If the single failing condition has an ambiguity flag,
    # the failure is uncertain (the rule itself is contested) → UNCERTAIN
    if failing_count == 1 and _failure_has_ambiguity(failing_conditions[0]):
        return ("UNCERTAIN", "LOW")

    if failing_count == 1:
        return ("ALMOST_ELIGIBLE", "LOW")

    return ("INELIGIBLE", "LOW")


def _count_top_level_failures(scheme: dict, profile: dict) -> int:
    return len(_get_failing_top_level_conditions(scheme, profile))


def _get_failing_top_level_conditions(scheme: dict, profile: dict) -> list[dict]:
    """Return top-level conditions that evaluated to False."""
    from engine.rule_evaluator import evaluate_condition

    rules = scheme.get("eligibility_rules", {})
    if rules.get("operator", "").upper() != "AND":
        return [rules]

    failing = []
    for condition in rules.get("conditions", []):
        res = evaluate_condition(condition, profile)
        if res.matched is False:
            failing.append(condition)
    return failing


def _has_not_failure(scheme: dict, profile: dict) -> bool:
    """True if any top-level failing condition is a NOT (exclusion that fired)."""
    from engine.rule_evaluator import evaluate_condition

    rules = scheme.get("eligibility_rules", {})
    if rules.get("operator", "").upper() != "AND":
        return False

    for condition in rules.get("conditions", []):
        if condition.get("operator", "").upper() == "NOT":
            res = evaluate_condition(condition, profile)
            if res.matched is False:
                return True
    return False


# Hard fields: failures on these are never ALMOST_ELIGIBLE — always INELIGIBLE
HARD_FIELDS = {"age", "gender", "nationality"}


def _any_failure_is_hard(failing_conditions: list[dict], profile: dict) -> bool:
    """
    True if any failing condition is a hard immutable disqualifier (age, gender, etc.).

    Only checks DIRECT leaf conditions or AND children — never recurses into OR.
    OR conditions have multiple paths; a hard field in one branch does not make
    the whole OR hard (the user may be on a different, non-hard path).
    """
    from engine.rule_evaluator import evaluate_condition

    def _is_hard_leaf(cond: dict) -> bool:
        op = cond.get("operator", "").upper()
        # Only leaf operators, never recurse into OR (other paths may not be hard)
        if op in ("EQ", "NEQ", "IN", "NOT_IN", "GT", "GTE", "LT", "LTE", "BETWEEN"):
            return cond.get("field") in HARD_FIELDS
        return False

    for cond in failing_conditions:
        op = cond.get("operator", "").upper()
        if op == "OR":
            # Do NOT look inside OR for hard fields — see docstring
            continue
        elif op == "AND":
            # Check each AND child individually
            for child in cond.get("conditions", []):
                if _is_hard_leaf(child):
                    res = evaluate_condition(child, profile)
                    if res.matched is False:
                        return True
        else:
            # Direct leaf
            if _is_hard_leaf(cond):
                return True
    return False


def _failure_has_ambiguity(condition: dict) -> bool:
    """True if a failing condition or any of its leaves has an ambiguity_flag."""
    if condition.get("ambiguity_flag"):
        return True
    for child in condition.get("conditions", []):
        if _failure_has_ambiguity(child):
            return True
    return False


# ── Warning builder ───────────────────────────────────────────────────────────

AMBIGUITY_WARNINGS = {
    "AMBIGUITY-001": "Your farming arrangement (sharecrop/labour) may affect eligibility. Verify your role with your local agriculture office.",
    "AMBIGUITY-002": "Your area's rural/urban classification may affect eligibility. Verify with your Block Development Office.",
    "AMBIGUITY-003": "PM Kisan requires land ownership. If you farm leased or sharecrop land, eligibility is uncertain — verify at your Gram Panchayat.",
    "AMBIGUITY-004": "Eligibility depends on SECC 2011 data. Check your status at pmjay.gov.in or your nearest Common Service Centre.",
    "AMBIGUITY-005": "The definition of 'poor household' for PMUY 2.0 is not defined. Visit your nearest LPG distributor — acceptance may vary.",
    "AMBIGUITY-006": "Widow pension rules for remarried persons differ by state. Verify with your Block Development Office.",
    "AMBIGUITY-007": "You may be eligible for BOTH PM-SYM and APY simultaneously — they are not mutually exclusive.",
    "AMBIGUITY-008": "The 100-day MGNREGA guarantee is per household. If you are part of a large joint family, ask your Gram Panchayat about separate registration.",
    "AMBIGUITY-009": "MUDRA covers your non-farm business only, not farm income directly.",
    "AMBIGUITY-010": "If your bank account was opened before 2014, it may not carry full PMJDY insurance benefits. Confirm with your bank.",
    "AMBIGUITY-011": "If any family member in your household files income tax, PM Kisan eligibility is uncertain. Verify with your local agriculture office.",
    "AMBIGUITY-012": "Gig/platform workers may qualify as unorganised workers. If you are not EPFO/ESIC-covered, you likely qualify.",
    "AMBIGUITY-013": "MGNREGA eligibility in peri-urban areas depends on Gram Panchayat jurisdiction — verify at your Block Development Office.",
    "AMBIGUITY-014": "You can receive PM Kisan AND work under MGNREGA in the same year — these do not conflict.",
    "AMBIGUITY-015": "Previous miscarriage or stillbirth does NOT affect PMMVY eligibility — you are still eligible for the first living child benefit.",
    "AMBIGUITY-016": "NSAP 'destitute' status is assessed by your Gram Panchayat/ULB — apply with income evidence.",
    "AMBIGUITY-017": "PMJJBY and PMSBY can be enrolled simultaneously — together they provide ₹4 lakh coverage for ₹456/year.",
}


def _build_warnings(ambiguity_flags: list[str]) -> list[str]:
    seen = set()
    warnings = []
    for flag in ambiguity_flags:
        if flag not in seen and flag in AMBIGUITY_WARNINGS:
            warnings.append(f"[{flag}] {AMBIGUITY_WARNINGS[flag]}")
            seen.add(flag)
    return warnings


# ── Rule evaluation trace ─────────────────────────────────────────────────────

def _flatten_evaluation(result: EvaluationResult, depth: int = 0) -> list[dict]:
    """
    Flatten an EvaluationResult tree into a list of dicts for display.
    Only surfaces meaningful leaf nodes (not intermediate AND/OR groups).
    """
    entries = []
    entry = {
        "rule_id": result.rule_id or f"depth_{depth}",
        "matched": result.matched,
        "confidence": round(result.confidence, 3),
        "explanation": result.explanation,
        "ambiguity_flags": result.ambiguity_flags,
        "field_missing": result.field_missing,
    }
    entries.append(entry)
    return entries


# ── Missing fields extractor ──────────────────────────────────────────────────

def _extract_missing_fields(result: EvaluationResult) -> list[str]:
    """Pull out field names that were missing and caused None results."""
    missing = []
    # The explanation text contains "Cannot evaluate 'field_name'" for missing fields
    import re
    for match in re.finditer(r"Cannot evaluate '([^']+)'", result.explanation):
        field = match.group(1)
        if field not in missing:
            missing.append(field)
    return missing


# ── Main matching function ────────────────────────────────────────────────────

def match_profile(profile: dict, data_dir: str) -> list[MatchResult]:
    """
    Run the full matching engine against a user profile.

    Args:
        profile: UserProfile dict (fields may be None for unknown)
        data_dir: Path to the data/ directory

    Returns:
        List of MatchResult, sorted by:
          1. Status priority (FULLY_ELIGIBLE first, INELIGIBLE last)
          2. Confidence descending within status
    """
    schemes_dir = os.path.join(data_dir, "schemes")
    schemes = load_all_schemes(schemes_dir)

    results: list[MatchResult] = []

    for scheme in schemes:
        # Core evaluation
        eval_result = evaluate_scheme(scheme, profile)

        # Status classification
        status, conf_label = _classify_status(eval_result, scheme, profile)

        # Build warnings from ambiguity flags
        all_flags = list(set(
            eval_result.ambiguity_flags
            + scheme.get("ambiguity_flags", [])
        ))
        warnings = _build_warnings(all_flags)

        # Build document checklist (only for non-INELIGIBLE)
        doc_checklist = []
        if status not in ("INELIGIBLE",):
            for doc in scheme.get("required_documents", []):
                doc_checklist.append(DocumentItem(
                    document=doc["document"],
                    mandatory=doc.get("mandatory", True),
                    priority=doc.get("priority", 99),
                    obtainable_from=doc.get("obtainable_from", ""),
                ))
            doc_checklist.sort(key=lambda d: d.priority)

        # Extract missing fields
        missing = _extract_missing_fields(eval_result)

        # Rule evaluation trace (flattened for display)
        rule_evals = _flatten_evaluation(eval_result)

        match = MatchResult(
            scheme_id=scheme["scheme_id"],
            scheme_name=scheme["scheme_name"],
            ministry=scheme.get("ministry", ""),
            benefit=scheme.get("benefit", ""),
            application_url=scheme.get("application_portal", ""),
            status=status,
            confidence=eval_result.confidence,
            confidence_label=conf_label,
            rule_evaluations=rule_evals,
            document_checklist=doc_checklist,
            warnings=warnings,
            missing_fields=missing,
        )

        results.append(match)

    # Sort by status priority, then confidence
    status_order = {
        "FULLY_ELIGIBLE": 0,
        "LIKELY_ELIGIBLE": 1,
        "ALMOST_ELIGIBLE": 2,
        "UNCERTAIN": 3,
        "INELIGIBLE": 4,
    }
    results.sort(key=lambda r: (status_order.get(r.status, 9), -r.confidence))

    return results


# ── Summary renderer ──────────────────────────────────────────────────────────

def render_summary(results: list[MatchResult]) -> str:
    """
    Render a human-readable summary of match results.
    """
    lines = []

    fully    = [r for r in results if r.status == "FULLY_ELIGIBLE"]
    likely   = [r for r in results if r.status == "LIKELY_ELIGIBLE"]
    almost   = [r for r in results if r.status == "ALMOST_ELIGIBLE"]
    uncertain = [r for r in results if r.status == "UNCERTAIN"]
    inelig   = [r for r in results if r.status == "INELIGIBLE"]

    def _conf_bar(c: float) -> str:
        filled = int(c * 10)
        return "█" * filled + "░" * (10 - filled) + f" {c:.0%}"

    if fully:
        lines.append("═" * 60)
        lines.append("  FULLY ELIGIBLE SCHEMES")
        lines.append("═" * 60)
        for r in fully:
            lines.append(f"\n  ✓ {r.scheme_name}")
            lines.append(f"    Confidence : {_conf_bar(r.confidence)}")
            lines.append(f"    Benefit    : {r.benefit}")
            lines.append(f"    Apply at   : {r.application_url}")
            if r.warnings:
                for w in r.warnings:
                    lines.append(f"    ⚠  {w}")

    if likely:
        lines.append("\n" + "═" * 60)
        lines.append("  LIKELY ELIGIBLE (verify before applying)")
        lines.append("═" * 60)
        for r in likely:
            lines.append(f"\n  ~ {r.scheme_name}")
            lines.append(f"    Confidence : {_conf_bar(r.confidence)}")
            lines.append(f"    Benefit    : {r.benefit}")
            if r.warnings:
                for w in r.warnings:
                    lines.append(f"    ⚠  {w}")

    if almost:
        lines.append("\n" + "═" * 60)
        lines.append("  ALMOST ELIGIBLE (1 gap to close)")
        lines.append("═" * 60)
        for r in almost:
            lines.append(f"\n  ◌ {r.scheme_name}")
            lines.append(f"    Benefit    : {r.benefit}")
            if r.gap_analysis:
                lines.append("    Gap        :")
                for g in r.gap_analysis:
                    lines.append(f"      - {g.rule_description}: {g.required_description}")
                    if g.actionable:
                        lines.append(f"        → {g.action_hint}")

    if uncertain:
        lines.append("\n" + "═" * 60)
        lines.append("  UNCERTAIN (more information needed)")
        lines.append("═" * 60)
        for r in uncertain:
            lines.append(f"\n  ? {r.scheme_name}")
            if r.missing_fields:
                lines.append(f"    Need       : {', '.join(r.missing_fields)}")

    lines.append("\n" + "═" * 60)
    lines.append(f"  {len(fully)} fully eligible  |  {len(likely)} likely  |  {len(almost)} almost  |  {len(uncertain)} uncertain  |  {len(inelig)} ineligible")
    lines.append("═" * 60)

    return "\n".join(lines)
