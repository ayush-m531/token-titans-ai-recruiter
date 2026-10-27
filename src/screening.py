"""screening.py - Screening Evaluator. No LLM: SQL + Python rules only, so every decision is explainable."""


def screen(conn, application_id, job_id):
    years = conn.execute("SELECT total_years FROM applications WHERE application_id=?",
                         (application_id,)).fetchone()[0]
    min_years = conn.execute("SELECT min_years FROM jobs WHERE job_id=?", (job_id,)).fetchone()[0]
    if years is None:
        return {"decision": "NEEDS_REVIEW", "reasons": ["experience could not be calculated"]}

    # missing mandatory skills = job skills EXCEPT candidate skills (relational logic)
    missing = [r[0] for r in conn.execute(
        """SELECT skill FROM job_skills WHERE job_id = ?
           EXCEPT
           SELECT skill FROM candidate_skills WHERE application_id = ?""",
        (job_id, application_id))]

    reasons = []
    years_ok = years >= min_years                     # exactly the minimum counts as enough
    reasons.append(f"has {years:g} years, needs {min_years:g}" if years_ok
                   else f"only {years:g} years, needs {min_years:g}")
    reasons += [f"missing skill: {s}" for s in sorted(missing)]
    if not missing:
        reasons.append("has all mandatory skills")

    return {"decision": "SHORTLISTED" if years_ok and not missing else "REJECTED", "reasons": reasons}
