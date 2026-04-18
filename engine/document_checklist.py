"""
engine/document_checklist.py

Builds a unified, deduplicated, priority-ordered document checklist
across ALL schemes the user is eligible or almost-eligible for.

Priority ordering logic:
  1. Documents needed for prerequisite schemes come first (e.g., Aadhaar, bank)
  2. Among equal priority, mandatory documents come before optional
  3. Documents shared across multiple schemes are shown once with a note
     listing all schemes they apply to
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from engine.matcher import MatchResult, DocumentItem


@dataclass
class UnifiedDocument:
    document: str
    mandatory: bool
    priority: int
    obtainable_from: str
    schemes_requiring: list[str]       # scheme names that need this doc
    universal: bool = False            # True if Aadhaar/bank — needed by almost everything


# ── Core document deduplication ───────────────────────────────────────────────

# Canonical document names — these are deduplicated by matching against these keys
CANONICAL_DOCS = {
    "aadhaar": ["aadhaar", "aadhar", "aadhaar card", "aadhaar / identity proof"],
    "bank_account": ["bank account", "bank account / pmjdy", "savings bank account", "bank/post office account", "bank account (linked to aadhaar)"],
    "ration_card": ["ration card", "ration card (phh/aay)", "ration card / any residence proof"],
    "income_certificate": ["income certificate", "income proof"],
    "land_records": ["land records", "land records / khasra-khatauni / patta", "land records / khasra"],
    "photograph": ["passport-size photograph", "passport photograph"],
    "birth_certificate": ["birth certificate", "girl child's birth certificate"],
    "disability_certificate": ["disability certificate"],
    "death_certificate": ["husband's death certificate"],
    "address_proof": ["address proof"],
}


def _canonical_key(doc_name: str) -> str:
    """Map a raw document name to a canonical key for deduplication."""
    lower = doc_name.lower().strip()
    for key, variants in CANONICAL_DOCS.items():
        if any(v in lower for v in variants):
            return key
    return lower  # No canonical match — use as-is


def build_unified_checklist(results: list[MatchResult]) -> list[UnifiedDocument]:
    """
    Build a unified document checklist from all non-INELIGIBLE scheme results.
    Deduplicates, merges scheme references, and sorts by priority.
    """
    eligible_statuses = {"FULLY_ELIGIBLE", "LIKELY_ELIGIBLE", "ALMOST_ELIGIBLE"}
    eligible_results = [r for r in results if r.status in eligible_statuses]

    # doc_key → UnifiedDocument
    doc_map: dict[str, UnifiedDocument] = {}

    for result in eligible_results:
        for doc in result.document_checklist:
            key = _canonical_key(doc.document)

            if key not in doc_map:
                doc_map[key] = UnifiedDocument(
                    document=doc.document,
                    mandatory=doc.mandatory,
                    priority=doc.priority,
                    obtainable_from=doc.obtainable_from,
                    schemes_requiring=[result.scheme_name],
                )
            else:
                existing = doc_map[key]
                # If any scheme marks it mandatory → mark it mandatory
                if doc.mandatory:
                    existing.mandatory = True
                # Take the higher priority (lower number = higher priority)
                existing.priority = min(existing.priority, doc.priority)
                if result.scheme_name not in existing.schemes_requiring:
                    existing.schemes_requiring.append(result.scheme_name)

    # Mark universal docs
    total_schemes = len(eligible_results)
    for doc in doc_map.values():
        if len(doc.schemes_requiring) >= max(2, total_schemes // 2):
            doc.universal = True

    # Sort: mandatory first, then by priority, then by number of schemes requiring
    sorted_docs = sorted(
        doc_map.values(),
        key=lambda d: (
            0 if d.mandatory else 1,
            d.priority,
            -len(d.schemes_requiring),
        )
    )

    return sorted_docs


def render_checklist(checklist: list[UnifiedDocument]) -> str:
    """Render the checklist as a human-readable string."""
    lines = []
    lines.append("═" * 60)
    lines.append("  DOCUMENT CHECKLIST (priority order)")
    lines.append("═" * 60)
    lines.append("  Gather these documents before applying.")
    lines.append("  Documents marked [*] are mandatory for most schemes.\n")

    for i, doc in enumerate(checklist, 1):
        mandatory_mark = "[*]" if doc.mandatory else "[ ]"
        universal_note = " ← needed by everything" if doc.universal else ""
        schemes_note = f" (for: {', '.join(doc.schemes_requiring[:3])}{'...' if len(doc.schemes_requiring) > 3 else ''})"

        lines.append(f"  {i:2}. {mandatory_mark} {doc.document}{universal_note}")
        lines.append(f"       Get from : {doc.obtainable_from}")
        lines.append(f"       Used for : {schemes_note.strip()}")
        lines.append("")

    return "\n".join(lines)
