"""
stats.py — Numbers for the "Your Job Market", "Learning Gaps" and
"Application Tracker" panels.

Rule: every number here is COUNTED from data actually stored in your database
(jobs JobFisher found, statuses you set). Nothing is estimated or invented.
If there isn't enough data, the panel says so instead of guessing.
"""

from collections import Counter
from statistics import median

from .db import from_json, get_connection

ACTIVE_FOR_MARKET = ("New", "Viewed", "Saved", "Applied", "Interview", "Offer")


def _relevant_rows(conn):
    placeholders = ",".join("?" * len(ACTIVE_FOR_MARKET))
    return conn.execute(
        f"SELECT * FROM jobs WHERE is_relevant = 1 AND status IN ({placeholders})", ACTIVE_FOR_MARKET
    ).fetchall()


def job_market():
    with get_connection() as conn:
        rows = _relevant_rows(conn)
    n = len(rows)
    if n == 0:
        return {"job_count": 0}

    skills, titles, years_buckets = Counter(), Counter(), Counter()
    entry_level = 0
    salaries = []
    for r in rows:
        a = from_json(r["analysis_json"], {}) or {}
        sk = a.get("skills") or {}
        for name in set(sk.get("required", []) + sk.get("preferred", [])):
            skills[name] += 1
        titles[_simplify_title(r["title"])] += 1
        years = (a.get("experience") or {}).get("required_years")
        years_buckets[_years_bucket(years)] += 1
        if (a.get("level") or {}).get("junior"):
            entry_level += 1
        # Only employer-stated, annual-looking salaries (hourly numbers would skew it).
        for value in (r["salary_min"], r["salary_max"]):
            if value and value >= 15000:
                salaries.append(value)

    order = ["Not stated", "0–1 years", "2 years", "3–4 years", "5+ years"]
    return {
        "job_count": n,
        "top_skills": [{"skill": s, "count": c, "percent": round(100 * c / n)} for s, c in skills.most_common(10)],
        "experience": [{"bucket": b, "count": years_buckets.get(b, 0)} for b in order],
        "entry_level_count": entry_level,
        "top_titles": [{"title": t, "count": c} for t, c in titles.most_common(5)],
        "salary": {
            "count": len({r["id"] for r in rows if r["salary_min"] or r["salary_max"]}),
            "low": min(salaries) if salaries else None,
            "median": median(salaries) if salaries else None,
            "high": max(salaries) if salaries else None,
        },
    }


def learning_gaps():
    """Skills that relevant jobs ask for that your profile/resume doesn't show."""
    with get_connection() as conn:
        rows = _relevant_rows(conn)
    n = len(rows)
    missing = Counter()
    for r in rows:
        a = from_json(r["analysis_json"], {}) or {}
        for row in (a.get("skills") or {}).get("rows", []):
            if row.get("status") == "gap":
                missing[row["skill"]] += 1
    return {
        "job_count": n,
        "enough_data": n >= 10,
        "gaps": [{"skill": s, "count": c, "percent": round(100 * c / n)} for s, c in missing.most_common(8)] if n else [],
    }


def tracker():
    with get_connection() as conn:
        by_status = dict(conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall())
        apps = conn.execute(
            "SELECT j.*, a.date_applied, a.interview_dates_json FROM applications a JOIN jobs j ON j.id = a.job_id"
        ).fetchall()
        interviewed_ids = {r[0] for r in conn.execute(
            "SELECT DISTINCT job_id FROM status_history WHERE status IN ('Interview', 'Offer')").fetchall()}
        viewed = conn.execute(
            "SELECT COUNT(DISTINCT job_id) FROM status_history WHERE status = 'Viewed'").fetchone()[0]

    submitted = [a for a in apps if a["date_applied"]]
    interviews = [a for a in submitted if a["id"] in interviewed_ids or from_json(a["interview_dates_json"], [])]
    missing = Counter()
    by_level, by_arrangement = Counter(), Counter()
    for a in submitted:
        analysis = from_json(a["analysis_json"], {}) or {}
        for row in (analysis.get("skills") or {}).get("rows", []):
            if row.get("status") == "gap" and row.get("required"):
                missing[row["skill"]] += 1
        by_level[(analysis.get("level") or {}).get("label", "Unknown")] += 1
        by_arrangement[a["work_arrangement"] or "Unknown"] += 1

    return {
        "counts": {s: by_status.get(s, 0) for s in
                   ("New", "Viewed", "Saved", "Applied", "Interview", "Offer", "Rejected", "Expired", "Hidden",
                    "No Longer Relevant")},
        "jobs_viewed": viewed,
        "applications_submitted": len(submitted),
        "interviews_received": len(interviews),
        "interview_rate": round(100 * len(interviews) / len(submitted)) if submitted else None,
        "active": by_status.get("Applied", 0) + by_status.get("Interview", 0),
        "average_fit_of_applications": round(sum(a["fit_score"] or 0 for a in submitted) / len(submitted)) if submitted else None,
        "applications_by_level": dict(by_level),
        "applications_by_arrangement": dict(by_arrangement),
        "common_missing_skills_in_applications": [{"skill": s, "count": c} for s, c in missing.most_common(5)],
    }


def _years_bucket(years):
    if years is None:
        return "Not stated"
    if years <= 1:
        return "0–1 years"
    if years == 2:
        return "2 years"
    if years <= 4:
        return "3–4 years"
    return "5+ years"


def _simplify_title(title):
    """'Junior Front-End Developer (Remote)' and 'Jr. Front End Developer'
    should count as the same title in the "Most common job titles" list."""
    import re
    t = re.sub(r"\(.*?\)|[-–|,].*remote.*$", "", title or "", flags=re.I)
    t = re.sub(r"\b(jr\.?|junior|entry[- ]level|i|ii|iii)\b", "", t, flags=re.I)
    t = re.sub(r"front[- ]?end", "Front-End", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" -–,") or title
