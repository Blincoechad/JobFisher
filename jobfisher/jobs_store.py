"""
jobs_store.py — Everything that reads or changes jobs in the database
(other than the refresh pipeline itself).

WHAT:  List jobs, get one job, change status, save application notes,
       add a job manually, re-run the analysis, and pick the top 8.
WHY:   Keeping database queries here means the Flask routes in app.py stay
       short and readable: "get the data, return it as JSON".
"""

from datetime import datetime, timedelta, timezone

from . import normalize
from .candidate import build_candidate
from .db import from_json, get_connection, now_iso, to_json
from .matcher import analyze_job
from .profile_store import get_profile, get_settings
from .resume import get_active_resume

STATUSES = ["New", "Viewed", "Saved", "Applied", "Interview", "Offer", "Rejected",
            "Expired", "Hidden", "No Longer Relevant"]
# Jobs in these statuses can appear in the main "8 strongest" list.
RECOMMENDABLE = ("New", "Viewed", "Saved")
# Jobs in these statuses belong to the application tracker.
TRACKED = ("Applied", "Interview", "Offer", "Rejected")


def _days_since(iso_text):
    if not iso_text:
        return None
    try:
        then = datetime.fromisoformat(iso_text)
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds() / 86400


def row_to_job(row, full=False, settings=None):
    """Convert a database row into the JSON the front end receives."""
    settings = settings or get_settings()
    analysis = from_json(row["analysis_json"], {}) or {}
    days_unseen = _days_since(row["last_seen_active"])
    job = {
        "id": row["id"],
        "title": row["title"],
        "company": row["company"],
        "location": row["location"],
        "work_arrangement": row["work_arrangement"],
        "employment_type": row["employment_type"],
        "salary_text": row["salary_text"],
        "url": row["url"],
        "source": row["source"],
        "sources": from_json(row["sources_json"], []),
        "date_posted": row["date_posted"],
        "date_discovered": row["date_discovered"],
        "last_checked": row["last_checked"],
        "last_seen_active": row["last_seen_active"],
        "updated_at": row["updated_at"],
        "freshness": row["freshness"],
        "status": row["status"],
        "is_manual": bool(row["is_manual"]),
        "in_top8": bool(row["in_top8"]),
        "fit_score": row["fit_score"],
        "fit_category": row["fit_category"],
        "stale": days_unseen is not None and days_unseen > settings["freshness"]["stale_after_days"],
        "analysis": analysis if full else _card_analysis(analysis),
    }
    if full:
        job["description"] = row["description"]
    return job


def _card_analysis(a):
    """The subset of the analysis a card needs (keeps list responses small)."""
    if not a:
        return {}
    return {
        "summary": a.get("summary"),
        "strengths": a.get("strengths", [])[:6],
        "gaps": a.get("gaps", [])[:5],
        "difficulty": a.get("difficulty"),
        "competitiveness": a.get("competitiveness"),
        "hiring_context": a.get("hiring_context"),
        "portfolio": a.get("portfolio"),
        "level": a.get("level"),
        "caps": a.get("caps", []),
        "data_notes": a.get("data_notes", []),
    }


# --- Reading -----------------------------------------------------------------------

def list_jobs(status=None, query=None, sort="fit", include_irrelevant=False):
    sql = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if not include_irrelevant:
        sql += " AND is_relevant = 1"
    if status:
        sql += " AND status = ?"
        params.append(status)
    if query:
        sql += " AND (title LIKE ? OR company LIKE ? OR location LIKE ?)"
        params += [f"%{query}%"] * 3
    order = {
        "fit": "fit_score DESC",
        "newest": "date_discovered DESC",
        "posted": "COALESCE(date_posted, '') DESC",
        "company": "company COLLATE NOCASE ASC",
    }.get(sort, "fit_score DESC")
    sql += f" ORDER BY {order}"  # safe: `order` only comes from the fixed dict above
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    settings = get_settings()
    return [row_to_job(r, settings=settings) for r in rows]


def get_job(job_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        app_row = conn.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,)).fetchone()
        history = conn.execute("SELECT status, changed_at FROM status_history WHERE job_id = ? ORDER BY id",
                               (job_id,)).fetchall()
    job = row_to_job(row, full=True)
    job["application"] = {
        "date_applied": app_row["date_applied"],
        "interview_dates": from_json(app_row["interview_dates_json"], []),
        "notes": app_row["notes"],
    } if app_row else None
    job["history"] = [dict(h) for h in history]
    return job


def top_jobs():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE in_top8 = 1 ORDER BY fit_score DESC").fetchall()
    settings = get_settings()
    return [row_to_job(r, settings=settings) for r in rows]


# --- Changing ------------------------------------------------------------------------

def set_status(job_id, status):
    if status not in STATUSES:
        raise ValueError(f"Unknown status '{status}'.")
    with get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise LookupError("Job not found.")
        if row["status"] == status:
            return get_job(job_id)
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        conn.execute("INSERT INTO status_history (job_id, status, changed_at) VALUES (?, ?, ?)",
                     (job_id, status, now_iso()))
        # Applying creates the tracker record automatically.
        if status in ("Applied", "Interview", "Offer"):
            conn.execute("INSERT OR IGNORE INTO applications (job_id, date_applied, updated_at) VALUES (?, ?, ?)",
                         (job_id, now_iso()[:10], now_iso()))
        # Rejected/hidden/applied jobs leave the "8 strongest" list immediately.
        if status not in RECOMMENDABLE:
            conn.execute("UPDATE jobs SET in_top8 = 0 WHERE id = ?", (job_id,))
    return get_job(job_id)


def mark_viewed(job_id):
    """Opening a job's details moves it from New -> Viewed (nothing else changes)."""
    with get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row and row["status"] == "New":
        set_status(job_id, "Viewed")


def save_application(job_id, data):
    dates = [d for d in data.get("interview_dates", []) if isinstance(d, str) and d.strip()]
    with get_connection() as conn:
        if conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone() is None:
            raise LookupError("Job not found.")
        conn.execute(
            "INSERT INTO applications (job_id, date_applied, interview_dates_json, notes, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(job_id) DO UPDATE SET "
            "date_applied = excluded.date_applied, interview_dates_json = excluded.interview_dates_json, "
            "notes = excluded.notes, updated_at = excluded.updated_at",
            (job_id, data.get("date_applied") or None, to_json(dates), (data.get("notes") or "")[:5000], now_iso()),
        )
    return get_job(job_id)


def confirm_active(job_id):
    """You checked the posting yourself and it's still open."""
    with get_connection() as conn:
        conn.execute("UPDATE jobs SET last_seen_active = ?, last_checked = ? WHERE id = ?",
                     (now_iso(), now_iso(), job_id))
    return get_job(job_id)


def add_manual_job(data):
    """For postings you find on sites JobFisher can't access (LinkedIn, Indeed...).
    You paste the real posting text; nothing is invented."""
    title = (data.get("title") or "").strip()
    company = (data.get("company") or "").strip()
    description = (data.get("description") or "").strip()
    if not title or not company or len(description) < 50:
        raise ValueError("Title, company, and the full job description (50+ characters) are required.")
    url = (data.get("url") or "").strip()
    if url and not url.startswith(("http://", "https://")):
        raise ValueError("The application link must start with http:// or https://")
    job = normalize.make_job(
        source="Manual", source_id=None, title=title, company=company,
        location=(data.get("location") or "").strip(),
        work_arrangement=data.get("work_arrangement") or None,
        salary_text=(data.get("salary_text") or "").strip() or None,
        description=description, url=url or None, is_direct_url=True,
        date_posted=normalize.iso_date(data.get("date_posted")),
    )
    key = normalize.dedupe_key(job)
    now = now_iso()
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM jobs WHERE dedupe_key = ?", (key,)).fetchone()
        if existing:
            raise ValueError("This job is already in JobFisher (same company, title and location).")
        cur = conn.execute(
            "INSERT INTO jobs (dedupe_key, title, company, location, work_arrangement, salary_text, description, "
            "url, source, sources_json, source_ids_json, date_posted, date_discovered, last_checked, "
            "last_seen_active, content_hash, freshness, status, is_relevant, is_manual) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Manual', '[\"Manual\"]', '[]', ?, ?, ?, ?, ?, 'new', 'New', 1, 1)",
            (key, job["title"], job["company"], job["location"], job["work_arrangement"], job["salary_text"],
             job["description"], job["url"], job["date_posted"], now, now, now, normalize.content_hash(job)),
        )
        job_id = cur.lastrowid
        conn.execute("INSERT INTO status_history (job_id, status, changed_at) VALUES (?, 'New', ?)", (job_id, now))
    reanalyze_all()
    select_top_jobs()
    return get_job(job_id)


# --- Analysis + ranking -----------------------------------------------------------------

def current_candidate():
    return build_candidate(get_profile(), get_active_resume())


def reanalyze_all():
    """Re-score every stored job. Run after a refresh, a profile edit,
    a settings change or a new resume — so scores always reflect your
    CURRENT profile."""
    settings = get_settings()
    candidate = current_candidate()
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM jobs").fetchall()
        # First pass gives every job its level/years, which the company
        # history (second pass) needs.
        first = {}
        for r in rows:
            first[r["id"]] = analyze_job(dict(r), candidate, settings)
        history = {}
        for r in rows:
            a = first[r["id"]]
            history.setdefault(r["company"].lower(), []).append({
                "id": r["id"], "title": r["title"],
                "required_years": a["experience"].get("required_years"),
                "junior": a["level"]["junior"], "senior": a["level"]["senior"],
            })
        for r in rows:
            others = [h for h in history.get(r["company"].lower(), []) if h["id"] != r["id"]]
            a = analyze_job(dict(r), candidate, settings, others)
            relevant = 1 if (a["relevant"] or r["is_manual"]) else 0
            conn.execute(
                "UPDATE jobs SET analysis_json = ?, fit_score = ?, fit_category = ?, difficulty = ?, "
                "competitiveness = ?, hiring_context = ?, is_relevant = ? WHERE id = ?",
                (to_json(a), a["fit_score"], a["fit_category"], a["difficulty"]["level"],
                 a["competitiveness"]["level"], a["hiring_context"]["level"], relevant, r["id"]),
            )


def select_top_jobs():
    """Choose the dashboard's strongest N jobs.

    Rules (spec sections 8 & 9):
      * Only relevant, still-recommendable jobs (not applied/rejected/hidden/expired).
      * Must meet the minimum fit score — we'd rather show 5 good jobs than 8 bad ones.
      * Ranked by fit, NOT by newest.
      * Jobs already on the dashboard get small "stickiness" bonus points, so a
        newcomer only replaces one if it is meaningfully better.
      * Stale listings (not seen for a while) are pushed down.
    """
    settings = get_settings()
    display = settings["display"]
    stale_days = settings["freshness"]["stale_after_days"]
    placeholders = ",".join("?" * len(RECOMMENDABLE))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT id, fit_score, in_top8, last_seen_active, date_discovered FROM jobs "
            f"WHERE is_relevant = 1 AND status IN ({placeholders}) AND fit_score >= ?",
            (*RECOMMENDABLE, display["min_fit_score"]),
        ).fetchall()

        def rank(r):
            points = r["fit_score"]
            if r["in_top8"]:
                points += display["stickiness_points"]
            unseen = _days_since(r["last_seen_active"]) or 0
            if unseen > stale_days:
                points -= 10
            return (points, r["date_discovered"] or "")

        chosen = sorted(rows, key=rank, reverse=True)[: int(display["top_n"])]
        conn.execute("UPDATE jobs SET in_top8 = 0")
        conn.executemany("UPDATE jobs SET in_top8 = 1 WHERE id = ?", [(r["id"],) for r in chosen])
    return len(chosen)


def expire_old_jobs():
    """Jobs not seen in any source for `expire_after_days` become Expired —
    unless you're tracking them (Saved/Applied/...) or added them manually."""
    settings = get_settings()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings["freshness"]["expire_after_days"])).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id FROM jobs WHERE is_manual = 0 AND status IN ('New', 'Viewed') AND last_seen_active < ?",
            (cutoff,)).fetchall()
    for r in rows:
        set_status(r["id"], "Expired")
    return len(rows)
