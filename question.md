THE SCENARIO


Named after APJ Abdul Kalam. You're building an AI document intelligence engine for India's welfare system. Millions of Indians qualify for government schemes but never claim them because the eligibility criteria are buried in bureaucratic language across hundreds of PDFs and the requirements are unclear.
Your system changes that.

PART I  Taming the Data
Use AI to parse and structure eligibility criteria for at least 15 central government welfare schemes: PM Kisan, MGNREGA, Ayushman Bharat, PMAY, and others.
Critical constraint: eligibility must be expressed as explicit logical rules, not prose summaries. Then identify every contradiction, overlap, and ambiguity across all 15 schemes. Government eligibility language is intentionally vague because it preserves administrative discretion. Your ambiguity map is a core deliverable, not a footnote.

PART II  The Matching Engine
A user inputs: age, state, caste category, income, land ownership, occupation, family size, bank account status. The engine outputs: schemes they fully qualify for with confidence scores, schemes they almost qualify for with gap analysis, a document checklist in priority order, and the correct application sequence (some schemes are prerequisites for others).
Every output must be explainable. Confidence scores must be traceable to specific rule evaluations. No black boxes anywhere. Construct ten adversarial edge-case users: a widow who recently remarried, a farmer who leases rather than owns land, a person with Aadhaar but no bank account. Document every failure.

PART III  Conversational Interface
Build a CLI or basic web UI where a user describes their situation in natural language and the system asks intelligent follow-up questions. The conversation must work in Hinglish. It must handle incomplete answers, contradictory answers, and users who don't know their own eligibility.
Final deliverable: a full architecture document covering the system diagram, three key technical decisions with rejected alternatives, and the two most critical production-readiness gaps.

Fair Warning
Government data is genuinely messy and AI hallucinates eligibility criteria with complete confidence. If you take AI's parsing at face value, you'll build a system that gives wrong answers to real people.
Your architecture has to be designed around uncertainty. The system must fail clearly, not silently. Evaluators will feed edge-case profiles into your engine and check whether it flags ambiguity rather than fabricating a confident answer.


SUBMISSION CHECKLIST


Check every box. Incomplete submissions get disqualified. No exceptions.

□  Structured eligibility rules for 15+ central government schemes
□  Ambiguity map documenting contradictions and overlaps across schemes
□  Working matching engine with explainable confidence scores
□  Ten adversarial edge-case profiles with documented results
□  Conversational interface supporting Hinglish natural language input
□  Architecture document with system diagram and technical decisions

USED AI? YOUR PROMPT LOG IS MANDATORY.
Submit every prompt you fired, every output you got back, every output you threw away, and why. This isn't busywork. It's 25% of your score. A clean deliverable with no prompt log is an auto-disqualify.
