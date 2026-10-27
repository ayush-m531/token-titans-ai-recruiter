# REPORT — AI Recruiter & Auto-Scheduler (Team Token Titans)

**1. Approach.** A three-agent pipeline. The Resume Parser Agent turns an unstructured resume into validated JSON with an LLM; the Screening Evaluator compares it with the job using SQL (`job_skills EXCEPT candidate_skills`) and a years check; the Scheduler Agent books the earliest free panel slot with an atomic conditional update. An orchestrator logs every step and writes a candidate message. HR can search candidates by meaning.

**2. Tools.** Python, Streamlit, SQLite, Pydantic, pypdf, Gemini (3.5-flash-lite → 3.8-flash → 3.7-flash), MiniLM + Chroma for search.

**3. Constraints.** 4.5-hour build; internet-dependent LLM; no real calendars.

**4. Assumptions.** Today = Oct 2026; synthetic panel slots; internships listed as experience count.

**5. Top 5 design decisions.**
(1) LLM extracts, code decides — fair and explainable screening.
(2) Years computed in Python with overlapping jobs merged.
(3) Skills stored one row each so screening is relational SQL.
(4) Pydantic validation with one retry carrying the error, then model fallback, then NEEDS_REVIEW.
(5) File-hash uniqueness and conditional UPDATE to prevent duplicate applications and double-booking.

**6. AI-assistant use.** Code drafted with Claude from our design; every member reviewed, ran and can explain their files. Prompts in `docs/prompts.md`.

**7. Prior work.** HCLTech use-case brief; reference Hugging Face resume datasets; standard RAG/structured-extraction patterns.

**8. Failed attempts.** [team: fill in today's real failures, e.g. a model name that failed, parsing issues, changed designs]
