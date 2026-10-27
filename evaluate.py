"""evaluate.py - runs the Parser Agent + Screening Evaluator on hand-labelled resumes.
Uses a fresh eval.db each run (nothing is booked, recruit.db is untouched).
Run: python evaluate.py
"""
import csv
import hashlib
import os
import time

from src.db import init_db, save_application
from src.parser import analyse_resume
from src.screening import screen

EVAL_DB = "eval.db"
if os.path.exists(EVAL_DB):
    os.remove(EVAL_DB)
conn = init_db(EVAL_DB)                     # same seeded jobs: J01 ML Engineer, J02 Backend Developer

rows, out = list(csv.DictReader(open("eval/labels.csv"))), []
for row in rows:
    path = os.path.join("data/resumes", row["file"])
    t0 = time.time()
    r = analyse_resume(path)
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    app_id = save_application(conn, row["job_id"], row["file"], h, r["name"], r["location"],
                              r["total_years"], r["text"], r["parsed_json"], r["skills"],
                              "NEEDS_REVIEW" if r["error"] else "PENDING", [r["error"]] if r["error"] else [])
    decision = "NEEDS_REVIEW" if r["error"] else screen(conn, app_id, row["job_id"])["decision"]
    secs = round(time.time() - t0, 1)

    exp_skills = {s.strip() for s in row["expected_skills"].split(";") if s.strip()}
    years_ok = r["total_years"] is not None and abs(r["total_years"] - float(row["expected_years"])) <= 0.5
    skills_ok = exp_skills.issubset(set(r["skills"]))
    decision_ok = decision == row["expected_decision"]
    out.append({"file": row["file"], "job": row["job_id"], "years": r["total_years"], "expected_years": row["expected_years"],
                "years_ok": years_ok, "skills_ok": skills_ok, "decision": decision,
                "expected_decision": row["expected_decision"], "decision_ok": decision_ok,
                "dropped_skills": "; ".join(r["dropped_skills"]), "model": r["model"], "seconds": secs})
    print(f"{'OK ' if decision_ok else 'BAD'} {row['file']:22} years {r['total_years']} (exp {row['expected_years']}) "
          f"| skills {'ok' if skills_ok else 'MISSING'} | {decision} (exp {row['expected_decision']}) | {secs}s")

n = len(out)
print(f"\nYears correct (±0.5): {sum(o['years_ok'] for o in out)}/{n}")
print(f"Skills correct:       {sum(o['skills_ok'] for o in out)}/{n}")
print(f"Decision correct:     {sum(o['decision_ok'] for o in out)}/{n}")
print(f"Avg time per resume:  {sum(o['seconds'] for o in out) / n:.1f}s")
os.makedirs("eval", exist_ok=True)
with open("eval/results.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)
print("Saved eval/results.csv")
