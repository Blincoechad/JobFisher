"""
refresh.py — What happens when you press  🔄 Refresh Jobs.

The pipeline (spec section 7), one function per step so you can follow it:

  1. fetch_all_sources()   Search configured sources (respecting rate limits)
  2. dedupe_batch()        Remove duplicates inside this batch
  3. (matcher)             Analyze each job; keep only real web design/dev roles
  4. store_jobs()          Compare with the database: new / updated / previously seen
  5. mark_unseen()         Jobs that vanished from their source get older "last seen" dates
  6. expire_old_jobs()     Long-gone listings become Expired
  7. reanalyze_all()       Re-score everything against your current profile
  8. select_top_jobs()     Rank and pick the strongest 8
  9. record the summary    Numbers for the "Search Summary" panel
"""

import os
from datetime import datetime, timedelta, timezone

from . import jobs_store
from .db import from_json, get_connection, now_iso, to_json
from .matcher import analyze_job
from .normalize import content_hash, dedupe_key
from .profile_store import get_settings
from .sources import SOURCES
from .sources.http import SourceSkipped


def run_refresh(sources=None):
    """Run the whole pipeline. `sources` lets tests inject fake sources."""
    sources = sources or SOURCES
    settings = get_settings()
    started = now_iso()
    with get_connection() as conn:
        refresh_id = conn.execute("INSERT INTO refreshes (started_at) VALUES (?)", (started,)).lastrowid

    raw_jobs, report, checked_labels = fetch_all_sources(sources, settings)
    batch = dedupe_batch(raw_jobs)

    # Step 3: analyze each job once to decide whether it's a relevant web role.
    candidate = jobs_store.current_candidate()
    relevant = []
    for job in batch:
        analysis = analyze_job(job, candidate, settings)
        if analysis["relevant"]:
            relevant.append(job)

    any_success = bool(checked_labels)
    new_count = updated_count = 0
    if any_success:
        with get_connection() as conn:
            # Last refresh's "new"/"updated" badges become "seen" now.
            conn.execute("UPDATE jobs SET freshness = 'seen' WHERE freshness IN ('new', 'updated')")
        new_count, updated_count = store_jobs(relevant, started)
        mark_unseen(checked_labels, started)
        jobs_store.expire_old_jobs()

    jobs_store.reanalyze_all()
    displayed = jobs_store.select_top_jobs()

    with get_connection() as conn:
        strong = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE is_relevant = 1 AND fit_category = 'Strong Match' "
            "AND status IN ('New', 'Viewed', 'Saved')").fetchone()[0]
        conn.execute(
            "UPDATE refreshes SET finished_at = ?, scanned = ?, relevant = ?, new_count = ?, updated_count = ?, "
            "strong = ?, displayed = ?, source_report_json = ? WHERE id = ?",
            (now_iso(), len(raw_jobs), len(relevant), new_count, updated_count, strong, displayed,
             to_json(report), refresh_id),
        )
    return latest_refresh()


# --- Step 1 ------------------------------------------------------------------------

def fetch_all_sources(sources, settings):
    """Call each enabled source. One failing source never stops the others —
    the error is recorded in the report and shown on the dashboard."""
    all_jobs, report, checked = [], [], set()
    for key, fetch in sources.items():
        cfg = settings["sources"].get(key, {"enabled": True, "label": key})
        label = cfg.get("label", key)
        if not cfg.get("enabled", True):
            report.append({"source": label, "status": "disabled", "message": "Turned off in Settings."})
            continue
        wait = _cooldown_remaining(key, cfg.get("cooldown_hours", 0))
        if wait:
            report.append({"source": label, "status": "cooldown",
                           "message": f"Skipped to respect the source's rate limit — available again in {wait}."})
            continue
        try:
            jobs = fetch(cfg, settings)
        except SourceSkipped as exc:
            report.append({"source": label, "status": "skipped", "message": str(exc)})
            continue
        except Exception as exc:  # network errors, bad JSON, site changes...
            report.append({"source": label, "status": "error", "message": friendly_error(exc)})
            continue
        _record_call(key)
        checked.update({j["source"] for j in jobs} | {_source_name_for(key)})
        all_jobs.extend(jobs)
        report.append({"source": label, "status": "ok", "message": f"{len(jobs)} postings retrieved."})
    return all_jobs, report, checked


def friendly_error(exc):
    """Turn a Python exception into a sentence you can act on."""
    import requests
    if isinstance(exc, requests.Timeout):
        return "The site took longer than 20 seconds to answer. Try again later."
    if isinstance(exc, requests.ConnectionError):
        return "Couldn't connect. Check your internet connection (or the site may be down)."
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        if code == 429:
            return "The site says we've searched too often (429). It will work again after the cooldown."
        if code in (401, 403):
            return f"The site refused the request ({code}). If this source uses a key, check your .env file."
        if code == 404:
            return "Not found (404). Check the board token / company slug in Settings."
        return f"The site returned an error ({code})."
    if isinstance(exc, ValueError):
        return "The site sent data JobFisher couldn't read. Its API may have changed."
    return f"Unexpected error: {exc.__class__.__name__}: {str(exc)[:120]}"


def _source_name_for(key):
    return {"themuse": "The Muse", "remotive": "Remotive", "jobicy": "Jobicy", "adzuna": "Adzuna",
            "greenhouse": "Greenhouse", "lever": "Lever"}.get(key, key)


def _cooldown_remaining(key, hours):
    if not hours or os.environ.get("JOBFISHER_IGNORE_COOLDOWN"):
        return None
    with get_connection() as conn:
        row = conn.execute("SELECT last_called FROM source_calls WHERE source = ?", (key,)).fetchone()
    if not row:
        return None
    ready_at = datetime.fromisoformat(row["last_called"]) + timedelta(hours=hours)
    remaining = ready_at - datetime.now(timezone.utc)
    if remaining.total_seconds() <= 0:
        return None
    minutes = int(remaining.total_seconds() // 60) + 1
    return f"{minutes // 60}h {minutes % 60}m" if minutes >= 60 else f"{minutes} min"


def _record_call(key):
    with get_connection() as conn:
        conn.execute("INSERT INTO source_calls (source, last_called) VALUES (?, ?) "
                     "ON CONFLICT(source) DO UPDATE SET last_called = excluded.last_called", (key, now_iso()))


# --- Step 2 ------------------------------------------------------------------------

def dedupe_batch(jobs):
    """Merge postings that are the same job (same company + title + city)."""
    merged = {}
    for job in jobs:
        if not job.get("title"):
            continue
        key = dedupe_key(job)
        job["dedupe_key"] = key
        job["source_ids"] = [f"{job['source']}:{job['source_id']}"] if job.get("source_id") else []
        job["sources"] = [job["source"]]
        if key not in merged:
            merged[key] = job
            continue
        keep = merged[key]
        keep["sources"] = sorted(set(keep["sources"]) | set(job["sources"]))
        keep["source_ids"] = sorted(set(keep["source_ids"]) | set(job["source_ids"]))
        # Prefer the company's direct application URL over an aggregator's.
        if job.get("is_direct_url") and not keep.get("is_direct_url"):
            keep["url"], keep["is_direct_url"] = job["url"], True
        # Keep the longest description (more detail = better analysis).
        if len(job.get("description") or "") > len(keep.get("description") or ""):
            keep["description"] = job["description"]
        for field in ("salary_text", "salary_min", "salary_max", "date_posted", "employment_type", "level_hint"):
            keep[field] = keep.get(field) or job.get(field)
    return list(merged.values())


# --- Step 4 ------------------------------------------------------------------------

def _find_existing(conn, job):
    row = conn.execute("SELECT * FROM jobs WHERE dedupe_key = ?", (job["dedupe_key"],)).fetchone()
    if row:
        return row
    for sid in job["source_ids"]:
        row = conn.execute("SELECT * FROM jobs WHERE source_ids_json LIKE ?", (f'%"{sid}"%',)).fetchone()
        if row:
            return row
    return None


def store_jobs(jobs, now):
    """Insert brand-new jobs; refresh the dates on ones we've seen before.
    Returns (new_count, updated_count)."""
    new_count = updated_count = 0
    with get_connection() as conn:
        for job in jobs:
            fingerprint = content_hash(job)
            existing = _find_existing(conn, job)
            if existing is None:
                cur = conn.execute(
                    "INSERT INTO jobs (dedupe_key, title, company, location, work_arrangement, remote_region, "
                    "level_hint, employment_type, "
                    "salary_text, salary_min, salary_max, description, url, source, sources_json, source_ids_json, "
                    "date_posted, date_discovered, last_checked, last_seen_active, content_hash, freshness, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', 'New')",
                    (job["dedupe_key"], job["title"], job["company"], job["location"], job["work_arrangement"],
                     job.get("remote_region"), job.get("level_hint"), job.get("employment_type"), job.get("salary_text"), _num(job.get("salary_min")),
                     _num(job.get("salary_max")), job["description"], job.get("url"), job["source"],
                     to_json(job["sources"]), to_json(job["source_ids"]), job.get("date_posted"),
                     now, now, now, fingerprint),
                )
                conn.execute("INSERT INTO status_history (job_id, status, changed_at) VALUES (?, 'New', ?)",
                             (cur.lastrowid, now))
                new_count += 1
                continue

            sources = sorted(set(from_json(existing["sources_json"], [])) | set(job["sources"]))
            source_ids = sorted(set(from_json(existing["source_ids_json"], [])) | set(job["source_ids"]))
            url = existing["url"]
            if job.get("is_direct_url") and existing["source"] not in ("Greenhouse", "Lever", "Manual"):
                url = job.get("url") or url
            status = existing["status"]
            if status == "Expired":  # it came back, so it isn't expired after all
                status = "Viewed"
                conn.execute("INSERT INTO status_history (job_id, status, changed_at) VALUES (?, ?, ?)",
                             (existing["id"], status, now))
            changed = fingerprint != existing["content_hash"]
            if changed:
                updated_count += 1
                conn.execute(
                    "UPDATE jobs SET title = ?, location = ?, salary_text = ?, salary_min = ?, salary_max = ?, "
                    "description = ?, content_hash = ?, updated_at = ?, freshness = 'updated' WHERE id = ?",
                    (job["title"], job["location"], job.get("salary_text"), _num(job.get("salary_min")),
                     _num(job.get("salary_max")), job["description"], fingerprint, now, existing["id"]),
                )
            conn.execute(
                "UPDATE jobs SET sources_json = ?, source_ids_json = ?, url = ?, status = ?, last_checked = ?, "
                "last_seen_active = ?, remote_region = COALESCE(?, remote_region), "
                "level_hint = COALESCE(?, level_hint) WHERE id = ?",
                (to_json(sources), to_json(source_ids), url, status, now, now,
                 job.get("remote_region"), job.get("level_hint"), existing["id"]),
            )
    return new_count, updated_count


def _num(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


# --- Step 5 ------------------------------------------------------------------------

def mark_unseen(checked_labels, now):
    """Jobs from a source we DID check this time, but which weren't in the
    results, get last_checked updated while last_seen_active stays old.
    That growing gap is what drives "⚠ Listing may be stale" and expiry."""
    with get_connection() as conn:
        for label in checked_labels:
            conn.execute(
                "UPDATE jobs SET last_checked = ? WHERE is_manual = 0 AND sources_json LIKE ? "
                "AND (last_seen_active IS NULL OR last_seen_active < ?)",
                (now, f'%"{label}"%', now),
            )


def latest_refresh():
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM refreshes WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    result = dict(row)
    result["source_report"] = from_json(result.pop("source_report_json"), [])
    return result
