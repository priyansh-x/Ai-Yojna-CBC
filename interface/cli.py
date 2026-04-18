"""
interface/cli.py

Main conversational CLI for the welfare scheme eligibility engine.

Conversation flow:
  1. Greeting in Hinglish
  2. User describes their situation freely (Hindi/English/Hinglish)
  3. System extracts fields, asks intelligent follow-ups
  4. Runs partial match once minimum fields collected
  5. Asks targeted questions to resolve uncertain schemes
  6. Outputs final results: eligible schemes, gaps, document checklist,
     application sequence — all in Hinglish with plain-language explanations
  7. Contradictions surfaced and resolved before final output

Usage:
  cd /Users/priyanshjoshi/Desktop/cbc
  python -m interface.cli

  With API key:
  GEMINI_API_KEY=AIzaSy... python -m interface.cli

  Demo mode (no API key):
  python -m interface.cli --demo
"""

from __future__ import annotations

import os
import sys
import json
import re
import textwrap
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.matcher import match_profile, render_summary, MatchResult
from engine.gap_analyzer import analyze_gaps
from engine.document_checklist import build_unified_checklist, render_checklist
from engine.prerequisite_sequencer import build_application_sequence, render_sequence
from interface.hinglish_handler import extract_fields_from_text
from interface.question_generator import (
    get_next_questions, has_minimum_profile, has_good_profile,
    profile_completeness_pct, Question
)
from interface.contradiction_detector import detect_contradictions, format_contradiction_for_cli

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# ── Terminal color helpers (no external deps) ─────────────────────────────────

def _c(text: str, code: str) -> str:
    """Wrap text in ANSI color code."""
    codes = {
        "cyan":    "\033[96m",
        "green":   "\033[92m",
        "yellow":  "\033[93m",
        "red":     "\033[91m",
        "bold":    "\033[1m",
        "dim":     "\033[2m",
        "reset":   "\033[0m",
    }
    return f"{codes.get(code, '')}{text}{codes['reset']}"


def _print_banner():
    print("\n" + "═" * 62)
    print(_c("  SARKARI YOJANA MATCHER — Welfare Scheme Eligibility Engine", "cyan"))
    print(_c("  Aapki Yojana, Aapka Haq. (Your scheme, your right.)", "dim"))
    print("═" * 62)
    print()


def _print_divider():
    print(_c("  ─" * 31, "dim"))


def _wrap(text: str, width: int = 58, indent: str = "  ") -> str:
    """Wrap text for terminal display."""
    lines = []
    for para in text.split("\n"):
        if para.strip():
            wrapped = textwrap.wrap(para, width=width)
            lines.extend(f"{indent}{line}" for line in wrapped)
        else:
            lines.append("")
    return "\n".join(lines)


def _speak(text: str, color: str = ""):
    """Print a system message."""
    if color:
        print(_c(_wrap(text), color))
    else:
        print(_wrap(text))
    print()


def _ask(prompt: str) -> str:
    """Get user input."""
    print(_c(f"  ❯ {prompt}", "cyan"))
    try:
        response = input("    > ").strip()
        print()
        return response
    except (KeyboardInterrupt, EOFError):
        print("\n\n  Alvida! (Goodbye!)\n")
        sys.exit(0)


# ── Session logger ─────────────────────────────────────────────────────────────

class SessionLog:
    """Records the conversation for debugging and the prompt log."""

    def __init__(self):
        self.turns: list[dict] = []
        self.start_time = datetime.now().isoformat()

    def add(self, role: str, text: str, extracted: dict = None):
        self.turns.append({
            "role": role,
            "text": text,
            "extracted_fields": extracted or {},
            "timestamp": datetime.now().isoformat(),
        })

    def get_history(self) -> list[dict]:
        """Return conversation history for the Hinglish handler."""
        return [{"role": t["role"], "content": t["text"]} for t in self.turns]


# ── Results rendering ─────────────────────────────────────────────────────────

STATUS_LABELS = {
    "FULLY_ELIGIBLE":  ("✓", "green",  "ELIGIBLE hain"),
    "LIKELY_ELIGIBLE": ("~", "yellow", "SHAYAD eligible hain"),
    "ALMOST_ELIGIBLE": ("◌", "yellow", "LAGBHAG eligible hain — ek gap hai"),
    "UNCERTAIN":       ("?", "cyan",   "PATA NAHI — aur jaankari chahiye"),
    "INELIGIBLE":      ("✗", "red",    "ELIGIBLE NAHI hain"),
}


def _render_results_hinglish(results: list[MatchResult], profile: dict) -> None:
    """Render match results in Hinglish."""

    eligible   = [r for r in results if r.status in ("FULLY_ELIGIBLE", "LIKELY_ELIGIBLE")]
    almost     = [r for r in results if r.status == "ALMOST_ELIGIBLE"]
    uncertain  = [r for r in results if r.status == "UNCERTAIN"]
    ineligible = [r for r in results if r.status == "INELIGIBLE"]

    print("\n" + "═" * 62)
    print(_c("  AAPKE LIYE YOJANAEN (Schemes for you)", "bold"))
    print("═" * 62)

    # Eligible schemes
    if eligible:
        print(_c("\n  ✓ AAPKE LIYE CONFIRMED YOJANAEN:", "green"))
        for r in eligible:
            icon, color, label = STATUS_LABELS[r.status]
            conf_bar = "█" * int(r.confidence * 10) + "░" * (10 - int(r.confidence * 10))
            print(f"\n  {_c(icon + ' ' + r.scheme_name, color)}")
            print(f"    Confidence : [{conf_bar}] {r.confidence:.0%}")
            print(f"    Faayda     : {r.benefit[:80]}...")
            print(f"    Apply karen: {r.application_url}")
            if r.warnings:
                for w in r.warnings[:2]:
                    ambig_id = re.search(r"AMBIGUITY-\d+", w)
                    print(_c(f"    ⚠  {w[w.find(']')+2:]}", "yellow"))

    # Almost eligible
    if almost:
        print(_c("\n  ◌ LAGBHAG ELIGIBLE — ek cheez ki zaroorat hai:", "yellow"))
        for r in almost:
            print(f"\n  ◌ {r.scheme_name}")
            print(f"    Faayda : {r.benefit[:80]}...")
            # Show gap
            import json as _json
            scheme_path = os.path.join(DATA_DIR, "schemes", f"{r.scheme_id}.json")
            if os.path.exists(scheme_path):
                with open(scheme_path) as f:
                    scheme_data = _json.load(f)
                gaps = analyze_gaps(scheme_data, profile)
                for g in gaps[:2]:
                    print(_c(f"    Gap   : {g.rule_description}", "yellow"))
                    print(f"    Karna : {g.action_hint}")

    # Uncertain
    if uncertain:
        print(_c("\n  ? UNCERTAIN — aur jaankari dene par pata chalega:", "cyan"))
        for r in uncertain:
            missing_str = ", ".join(r.missing_fields[:3]) if r.missing_fields else "kuch fields"
            print(f"  ? {r.scheme_name} — [{missing_str}] bata den to confirm ho sakta hai")

    # Summary line
    print("\n" + "═" * 62)
    summary_hi = (
        f"  {len(eligible)} yojana confirm | "
        f"{len(almost)} mein ek gap | "
        f"{len(uncertain)} ke liye aur jaankari chahiye | "
        f"{len(ineligible)} ke liye eligible nahi"
    )
    print(summary_hi)
    print("═" * 62)


def _render_documents_hinglish(checklist) -> None:
    """Render document checklist in Hinglish."""
    if not checklist:
        return

    print("\n" + "═" * 62)
    print(_c("  DOCUMENTS KI LIST (pehle yeh taiyaar karen)", "bold"))
    print("═" * 62)
    print("  [*] = Zaroor chahiye  [ ] = Optional\n")

    for i, doc in enumerate(checklist, 1):
        mark = "[*]" if doc.mandatory else "[ ]"
        universal = " ← sabke liye zaroor" if doc.universal else ""
        print(f"  {i:2}. {mark} {doc.document}{_c(universal, 'dim')}")
        print(f"       Kahan milega: {doc.obtainable_from}")
    print()


def _render_sequence_hinglish(steps) -> None:
    """Render application sequence in Hinglish."""
    if not steps:
        return

    print("═" * 62)
    print(_c("  APPLY KARNE KA ORDER (yeh sequence follow karen)", "bold"))
    print("═" * 62)
    print()

    for step in steps:
        prereq_note = _c(" [PEHLE YAHAN JANA ZAROORI HAI]", "yellow") if step.is_prerequisite else ""
        print(f"  STEP {step.step_number}: {_c(step.scheme_name, 'bold')}{prereq_note}")
        print(f"    Kyun pehle   : {step.reason}")
        print(f"    Kitna time   : {step.estimated_time}")
        if step.application_url:
            print(f"    Apply karen  : {step.application_url}")
        if step.notes:
            print(_c(f"    Note         : {step.notes}", "dim"))
        print()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_and_merge(user_input: str, profile: dict, log: SessionLog, api_key: str) -> dict:
    """Extract fields from user input, merge into profile, return new fields added."""
    log.add("user", user_input)
    extracted = extract_fields_from_text(
        user_text=user_input,
        conversation_history=log.get_history(),
        api_key=api_key,
    )
    if "_extraction_error" in extracted:
        err = extracted.pop("_extraction_error")
        _speak(
            f"[Demo mode] Field extraction via API not available: {err}\n"
            "Using basic pattern matching instead.",
            color="yellow"
        )
    new_fields = {k: v for k, v in extracted.items() if v is not None and not k.startswith("_")}
    profile.update(new_fields)
    log.add("assistant", f"Extracted: {new_fields}", extracted=new_fields)
    return new_fields


def _ask_one_question(q, profile: dict, log: SessionLog, api_key: str) -> None:
    """Print one follow-up question, collect answer, merge into profile."""
    _print_divider()
    print(f"\n  {_c('?', 'cyan')} {q.text_hinglish}")
    if q.expected_type == "choice" and q.choices:
        for j, c in enumerate(q.choices, ord('a')):
            print(f"     {chr(j)}) {c}")
    print()
    answer = _ask("Aapka jawab")
    if answer:
        _extract_and_merge(answer, profile, log, api_key)


# ── Main conversation loop ────────────────────────────────────────────────────

def run_conversation(
    api_key: str = "",
    demo_mode: bool = False,
) -> None:
    """Main conversation loop."""

    _print_banner()

    _speak(
        "Namaskar! Main aapki sarkari yojanaon mein help kar sakta hoon.\n"
        "Apni situation ek baar mein bata dijiye — jitna pata ho:\n"
        "umar, kaam, kahan rehte hain, income, zameen, bank account, ration card.\n"
        "Baad mein jo missing hoga, woh alag se poochunga.",
        color="cyan"
    )

    profile: dict = {"nationality": "indian"}
    log = SessionLog()
    asked_fields: set[str] = set()   # track which fields we've already asked about

    # ── Step 1: Get initial free-form input ────────────────────────────────────

    user_input = _ask("Aap batao (jitna pata ho likhein)...")
    if not user_input:
        _speak("Kuch nahi bataya. Phir try karein.", color="yellow")
        return

    if user_input.lower() in ("quit", "exit", "bye", "alvida"):
        _speak("Alvida!")
        return

    _speak("Samajh raha hoon...", color="dim")
    _extract_and_merge(user_input, profile, log, api_key)

    # ── Step 2: Resolve contradictions if any ─────────────────────────────────

    contradictions = detect_contradictions(profile)
    for c in contradictions:
        _print_divider()
        print(format_contradiction_for_cli(c))
        print()
        clarify = _ask("Yeh clarify karen")
        if clarify:
            _extract_and_merge(clarify, profile, log, api_key)

    # ── Step 3: Ask only for missing fields, one at a time ────────────────────

    import json as _json

    while True:
        # Run a quick match to see what's still uncertain
        if has_minimum_profile(profile):
            match_results = match_profile(profile, DATA_DIR)
            uncertain_ids = [r.scheme_id for r in match_results if r.status == "UNCERTAIN"]
            almost_ids    = [r.scheme_id for r in match_results if r.status == "ALMOST_ELIGIBLE"]
            priority_ids  = uncertain_ids + almost_ids
        else:
            priority_ids = None

        # Get next most-impactful unanswered question, skip already asked
        next_qs = get_next_questions(
            profile=profile,
            max_questions=10,   # get a bigger pool so we can skip already-asked ones
            potentially_eligible_schemes=priority_ids,
        )
        # Filter out fields we've already explicitly asked about this session
        next_qs = [q for q in next_qs if q.field not in asked_fields]

        if not next_qs:
            break   # Nothing left to ask

        # Ask the single highest-impact question
        q = next_qs[0]
        asked_fields.add(q.field)
        _ask_one_question(q, profile, log, api_key)

        # Check if profile is now good enough to stop asking
        if has_good_profile(profile):
            break

    # ── Step 4: Final match run ────────────────────────────────────────────────

    if not has_minimum_profile(profile):
        _speak(
            "Enough jaankari nahi mili match karne ke liye.\n"
            "Apne nearest Common Service Centre ya Jan Seva Kendra par jaiye.",
            color="yellow"
        )
        return

    _speak("Sab jaankari mil gayi — results nikaal raha hoon...", color="dim")
    match_results = match_profile(profile, DATA_DIR)

    # Add gap analysis to ALMOST_ELIGIBLE results
    for r in match_results:
        if r.status == "ALMOST_ELIGIBLE":
            scheme_path = os.path.join(DATA_DIR, "schemes", f"{r.scheme_id}.json")
            if os.path.exists(scheme_path):
                with open(scheme_path) as f:
                    sd = _json.load(f)
                r.gap_analysis = analyze_gaps(sd, profile)

    # ── Step 5: Show everything once ──────────────────────────────────────────

    _render_results_hinglish(match_results, profile)

    checklist = build_unified_checklist(match_results)
    if checklist:
        _render_documents_hinglish(checklist)

    eligible_ids = [
        r.scheme_id for r in match_results
        if r.status in ("FULLY_ELIGIBLE", "LIKELY_ELIGIBLE", "ALMOST_ELIGIBLE")
    ]
    if eligible_ids:
        seq = build_application_sequence(eligible_ids, match_results, DATA_DIR)
        _render_sequence_hinglish(seq)

    _print_divider()
    _speak(
        "ZAROOR YAAD RAKHEN:\n"
        "Yeh system ek guide hai — final eligibility government verify karegi.\n"
        "Agar koi scheme UNCERTAIN dikhi hai, apne nearest:\n"
        "  • Common Service Centre (CSC)\n"
        "  • Jan Seva Kendra\n"
        "  • Block Development Office (BDO)\n"
        "par jakar verify karein.\n\n"
        "Yeh system kabhi bhi galat confident answer nahi deta — "
        "jab pata nahi, toh clearly kehta hai 'UNCERTAIN'.",
        color="dim"
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    demo_mode = "--demo" in sys.argv
    api_key = os.environ.get("GEMINI_API_KEY", "")

    if not api_key and not demo_mode:
        print(_c(
            "\n  Note: GEMINI_API_KEY not set. Running in demo mode "
            "(basic pattern extraction only).\n"
            "  For full Hinglish understanding: export GEMINI_API_KEY=AIzaSy...\n",
            "yellow"
        ))
        demo_mode = True

    run_conversation(api_key=api_key, demo_mode=demo_mode)


if __name__ == "__main__":
    main()
