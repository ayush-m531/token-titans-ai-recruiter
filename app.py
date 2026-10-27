"""app.py - Streamlit UI. Run: streamlit run app.py"""
import os

import pandas as pd
import streamlit as st

from src.db import add_job, get_applications, get_audit, get_slots, init_db, list_jobs
from src.pipeline import process_application
from src.search import search

st.set_page_config(page_title="AI Recruiter", layout="wide")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@st.cache_resource
def get_conn():
    return init_db("recruit.db")


conn = get_conn()
st.title("AI Recruiter & Auto-Scheduler")
st.caption("Parser Agent (LLM reads the resume) → Screening Evaluator (SQL rules) → "
           "Scheduler Agent (books a slot). The LLM never makes the decision.")

hr, cand, dash, find = st.tabs(["HR: post job", "Candidate: apply", "Dashboard", "Search candidates"])

# ---------------- HR ----------------
with hr:
    with st.form("job"):
        title = st.text_input("Job title", "Data Scientist")
        min_years = st.number_input("Minimum years of experience", 0.0, 30.0, 2.0, 0.5)
        skills = st.text_input("Mandatory skills (comma separated)", "Python, SQL, ML")
        if st.form_submit_button("Post job") and title.strip():
            job_id = add_job(conn, title.strip(), min_years, skills.split(","))
            st.success(f"Posted {job_id}")
    st.subheader("Open jobs")
    st.dataframe(pd.DataFrame([{**j, "skills": ", ".join(j["skills"])} for j in list_jobs(conn)]),
                 hide_index=True, width="stretch")

# ---------------- Candidate ----------------
with cand:
    jobs = list_jobs(conn)
    job = st.selectbox("Job", jobs, format_func=lambda j: f"{j['job_id']} – {j['title']} "
                       f"(min {j['min_years']:g} yrs; {', '.join(j['skills'])})")
    file = st.file_uploader("Upload resume (PDF or TXT)", type=["pdf", "txt"])
    if file and job and st.button("Apply"):
        path = os.path.join(UPLOAD_DIR, file.name)
        with open(path, "wb") as f:
            f.write(file.getbuffer())
        with st.spinner("Agents working..."):
            res = process_application(conn, job["job_id"], path)

        if res["status"] == "ALREADY_APPLIED":
            st.warning(res["reasons"][0])
        else:
            parsed = res["status"] != "NEEDS_REVIEW" or res.get("total_years") is not None
            st.markdown(f"{'✅' if parsed else '⚠️'} **Parser Agent** — model: `{res['model']}`")
            screened = res["status"] in ("SHORTLISTED", "REJECTED", "SCHEDULED")
            st.markdown(f"{'✅' if screened else '⏭️'} **Screening Evaluator**")
            st.markdown(f"{'✅' if res['status'] == 'SCHEDULED' else '⏭️'} **Scheduler Agent**")

            color = {"SCHEDULED": "green", "SHORTLISTED": "green", "REJECTED": "red"}.get(res["status"], "orange")
            st.markdown(f"### Status: :{color}[{res['status']}]")
            c1, c2 = st.columns(2)
            c1.metric("Experience (years, calculated in Python)", res["total_years"] if res["total_years"] is not None else "—")
            c2.write("**Skills found:** " + (", ".join(res["skills"]) or "—"))
            st.write("**Reasons:**")
            for r in res["reasons"]:
                st.write("• " + r)
            if res["slot"]:
                st.success(f"Interview: {res['slot']['start_time']} with {res['slot']['panelist']}")
            st.info("Message to candidate: " + res["message"])

# ---------------- Dashboard ----------------
with dash:
    apps = get_applications(conn)
    if apps:
        df = pd.DataFrame(apps)
        st.subheader("Applications")
        st.dataframe(df, hide_index=True, width="stretch")
        counts = df["status"].value_counts()
        st.bar_chart(counts)
        pick = st.selectbox("Audit trail for", df["application_id"])
        st.dataframe(pd.DataFrame(get_audit(conn, pick)), hide_index=True, width="stretch")
    else:
        st.write("No applications yet.")
    st.subheader("Interview slots")
    st.dataframe(pd.DataFrame(get_slots(conn)), hide_index=True, width="stretch")

# ---------------- Search (retrieval) ----------------
with find:
    q = st.text_input("Describe who you are looking for", "machine learning with SQL")
    if st.button("Search"):
        results, method = search(conn, q)
        st.caption(f"Method: {method}")
        st.dataframe(pd.DataFrame(results), hide_index=True, width="stretch")
