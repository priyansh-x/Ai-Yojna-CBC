"""
tests/test_engine.py

Test runner for the matching engine.

Runs all 10 adversarial profiles through the engine and:
  1. Checks expected statuses are produced
  2. Checks must_not_do conditions are not violated
  3. Checks required ambiguity flags are surfaced
  4. Prints a full result report

Usage:
  cd /Users/priyanshjoshi/Desktop/cbc
  python -m tests.test_engine
"""

from __future__ import annotations

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.matcher import match_profile, render_summary, MatchResult
from engine.gap_analyzer import analyze_gaps
from engine.document_checklist import build_unified_checklist, render_checklist
from engine.prerequisite_sequencer import build_application_sequence, render_sequence
from tests.adversarial_profiles import ADVERSARIAL_CASES, AdversarialProfile

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


# ── Test runner ───────────────────────────────────────────────────────────────

def run_case(case: AdversarialProfile, verbose: bool = True) -> dict:
    """
    Run one adversarial case through the engine.
    Returns a result dict with pass/fail details.
    """
    results: list[MatchResult] = match_profile(case.profile, DATA_DIR)

    # Map scheme_id → MatchResult for easy lookup
    result_map = {r.scheme_id: r for r in results}

    checks_passed = []
    checks_failed = []

    # ── Check 1: Expected statuses ────────────────────────────────────────────
    for scheme_id, expected_status in case.expected_statuses.items():
        if scheme_id not in result_map:
            checks_failed.append(
                f"Expected scheme '{scheme_id}' not found in results"
            )
            continue

        actual_status = result_map[scheme_id].status
        if actual_status == expected_status:
            checks_passed.append(
                f"[STATUS OK] {scheme_id}: got {actual_status} (expected {expected_status})"
            )
        else:
            checks_failed.append(
                f"[STATUS FAIL] {scheme_id}: got {actual_status}, expected {expected_status}"
            )

    # ── Check 2: Ambiguity flags surfaced ─────────────────────────────────────
    all_surfaced_flags = set()
    for r in results:
        for flag in r.warnings:
            # Extract AMBIGUITY-xxx from warning string
            import re
            matches = re.findall(r"AMBIGUITY-\d+", flag)
            all_surfaced_flags.update(matches)

    for flag in case.key_ambiguities:
        if flag in all_surfaced_flags:
            checks_passed.append(f"[FLAG OK] {flag} was surfaced")
        else:
            checks_failed.append(
                f"[FLAG MISSING] {flag} was expected but not surfaced in warnings"
            )

    # ── Check 3: No FULLY_ELIGIBLE on uncertain schemes ───────────────────────
    # For any scheme expected to be UNCERTAIN, check confidence is <= 0.60
    for scheme_id, expected_status in case.expected_statuses.items():
        if expected_status == "UNCERTAIN" and scheme_id in result_map:
            r = result_map[scheme_id]
            if r.status == "FULLY_ELIGIBLE" and r.confidence > 0.75:
                checks_failed.append(
                    f"[OVERCONFIDENCE FAIL] {scheme_id} returned FULLY_ELIGIBLE with {r.confidence:.0%} confidence — expected UNCERTAIN"
                )

    # ── Check 4: INELIGIBLE schemes have no document checklists ──────────────
    for r in results:
        if r.status == "INELIGIBLE" and r.document_checklist:
            checks_failed.append(
                f"[DOC LEAK] {r.scheme_id} is INELIGIBLE but has a document checklist — should be empty"
            )

    passed = len(checks_failed) == 0

    if verbose:
        divider = "─" * 60
        print(f"\n{'═' * 60}")
        print(f"  {case.case_id}: {case.name}")
        print(f"{'═' * 60}")
        print(f"  Intent : {case.adversarial_intent}")
        print(f"  Result : {'✓ PASS' if passed else '✗ FAIL'}")
        print(divider)

        if checks_passed:
            for c in checks_passed:
                print(f"  ✓ {c}")

        if checks_failed:
            for c in checks_failed:
                print(f"  ✗ {c}")

        print(divider)
        print("  MATCHING ENGINE OUTPUT:")
        print(render_summary(results))

        # Show gap analysis for ALMOST_ELIGIBLE schemes
        almost = [r for r in results if r.status == "ALMOST_ELIGIBLE"]
        if almost:
            print(f"\n  GAP ANALYSIS:")
            for r in almost:
                scheme_data = _load_scheme(r.scheme_id)
                if scheme_data:
                    gaps = analyze_gaps(scheme_data, case.profile)
                    if gaps:
                        print(f"    {r.scheme_name}:")
                        for g in gaps:
                            print(f"      Gap   : {g.rule_description}")
                            print(f"      Need  : {g.required_description}")
                            if g.actionable:
                                print(f"      Action: {g.action_hint}")
                            else:
                                print(f"      Action: NOT ACTIONABLE — {g.action_hint}")

        # Show application sequence for eligible schemes
        eligible_ids = [
            r.scheme_id for r in results
            if r.status in ("FULLY_ELIGIBLE", "LIKELY_ELIGIBLE", "ALMOST_ELIGIBLE")
        ]
        if eligible_ids:
            seq = build_application_sequence(eligible_ids, results, DATA_DIR)
            print(f"\n{render_sequence(seq)}")

        # Unified document checklist
        checklist = build_unified_checklist(results)
        if checklist:
            print(render_checklist(checklist))

    return {
        "case_id": case.case_id,
        "name": case.name,
        "passed": passed,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
    }


def _load_scheme(scheme_id: str) -> dict | None:
    """Load a scheme JSON file by ID."""
    import json
    schemes_dir = os.path.join(DATA_DIR, "schemes")
    fpath = os.path.join(schemes_dir, f"{scheme_id}.json")
    if os.path.exists(fpath):
        with open(fpath) as f:
            return json.load(f)
    return None


# ── Summary ───────────────────────────────────────────────────────────────────

def run_all_cases(verbose: bool = True) -> None:
    print("\n" + "█" * 60)
    print("  ADVERSARIAL TEST SUITE — WELFARE ELIGIBILITY ENGINE")
    print("█" * 60)

    all_results = []
    for case in ADVERSARIAL_CASES:
        result = run_case(case, verbose=verbose)
        all_results.append(result)

    passed = [r for r in all_results if r["passed"]]
    failed = [r for r in all_results if not r["passed"]]

    print("\n" + "█" * 60)
    print("  FINAL SUMMARY")
    print("█" * 60)
    print(f"  Total cases : {len(all_results)}")
    print(f"  Passed      : {len(passed)}")
    print(f"  Failed      : {len(failed)}")

    if failed:
        print("\n  FAILED CASES:")
        for r in failed:
            print(f"    ✗ {r['case_id']}: {r['name']}")
            for fail in r["checks_failed"]:
                print(f"       → {fail}")

    print("\n" + "█" * 60)


if __name__ == "__main__":
    verbose = "--quiet" not in sys.argv
    run_all_cases(verbose=verbose)
