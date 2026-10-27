"""pipeline.py - the orchestrator.
Parser Agent -> save -> Screening Evaluator -> Scheduler Agent -> candidate message.
Never crashes: anything that fails is saved as NEEDS_REVIEW with a reason.
"""
import hashlib
import json
import os

from src.db import save_application, update_status, log_event      # P1
from src.llm import ask_llm
from src.parser import analyse_resume
from src.scheduler import book_interview                             # P4
from src.screening import screen                                     # P3

MESSAGE_RULES = """Write a short, polite 2-3 line message to a job applicant.
Use ONLY the facts in the given JSON (status, reasons, slot). Do not add or change any fact.
Return JSON: {"message": "..."}"""


def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _check_message(raw):
    try:
        msg = json.loads(raw).get("message", "")
        return (msg, None) if msg.strip() else (None, "message is empty")
    except (json.JSONDecodeError, AttributeError) as e:
        return None, f"not valid JSON: {e}"


def _template_message(status, reasons, slot):
    """Fixed wording used when the LLM is not available."""
    if status == "SCHEDULED":
        return f"Congratulations! You are shortlisted. Your interview is on {slot['start_time']} with {slot['panelist']}."
    if status == "SHORTLISTED":
        return "Congratulations! You are shortlisted. We will share your interview slot soon."
    if status == "REJECTED":
        return "Thank you for applying. Unfortunately you do not meet the requirements: " + "; ".join(reasons) + "."
    return "Thank you for applying. Your application is being reviewed by our team."


def write_message(status, reasons, slot):
    facts = json.dumps({"status": status, "reasons": reasons, "slot": slot})
    msg, _ = ask_llm(MESSAGE_RULES, facts, _check_message)
    return msg or _template_message(status, reasons, slot)


def process_application(conn, job_id, file_path):
    h = file_hash(file_path)

    # 0. same file already applied to this job? (checked before calling the LLM)
    row = conn.execute("SELECT application_id, status FROM applications WHERE job_id=? AND file_hash=?",
                       (job_id, h)).fetchone()
    if row:
        return {"application_id": row[0], "status": "ALREADY_APPLIED",
                "reasons": [f"this resume already applied to {job_id} (status {row[1]})"]}

    # 1. Parser Agent
    r = analyse_resume(file_path)
    status = "NEEDS_REVIEW" if r["error"] else "PENDING"
    reasons = [r["error"]] if r["error"] else []
    app_id = save_application(conn, job_id=job_id, file_name=os.path.basename(file_path), file_hash=h,
                              name=r["name"], location=r["location"], total_years=r["total_years"],
                              resume_text=r["text"], parsed_json=r["parsed_json"], skills=r["skills"],
                              status=status, reasons=reasons)
    log_event(conn, "PARSE", app_id, json.dumps({"model": r["model"], "skills": r["skills"],
              "dropped_skills": r["dropped_skills"], "years": r["total_years"], "error": r["error"]}))

    # 2. Screening Evaluator (only if parsing worked)
    slot = None
    if status == "PENDING":
        result = screen(conn, app_id, job_id)
        status, reasons = result["decision"], result["reasons"]
        log_event(conn, "SCREEN", app_id, json.dumps(result))

        # 3. Scheduler Agent (only if shortlisted)
        if status == "SHORTLISTED":
            booking = book_interview(conn, app_id)
            log_event(conn, "BOOK", app_id, json.dumps(booking))
            if booking.get("ok"):
                status = "SCHEDULED"
                slot = {"start_time": booking["start_time"], "panelist": booking["panelist"]}
            else:
                reasons = reasons + [booking.get("reason", "no slot available")]

    update_status(conn, app_id, status, reasons)

    # 4. Response generation (LLM, with a template fallback)
    message = write_message(status, reasons, slot)
    log_event(conn, "MESSAGE", app_id, message)

    return {"application_id": app_id, "status": status, "name": r["name"],
            "total_years": r["total_years"], "skills": r["skills"], "reasons": reasons,
            "slot": slot, "message": message, "model": r["model"]}
