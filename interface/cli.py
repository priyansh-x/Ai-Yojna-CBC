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
import time
import threading
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

# ── Terminal color + style helpers ────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
ITALIC = "\033[3m"

# Foreground colors
BLACK   = "\033[30m"
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
WHITE   = "\033[97m"

# Background colors
BG_CYAN    = "\033[46m"
BG_GREEN   = "\033[42m"
BG_YELLOW  = "\033[43m"
BG_RED     = "\033[41m"
BG_BLUE    = "\033[44m"

def _c(text: str, code: str) -> str:
    codes = {
        "cyan":    CYAN,
        "green":   GREEN,
        "yellow":  YELLOW,
        "red":     RED,
        "bold":    BOLD,
        "dim":     DIM,
        "magenta": MAGENTA,
        "white":   WHITE,
        "reset":   RESET,
    }
    return f"{codes.get(code, '')}{text}{RESET}"


# ── Logo & Banner ─────────────────────────────────────────────────────────────

LOGO = f"""
{CYAN}{BOLD}
  ██╗   ██╗ ██████╗      ██╗███╗   ██╗ █████╗       █████╗ ██╗
  ╚██╗ ██╔╝██╔═══██╗     ██║████╗  ██║██╔══██╗     ██╔══██╗██║
   ╚████╔╝ ██║   ██║     ██║██╔██╗ ██║███████║     ███████║██║
    ╚██╔╝  ██║   ██║██   ██║██║╚██╗██║██╔══██║     ██╔══██║██║
     ██║   ╚██████╔╝╚█████╔╝██║ ╚████║██║  ██║  ██╗██║  ██║██║
     ╚═╝    ╚═════╝  ╚════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝
{RESET}{DIM}
        Aapki Yojana, Aapka Haq  •  Your Scheme, Your Right
        India's Welfare Scheme Eligibility Engine
{RESET}"""

def _print_banner():
    os.system("clear")
    print(LOGO)
    print(f"  {DIM}{'─' * 66}{RESET}")
    print()


def _print_divider(label: str = ""):
    if label:
        pad = (60 - len(label) - 2) // 2
        print(f"\n  {DIM}{'─' * pad}{RESET} {CYAN}{label}{RESET} {DIM}{'─' * pad}{RESET}\n")
    else:
        print(f"\n  {DIM}{'─' * 64}{RESET}\n")


def _section(title: str, color: str = CYAN):
    width = 64
    bar = "═" * width
    print(f"\n  {color}{BOLD}{bar}{RESET}")
    print(f"  {color}{BOLD}  {title}{RESET}")
    print(f"  {color}{BOLD}{bar}{RESET}\n")


def _wrap(text: str, width: int = 60, indent: str = "  ") -> str:
    lines = []
    for para in text.split("\n"):
        if para.strip():
            wrapped = textwrap.wrap(para, width=width)
            lines.extend(f"{indent}{line}" for line in wrapped)
        else:
            lines.append("")
    return "\n".join(lines)


def _speak(text: str, color: str = "", prefix: str = ""):
    """Print a system message with optional bot prefix."""
    icon = f"{CYAN}◈{RESET}  " if not prefix else prefix
    color_map = {"cyan": CYAN, "green": GREEN, "yellow": YELLOW,
                 "red": RED, "dim": DIM, "magenta": MAGENTA}
    col = color_map.get(color, "")
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip():
            wrapped = textwrap.wrap(line, width=60)
            for j, wl in enumerate(wrapped):
                lead = icon if (i == 0 and j == 0) else "   "
                print(f"  {lead}{col}{wl}{RESET}")
        else:
            print()
    print()


def _ask(prompt: str, hint: str = "") -> str:
    """Styled user input prompt."""
    if hint:
        print(f"  {DIM}{hint}{RESET}")
    print(f"  {CYAN}╭─ {prompt}{RESET}")
    print(f"  {CYAN}╰❯{RESET} ", end="")
    try:
        response = input("").strip()
        print()
        return response
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n  {YELLOW}Alvida! Phir milenge.{RESET}\n")
        sys.exit(0)


# ── Spinner ───────────────────────────────────────────────────────────────────

class Spinner:
    """Simple single-threaded spinner — no background threads that corrupt terminal input."""

    def __init__(self, message: str):
        self.message = message

    def __enter__(self):
        print(f"  {CYAN}◌{RESET}  {DIM}{self.message}...{RESET}", flush=True)
        return self

    def __exit__(self, *_):
        # Move up one line and replace with done tick
        print(f"\033[1A\033[2K  {GREEN}✓{RESET}  {DIM}{self.message}{RESET}")


# ── Progress bar ──────────────────────────────────────────────────────────────

def _progress_bar(pct: int, label: str = "") -> str:
    filled = int(pct / 5)   # out of 20 blocks
    bar = f"{GREEN}{'█' * filled}{DIM}{'░' * (20 - filled)}{RESET}"
    return f"  [{bar}] {CYAN}{pct}%{RESET}  {DIM}{label}{RESET}"


# ── Typing effect ─────────────────────────────────────────────────────────────

def _typewrite(text: str, delay: float = 0.018):
    """Print text with a subtle typewriter effect."""
    for char in text:
        print(char, end="", flush=True)
        time.sleep(delay)
    print()


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

STATUS_CONFIG = {
    "FULLY_ELIGIBLE":  {"icon": "✦", "color": GREEN,  "bg": "",        "label": "ELIGIBLE"},
    "LIKELY_ELIGIBLE": {"icon": "◉", "color": CYAN,   "bg": "",        "label": "LIKELY ELIGIBLE"},
    "ALMOST_ELIGIBLE": {"icon": "◎", "color": YELLOW, "bg": "",        "label": "1 GAP BAAKI"},
    "UNCERTAIN":       {"icon": "◌", "color": DIM,    "bg": "",        "label": "AUR JAANKARI CHAHIYE"},
    "INELIGIBLE":      {"icon": "✗", "color": RED,    "bg": "",        "label": "ELIGIBLE NAHI"},
}


def _conf_bar(confidence: float) -> str:
    filled = int(confidence * 12)
    bar = f"{GREEN}{'█' * filled}{DIM}{'░' * (12 - filled)}{RESET}"
    pct = f"{BOLD}{int(confidence * 100)}%{RESET}"
    return f"[{bar}] {pct}"


def _render_results_hinglish(results: list[MatchResult], profile: dict) -> None:
    """Render match results in Hinglish."""
    import json as _json

    eligible   = [r for r in results if r.status in ("FULLY_ELIGIBLE", "LIKELY_ELIGIBLE")]
    almost     = [r for r in results if r.status == "ALMOST_ELIGIBLE"]
    uncertain  = [r for r in results if r.status == "UNCERTAIN"]
    ineligible = [r for r in results if r.status == "INELIGIBLE"]

    _section("AAPKE LIYE YOJANAEN  ·  Your Eligible Schemes", GREEN)

    # ── Eligible ──────────────────────────────────────────────────────────────
    if eligible:
        print(f"  {GREEN}{BOLD}✦  AAPKO MILNE WALI YOJANAEN{RESET}\n")
        for r in eligible:
            cfg = STATUS_CONFIG[r.status]
            badge = f"{cfg['color']}{BOLD} {cfg['label']} {RESET}"
            print(f"  {cfg['color']}{BOLD}┌{'─'*58}┐{RESET}")
            print(f"  {cfg['color']}{BOLD}│{RESET}  {BOLD}{r.scheme_name[:52]:<52}{cfg['color']}{BOLD}│{RESET}")
            print(f"  {cfg['color']}{BOLD}└{'─'*58}┘{RESET}")
            print(f"    {DIM}Confidence{RESET}  {_conf_bar(r.confidence)}")
            benefit_lines = textwrap.wrap(r.benefit, width=56)
            print(f"    {DIM}Faayda{RESET}      {benefit_lines[0]}")
            for bl in benefit_lines[1:]:
                print(f"                {bl}")
            print(f"    {DIM}Apply karen{RESET} {CYAN}{r.application_url}{RESET}")
            if r.warnings:
                for w in r.warnings[:2]:
                    msg = w[w.find(']')+2:] if ']' in w else w
                    print(f"    {YELLOW}⚠  {msg[:70]}{RESET}")
            print()

    # ── Almost eligible ───────────────────────────────────────────────────────
    if almost:
        print(f"  {YELLOW}{BOLD}◎  EK KADAM DUR — 1 Gap Baaki{RESET}\n")
        for r in almost:
            print(f"  {YELLOW}┌{'─'*58}┐{RESET}")
            print(f"  {YELLOW}│{RESET}  {BOLD}{r.scheme_name[:52]:<52}{YELLOW}│{RESET}")
            print(f"  {YELLOW}└{'─'*58}┘{RESET}")
            print(f"    {DIM}Faayda{RESET}  {r.benefit[:70]}")
            scheme_path = os.path.join(DATA_DIR, "schemes", f"{r.scheme_id}.json")
            if os.path.exists(scheme_path):
                with open(scheme_path) as f:
                    sd = _json.load(f)
                gaps = analyze_gaps(sd, profile)
                for g in gaps[:1]:
                    print(f"    {YELLOW}Gap  {RESET}  {g.rule_description}")
                    print(f"    {CYAN}Karo {RESET}  {g.action_hint}")
            print()

    # ── Uncertain ─────────────────────────────────────────────────────────────
    if uncertain:
        print(f"  {DIM}◌  UNCERTAIN — Pata Nahi (aur jaankari se confirm ho sakta hai){RESET}\n")
        for r in uncertain:
            print(f"  {DIM}  • {r.scheme_name}{RESET}")
        print()

    # ── Summary pill row ──────────────────────────────────────────────────────
    print(f"  {'─'*64}")
    pills = [
        (len(eligible),   GREEN,  "Eligible"),
        (len(almost),     YELLOW, "1 Gap"),
        (len(uncertain),  DIM,    "Uncertain"),
        (len(ineligible), RED,    "Nahi"),
    ]
    row = "  "
    for count, col, label in pills:
        row += f"{col}{BOLD} {count} {label} {RESET}  "
    print(row)
    print(f"  {'─'*64}\n")


def _render_documents_hinglish(checklist) -> None:
    """Render document checklist in Hinglish."""
    if not checklist:
        return

    _section("DOCUMENTS KI LIST  ·  Pehle Yeh Taiyaar Karen", CYAN)
    print(f"  {GREEN}[✦]{RESET} = Zaroor chahiye   {DIM}[ ]{RESET} = Optional\n")

    for i, doc in enumerate(checklist, 1):
        if doc.mandatory:
            mark  = f"{GREEN}[✦]{RESET}"
            dname = f"{BOLD}{doc.document}{RESET}"
        else:
            mark  = f"{DIM}[ ]{RESET}"
            dname = f"{DIM}{doc.document}{RESET}"
        universal = f"  {CYAN}← sabke liye{RESET}" if doc.universal else ""
        print(f"  {i:2}. {mark} {dname}{universal}")
        print(f"       {DIM}Kahan milega:{RESET} {doc.obtainable_from}")
    print()


def _render_sequence_hinglish(steps) -> None:
    """Render application sequence in Hinglish."""
    if not steps:
        return

    _section("APPLY KARNE KA ORDER  ·  Is Sequence Mein Karein", MAGENTA)

    for step in steps:
        is_prereq = step.is_prerequisite
        num_color = YELLOW if is_prereq else CYAN
        prereq_badge = f"  {YELLOW}{BOLD}[PEHLE YAHAN JAROOR JAIYE]{RESET}" if is_prereq else ""
        print(f"  {num_color}{BOLD}STEP {step.step_number}{RESET}{prereq_badge}")
        print(f"  {BOLD}{step.scheme_name}{RESET}")
        print(f"  {DIM}{'─' * 48}{RESET}")
        print(f"  {DIM}Kyun pehle  :{RESET} {step.reason}")
        print(f"  {DIM}Time lagega :{RESET} {step.estimated_time}")
        if step.application_url:
            print(f"  {DIM}Apply karen :{RESET} {CYAN}{step.application_url}{RESET}")
        if step.notes:
            print(f"  {DIM}Note        : {step.notes}{RESET}")
        print()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_and_merge(user_input: str, profile: dict, log: SessionLog, api_key: str) -> dict:
    """Extract fields from user input, merge into profile, return new fields added."""
    log.add("user", user_input)
    with Spinner("Samajh raha hoon"):
        extracted = extract_fields_from_text(
            user_text=user_input,
            conversation_history=log.get_history(),
            api_key=api_key,
        )
    if "_extraction_error" in extracted:
        extracted.pop("_extraction_error")
        # Silent fallback — demo mode already used, no need to alarm user
    new_fields = {k: v for k, v in extracted.items() if v is not None and not k.startswith("_")}
    profile.update(new_fields)
    log.add("assistant", f"Extracted: {new_fields}", extracted=new_fields)

    # Show a friendly confirmation of what was understood
    if new_fields:
        understood = []
        labels = {
            "age": "umar", "gender": "gender", "state": "state",
            "occupation": "kaam", "residence_type": "rehne ki jagah",
            "annual_income_household": "income", "ration_card_type": "ration card",
            "land_ownership": "zameen", "has_bank_account": "bank account",
            "caste_category": "category", "family_size": "parivaar",
            "is_pregnant": "pregnancy", "marital_status": "vaivahik sthiti",
            "house_type": "ghar ka type", "disability": "viklangta",
        }
        for k, v in list(new_fields.items())[:6]:
            lbl = labels.get(k, k.replace("_", " "))
            understood.append(f"{DIM}{lbl}:{RESET} {CYAN}{v}{RESET}")
        print(f"  {GREEN}✓{RESET}  Samjha — {',  '.join(understood)}")
        print()

    return new_fields


def _ask_one_question(q, profile: dict, log: SessionLog, api_key: str) -> None:
    """Print one follow-up question, collect answer, merge into profile."""
    _print_divider(label="Ek sawaal")
    print(f"  {CYAN}{BOLD}◈{RESET}  {BOLD}{q.text_hinglish}{RESET}")
    if q.expected_type == "choice" and q.choices:
        print()
        for j, choice in enumerate(q.choices, ord('a')):
            print(f"     {CYAN}{chr(j)}{RESET})  {choice}")
    print()
    answer = _ask("Aapka jawab", hint="(kuch bhi likh sakte hain — option letter ya apni baat)")
    if answer:
        _extract_and_merge(answer, profile, log, api_key)


# ── Main conversation loop ────────────────────────────────────────────────────

def run_conversation(
    api_key: str = "",
    demo_mode: bool = False,
) -> None:
    """Main conversation loop."""

    _print_banner()

    # Typewriter greeting
    greeting = (
        f"  {CYAN}◈{RESET}  {BOLD}Namaskar! Main Yojna.ai hoon.{RESET}\n\n"
        f"  {DIM}Main aapki sarkari yojanaon mein help karta hoon —\n"
        f"  kaunsi schemes ke liye aap eligible hain, kya documents\n"
        f"  chahiye, aur kahan apply karna hai.\n\n"
        f"  {CYAN}Apni situation ek baar mein bata dijiye:{RESET}\n"
        f"  {DIM}umar, kaam, kahan rehte hain, income, zameen,\n"
        f"  bank account, ration card — jo bhi pata ho.{RESET}\n"
    )
    print(greeting)

    profile: dict = {"nationality": "indian"}
    log = SessionLog()
    asked_fields: set[str] = set()

    # ── Step 1: Get initial free-form input ────────────────────────────────────

    user_input = _ask(
        "Apni baat kaho",
        hint="Hindi, English, ya Hinglish — jo comfortable lage"
    )
    if not user_input or user_input.lower() in ("quit", "exit", "bye", "alvida"):
        print(f"\n  {YELLOW}Alvida! Phir milenge.{RESET}\n")
        return

    _extract_and_merge(user_input, profile, log, api_key)

    # ── Step 2: Resolve contradictions if any ─────────────────────────────────

    contradictions = detect_contradictions(profile)
    for c in contradictions:
        _print_divider(label="Ek clarification chahiye")
        print(f"  {YELLOW}⚠{RESET}  {format_contradiction_for_cli(c)}")
        print()
        clarify = _ask("Yeh clarify karen")
        if clarify:
            _extract_and_merge(clarify, profile, log, api_key)

    # ── Step 3: Ask only for missing fields, one at a time ────────────────────

    import json as _json

    while True:
        # Get next highest-impact unanswered question (no mid-loop match — faster)
        next_qs = get_next_questions(
            profile=profile,
            max_questions=10,
            potentially_eligible_schemes=None,
        )
        next_qs = [q for q in next_qs if q.field not in asked_fields]

        if not next_qs or has_good_profile(profile):
            break

        # Show progress bar only when there are still questions to ask
        pct = profile_completeness_pct(profile)
        print(_progress_bar(pct, f"Profile {pct}% complete — thoda aur batao"))
        print()

        # Ask the single highest-impact question
        q = next_qs[0]
        asked_fields.add(q.field)
        _ask_one_question(q, profile, log, api_key)

    # ── Step 4: Final match run ────────────────────────────────────────────────

    if not has_minimum_profile(profile):
        print(f"\n  {YELLOW}⚠  Enough jaankari nahi mili.{RESET}")
        print(f"  {DIM}Apne nearest Common Service Centre ya Jan Seva Kendra par jaiye.{RESET}\n")
        return

    print()
    with Spinner("Aapke liye 18 schemes check kar raha hoon"):
        match_results = match_profile(profile, DATA_DIR)
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

    # ── Disclaimer ────────────────────────────────────────────────────────────

    print(f"  {DIM}{'═' * 64}{RESET}")
    print(f"  {CYAN}{BOLD}  ◈  ZAROOR YAAD RAKHEN{RESET}")
    print(f"  {DIM}{'═' * 64}{RESET}\n")
    notes = [
        "Yeh system ek guide hai — final eligibility government verify karegi.",
        "UNCERTAIN results ke liye in jagahon par jaiye:",
        "  •  Common Service Centre (CSC)  •  Jan Seva Kendra",
        "  •  Block Development Office (BDO)",
        "",
        "Yojna.ai kabhi bhi galat confident answer nahi deta.",
        "Jab pata nahi — clearly kehta hai UNCERTAIN.",
    ]
    for note in notes:
        print(f"  {DIM}{note}{RESET}")
    print(f"\n  {DIM}Powered by Yojna.ai  ·  APJ Abdul Kalam Hackathon{RESET}\n")


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
