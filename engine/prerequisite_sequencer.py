"""
engine/prerequisite_sequencer.py

Topological sort of the prerequisites graph to produce the correct
application sequence for a user's set of eligible schemes.

The prerequisites graph (data/prerequisites_graph.json) is a DAG where
an edge A → B means: apply for A before B.

The sequencer:
  1. Loads the graph
  2. Filters to only the schemes relevant to this user
  3. Topologically sorts them
  4. Returns an ordered list of application steps with explanations

If a prerequisite is not in the user's eligible set but IS needed,
it is added as a "required enabler" step.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ApplicationStep:
    step_number: int
    scheme_id: str
    scheme_name: str
    reason: str             # Why this comes at this position
    is_prerequisite: bool   # True if user wasn't directly matched — added as enabler
    application_url: str
    estimated_time: str     # Rough guidance on processing time
    notes: str


# ── Topo sort ─────────────────────────────────────────────────────────────────

def _build_adjacency(edges: list[dict], relevant_ids: set[str]) -> dict[str, list[str]]:
    """
    Build adjacency list (from → [to]) for nodes in relevant_ids.
    Also pulls in prerequisite nodes even if not in relevant_ids.
    """
    adj: dict[str, list[str]] = {node_id: [] for node_id in relevant_ids}
    in_degree: dict[str, int] = {node_id: 0 for node_id in relevant_ids}

    for edge in edges:
        frm = edge["from"]
        to  = edge["to"]
        if to in relevant_ids:
            # Ensure prerequisite is in the graph even if not directly eligible
            if frm not in adj:
                adj[frm] = []
                in_degree[frm] = 0
            adj[frm].append(to)
            in_degree[to] = in_degree.get(to, 0) + 1

    return adj, in_degree


def _kahn_topological_sort(adj: dict, in_degree: dict) -> list[str]:
    """
    Kahn's algorithm for topological sort.
    Returns nodes in application order (dependencies first).
    """
    from collections import deque

    queue = deque(node for node, deg in in_degree.items() if deg == 0)
    order = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbour in adj.get(node, []):
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if len(order) != len(in_degree):
        # Cycle detected — should not happen in a valid DAG
        # Return partial order + remaining nodes
        remaining = [n for n in in_degree if n not in order]
        order.extend(remaining)

    return order


# ── Time estimates ─────────────────────────────────────────────────────────────

PROCESSING_TIMES = {
    "pm_jan_dhan":           "Same day (at bank branch)",
    "pm_suraksha_bima":      "Same day (at bank branch)",
    "pm_jeevan_jyoti_bima":  "Same day (at bank branch)",
    "mgnrega":               "1–4 weeks (Job Card issuance)",
    "pm_kisan":              "2–4 weeks (state verification)",
    "pm_ujjwala":            "1–2 weeks (distributor processing)",
    "pmgkay":                "Varies by state (ration card: weeks to months)",
    "ayushman_bharat":       "Instant if SECC-listed (Ayushman Card at CSC/hospital)",
    "pmay_gramin":           "3–6 months (state allocation and construction)",
    "pmay_urban":            "3–12 months (loan processing + subsidy credit)",
    "nsap":                  "1–3 months (state verification of BPL/age)",
    "pm_matru_vandana":      "1–2 weeks (Anganwadi registration)",
    "sukanya_samriddhi":     "Same day (at Post Office or bank)",
    "pm_shram_yogi_mandhan": "Same day (at CSC with bank auto-debit setup)",
    "atal_pension_yojana":   "Same day (at bank branch)",
    "pm_mudra":              "2–4 weeks (bank credit assessment)",
    "pm_fasal_bima":         "Before seasonal cut-off date (check local agriculture office)",
    "pm_kisan_credit_card":  "1–2 weeks (bank processing)",
}


SCHEME_NOTES = {
    "pm_jan_dhan":           "Open first — most other schemes deposit money here.",
    "ayushman_bharat":       "Check SECC status at pmjay.gov.in before visiting hospital.",
    "pm_fasal_bima":         "Enrollment has seasonal cut-off dates — act before Kharif/Rabi sowing.",
    "pm_kisan_credit_card":  "Having a KCC auto-enrolls you in PMFBY crop insurance.",
    "mgnrega":               "You can apply for work within 15 days of registering.",
    "pm_mudra":              "Approach your bank with a basic business plan.",
}


# ── Main sequencer ─────────────────────────────────────────────────────────────

def build_application_sequence(
    eligible_scheme_ids: list[str],
    all_match_results,        # list[MatchResult] — for scheme name/URL lookup
    data_dir: str,
) -> list[ApplicationStep]:
    """
    Given a list of scheme IDs the user is eligible for, return the
    recommended application sequence in topological order.

    Args:
        eligible_scheme_ids: Scheme IDs to sequence
        all_match_results: Full match results for name/URL lookup
        data_dir: Path to data/ directory

    Returns:
        Ordered list of ApplicationStep
    """
    graph_path = os.path.join(data_dir, "prerequisites_graph.json")
    with open(graph_path, "r", encoding="utf-8") as f:
        graph = json.load(f)

    nodes_map = {n["id"]: n for n in graph["nodes"]}
    edges = graph["edges"]

    # Build scheme_id → MatchResult lookup
    result_map = {r.scheme_id: r for r in all_match_results}

    eligible_set = set(eligible_scheme_ids)

    # Build graph and topo-sort
    adj, in_degree = _build_adjacency(edges, eligible_set)
    ordered_ids = _kahn_topological_sort(adj, in_degree)

    # Annotate each step
    steps = []
    for i, scheme_id in enumerate(ordered_ids, 1):
        node_info = nodes_map.get(scheme_id, {})
        result    = result_map.get(scheme_id)
        is_prereq = scheme_id not in eligible_set  # Added as an enabler, not directly eligible

        if result:
            name = result.scheme_name
            url  = result.application_url
        else:
            name = node_info.get("name", scheme_id)
            url  = ""

        # Determine reason for this position
        predecessors = [e["from"] for e in edges if e["to"] == scheme_id and e["from"] in ordered_ids]
        if predecessors:
            pred_names = [nodes_map.get(p, {}).get("name", p) for p in predecessors if p in eligible_set or p in [e2["from"] for e2 in edges]]
            reason = f"Requires: {', '.join(pred_names)}" if pred_names else "Foundation step"
        elif is_prereq:
            reason = "Required enabler — other schemes depend on this"
        else:
            reason = "No dependencies — can apply immediately"

        step = ApplicationStep(
            step_number=i,
            scheme_id=scheme_id,
            scheme_name=name,
            reason=reason,
            is_prerequisite=is_prereq,
            application_url=url,
            estimated_time=PROCESSING_TIMES.get(scheme_id, "Varies"),
            notes=SCHEME_NOTES.get(scheme_id, ""),
        )
        steps.append(step)

    return steps


def render_sequence(steps: list[ApplicationStep]) -> str:
    """Render the application sequence as a human-readable string."""
    lines = []
    lines.append("═" * 60)
    lines.append("  APPLICATION SEQUENCE (do these in order)")
    lines.append("═" * 60)
    lines.append("")

    for step in steps:
        prereq_tag = " [ENABLER — required first]" if step.is_prerequisite else ""
        lines.append(f"  STEP {step.step_number}: {step.scheme_name}{prereq_tag}")
        lines.append(f"    Why now     : {step.reason}")
        lines.append(f"    Time        : {step.estimated_time}")
        if step.application_url:
            lines.append(f"    Apply at    : {step.application_url}")
        if step.notes:
            lines.append(f"    Note        : {step.notes}")
        lines.append("")

    return "\n".join(lines)
