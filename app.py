"""
app.py — JobFisher's web server (Flask). Start the app with:  python app.py

WHAT:  Flask "routes" — each one connects a URL to a Python function.
         GET  /                 -> the dashboard page (HTML)
         GET  /api/...          -> data as JSON, read by static/js/*.js
         POST/PUT/DELETE /api/  -> changes (refresh, status, profile, resume)
WHY:   The front end (browser) can't read SQLite or PDFs directly. It asks
       this server over HTTP; the server does the work and replies with JSON.
HOW:   Routes stay SHORT on purpose: they read the request, call a function in
       the jobfisher/ package, and return the result. The real logic lives in
       those modules, so you can test it without a browser.

   Browser (static/js)  --fetch()-->  app.py routes  -->  jobfisher/*.py  -->  SQLite (data/)
"""

import os

from flask import Flask, jsonify, render_template, request

from jobfisher import jobs_store, profile_store, refresh, resume, stats
from jobfisher.db import init_db


def load_env_file(path=".env"):
    """Tiny .env reader (so we don't need another dependency).
    Each line looks like KEY=value. Real environment variables win."""
    full = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if not os.path.exists(full):
        return
    with open(full) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()
app = Flask(__name__)
app.json.sort_keys = False  # keep settings/sources in the order they're written
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # reject uploads over ~6 MB before reading them
init_db()


# --- Helpers -----------------------------------------------------------------------

def error(message, code=400):
    return jsonify({"error": message}), code


@app.errorhandler(413)
def too_large(_):
    return error("That file is too large (5 MB max).", 413)


# --- Page --------------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html")


# --- Dashboard + refresh -------------------------------------------------------------

def dashboard_payload():
    return {
        "top_jobs": jobs_store.top_jobs(),
        "last_refresh": refresh.latest_refresh(),
        "market": stats.job_market(),
        "gaps": stats.learning_gaps(),
        "tracker": stats.tracker(),
        "resume": resume.get_active_resume(),
        "settings": {"top_n": profile_store.get_settings()["display"]["top_n"]},
    }


@app.get("/api/dashboard")
def get_dashboard():
    return jsonify(dashboard_payload())


@app.post("/api/refresh")
def post_refresh():
    refresh.run_refresh()
    return jsonify(dashboard_payload())


# --- Jobs ----------------------------------------------------------------------------

@app.get("/api/jobs")
def get_jobs():
    return jsonify(jobs_store.list_jobs(
        status=request.args.get("status") or None,
        query=request.args.get("q") or None,
        sort=request.args.get("sort", "fit"),
    ))


@app.get("/api/jobs/<int:job_id>")
def get_job(job_id):
    if request.args.get("view") == "1":
        jobs_store.mark_viewed(job_id)
    job = jobs_store.get_job(job_id)
    return jsonify(job) if job else error("Job not found.", 404)


@app.post("/api/jobs/<int:job_id>/status")
def post_status(job_id):
    try:
        job = jobs_store.set_status(job_id, (request.get_json(silent=True) or {}).get("status"))
    except LookupError as exc:
        return error(str(exc), 404)
    except ValueError as exc:
        return error(str(exc))
    jobs_store.select_top_jobs()  # a rejected/applied job frees a dashboard slot
    return jsonify(job)


@app.post("/api/jobs/<int:job_id>/application")
def post_application(job_id):
    try:
        return jsonify(jobs_store.save_application(job_id, request.get_json(silent=True) or {}))
    except LookupError as exc:
        return error(str(exc), 404)


@app.post("/api/jobs/<int:job_id>/confirm-active")
def post_confirm_active(job_id):
    job = jobs_store.confirm_active(job_id)
    return jsonify(job) if job else error("Job not found.", 404)


@app.post("/api/jobs/manual")
def post_manual_job():
    try:
        return jsonify(jobs_store.add_manual_job(request.get_json(silent=True) or {})), 201
    except ValueError as exc:
        return error(str(exc))


# --- Profile + settings ------------------------------------------------------------------

@app.get("/api/profile")
def get_profile():
    return jsonify(profile_store.get_profile())


@app.put("/api/profile")
def put_profile():
    try:
        profile_store.save_profile(request.get_json(silent=True))
    except ValueError as exc:
        return error(str(exc))
    jobs_store.reanalyze_all()   # your profile changed -> every score may change
    jobs_store.select_top_jobs()
    return jsonify(profile_store.get_profile())


@app.get("/api/settings")
def get_settings():
    return jsonify(profile_store.get_settings())


@app.put("/api/settings")
def put_settings():
    try:
        saved = profile_store.save_settings(request.get_json(silent=True) or {})
    except ValueError as exc:
        return error(str(exc))
    jobs_store.reanalyze_all()
    jobs_store.select_top_jobs()
    return jsonify(saved)


# --- Resume ----------------------------------------------------------------------------------

@app.get("/api/resume")
def get_resume():
    return jsonify(resume.get_active_resume(include_text=request.args.get("text") == "1"))


@app.post("/api/resume")
def post_resume():
    upload = request.files.get("resume")
    if upload is None:
        return error("No file was sent.")
    try:
        saved = resume.save_resume(upload.filename, upload.read())
    except resume.ResumeError as exc:
        return error(str(exc))
    jobs_store.reanalyze_all()  # the authoritative source changed
    jobs_store.select_top_jobs()
    return jsonify(saved), 201


@app.delete("/api/resume")
def delete_resume():
    resume.delete_active_resume()
    jobs_store.reanalyze_all()
    jobs_store.select_top_jobs()
    return jsonify({"deleted": True})


if __name__ == "__main__":
    port = int(os.environ.get("JOBFISHER_PORT", "5050"))
    print(f"\n  🎣 JobFisher is running →  http://127.0.0.1:{port}\n  (Press Ctrl+C to stop)\n")
    # host 127.0.0.1 = only YOUR computer can open it. Nobody else on your Wi-Fi.
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("JOBFISHER_DEBUG") == "1")
