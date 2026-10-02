# JobFisher Learning Guide

This guide explains **what** each part of JobFisher does, **why** it was built that way, and **how** the pieces talk to each other. Read it alongside the code. Every file also starts with a comment block that explains its job.

---

## 1. The big picture

```
 You (browser)
    │  click "Refresh jobs"
    ▼
 FRONT END   templates/index.html + static/css + static/js/*.js
    │  fetch("/api/refresh", { method: "POST" })      ← HTTP request
    ▼
 ROUTES      app.py  (Flask: URL → Python function)
    │  refresh.run_refresh()
    ▼
 APP LOGIC   jobfisher/*.py
    │  sources → normalize → matcher → ranking → stats
    ▼
 DATA / API  jobfisher/sources/*.py  →  The Muse, Remotive, Jobicy, Adzuna, Greenhouse, Lever
    ▼
 STORAGE     data/jobfisher.db (SQLite)  +  data/resumes/*.pdf
```

> **Remember:** The front end *displays* data. The back end *processes* data. The database *persists* data.

### File map

| File | Layer | Job in one sentence |
|---|---|---|
| `app.py` | Routes | Connects each URL to a function and returns JSON. Deliberately thin. |
| `jobfisher/db.py` | Storage | Creates the tables and opens database connections. |
| `jobfisher/config.py` | Config | Default settings and the starting profile (copied into the DB once). |
| `jobfisher/profile_store.py` | Logic | Load/save your profile and settings. |
| `jobfisher/resume.py` | Logic | Validate → save → extract → parse your resume PDF. |
| `jobfisher/skills.py` | Logic | The skill dictionary: recognises "React.js" and "ReactJS" as **React**. |
| `jobfisher/candidate.py` | Logic | Merges resume + profile into the **Structured Candidate Profile**. |
| `jobfisher/matcher.py` | Logic | Scores one job against you and explains every part of the score. |
| `jobfisher/normalize.py` | Logic | Converts every source's format into one job shape; spots duplicates. |
| `jobfisher/sources/*.py` | Data/API | One file per job source; all share the same `fetch()` "contract". |
| `jobfisher/refresh.py` | Logic | The Refresh pipeline, step by step. |
| `jobfisher/jobs_store.py` | Logic | Statuses, manual jobs, re-scoring, and choosing the top 8. |
| `jobfisher/stats.py` | Logic | Job market, learning gaps and tracker numbers (counted, never estimated). |
| `static/js/api.js` | Front end | The one place the browser calls the server. |
| `static/js/format.js` | Front end | Escaping (security), dates, colours, toast messages. |
| `static/js/cards.js` | Front end | Draws a job card and the full-analysis dialog. |
| `static/js/dashboard.js`, `tracker.js`, `profile.js`, `settings.js` | Front end | One file per page. |
| `static/js/main.js` | Front end | Starts everything and switches pages (#dashboard, #tracker…). |
| `tests/test_jobfisher.py` | Tests | 23 automated checks. |

---

## 2. Follow one click: what "Refresh jobs" actually does

1. **`dashboard.js` → `refreshJobs()`** disables the button, shows "Searching for new opportunities…", and calls `api("/api/refresh", { method: "POST" })`.
2. **`api.js`** sends the HTTP request with `fetch()` and waits for JSON.
3. **`app.py` → `post_refresh()`** calls `refresh.run_refresh()`.
4. **`refresh.py`** runs the pipeline:
   1. `fetch_all_sources()` loops over `sources/`. Each source is wrapped in `try/except`, so one failure can't stop the others. Cooldowns protect the APIs' rate limits.
   2. `dedupe_batch()` merges the same job found on two sites (company + title + city) and keeps the company's direct link.
   3. Each job is analysed once to decide **is this really a web design/dev job?** Generic marketing jobs that only mention "website" are dropped.
   4. `store_jobs()` compares against the database: **new** (never seen), **updated** (the text changed), or **seen before**. `date_discovered` is never overwritten, so an old job can't pretend to be new.
   5. `mark_unseen()` + `expire_old_jobs()`: jobs that stop appearing in their source become "⚠ Listing may be stale" after 14 days and *Expired* after 30 (unless you're tracking them).
   6. `jobs_store.reanalyze_all()` re-scores **every** stored job against your **current** profile.
   7. `jobs_store.select_top_jobs()` picks the strongest 8 (rules in section 4).
   8. The numbers are saved in the `refreshes` table for the Search Summary panel.
5. **`app.py`** returns `dashboard_payload()`: top jobs, summary, market, gaps and tracker, all in one JSON response.
6. **`dashboard.js` → `renderDashboard()`** turns that JSON into HTML.

> **Remember:** a request goes *down* the layers and the response comes back *up*. When something breaks, find which layer the data stopped at.

---

## 3. The stages, and the thinking behind each

Each stage is a logical **Git commit point**.

### Stage 1: Project setup
- **What:** `requirements.txt`, `.gitignore`, `.env.example`, folder layout.
- **Why Flask + SQLite + plain JS?** You already know basic Flask, and there's no build step to debug. SQLite is a real SQL database that ships inside Python, at $0. React would add a build system without solving a problem this app has.
- **`.env` vs `.env.example`:** `.env` holds real secrets (your Adzuna key) and is git-ignored. `.env.example` lists the *names* of settings with no values and **is** committed, so future-you knows what to fill in. (`.env.local` is a convention some tools use for machine-specific overrides; we don't need it.)
- **Commit:** `chore: project setup`

### Stage 2: Database (`db.py`)
- **What:** seven tables: `jobs`, `refreshes`, `profile`, `settings`, `resumes`, `applications`, `status_history`, plus `source_calls` for rate limits.
- **Why:** browser memory disappears when you close the tab; a database file doesn't.
- **Concept: context manager.** `with get_connection() as conn:` opens the database, **commits** if the block finishes, **rolls back** if an error happens, and always **closes**. That's why a failed resume upload can never leave half-saved rows.
- **Concept: JSON columns.** SQLite has no "list" type, so lists (like `sources_json`) are stored as JSON text and converted with `to_json()` / `from_json()`.
- **Commit:** `feat: add SQLite schema`

### Stage 3: Profile (`config.py`, `profile_store.py`)
- **What:** your profile is one JSON document. On first run it's seeded from `config.py`; after that, the database copy is the real one.
- **Why `deep_merge()`?** If a future version adds a new setting, your saved settings won't have it. Merging gives new keys their default while keeping your changes.
- **Validation:** `validate_profile()` rejects bad shapes *before* saving, because user input can't be assumed valid.
- ⚠ **Review the seed profile.** It was built from your spec and from what you've told Claude about your work. Anything wrong should be fixed on the Profile page.
- **Commit:** `feat: add editable profile`

### Stage 4: Resume (`resume.py`)
- **What:** `validate_upload` → write file → `extract_text` (pypdf) → `parse_resume_text` → activate → delete old.
- **Why this order?** "Save new first, delete old last." If any step fails, the new file is removed and your previous resume is untouched.
- **Why validate?** A file named `.pdf` isn't necessarily a PDF. Real PDFs start with the bytes `%PDF-`, so we check that.
- **Why a random file name?** Using your original filename as a path would allow tricks like `../../file.pdf` (*path traversal*). We store `3f9a…c1.pdf` and keep the original name only for display.
- **Why parse sections?** *Where* a skill appears matters: React under "Projects" is project experience, not a job.
- **Commit:** `feat: add persistent resume upload`

### Stage 5: Structured candidate profile (`skills.py`, `candidate.py`)
- **What:** each skill you have gets an **evidence type** and a **weight**:

  | Evidence | Weight | Shown as |
  |---|---|---|
  | Professional web job | 1.00 | Professional experience |
  | Freelance/client work | 1.00 | Client/freelance experience |
  | Projects | 0.90 | Project experience |
  | Coursework | 0.85 | Academic coursework |
  | Resume (skills list) | 0.80 | Listed on resume |
  | Profile only (resume uploaded) | 0.60 | Profile summary only (not on resume) |

  "Still developing" multiplies by 0.85 and adds "— still developing" to the label. Profile evidence not confirmed by the resume gets "(not on resume)".
- **Why:** this is how the app avoids inflating your qualifications (instruction #10). React from a team project is labelled *Project experience*, never *Professional*.
- **Commit:** `feat: build structured candidate profile`

### Stage 6: Matching engine (`matcher.py`), explained in section 4
- **Commit:** `feat: add explainable job matching`

### Stage 7: Sources (`sources/`, `normalize.py`)
- **The "contract":** every source has `fetch(source_settings, app_settings)` and returns jobs in `make_job()` shape. `refresh.py` loops over them without knowing their internals. Adding a source means one new file plus one line in `sources/__init__.py`.
- **Honesty rules in the parsers:** Remotive's empty salary stays empty. Adzuna's *predicted* salary is thrown away. Only employer-stated pay is shown.
- **Security:** job descriptions come from other websites, so `html_to_text()` strips their HTML, and the front end escapes all text again before display (see `esc()` in `format.js`).
- **Commit:** `feat: add free job sources`

### Stage 8–10: Refresh, freshness, history (`refresh.py`, `jobs_store.py`)
- See section 2. Statuses: New, Viewed, Saved, Applied, Interview, Offer, Rejected, Expired, Hidden, No Longer Relevant. **Offer** was added because the spec's history section tracks offers.
- **Rejected / Hidden / No Longer Relevant** never return to the top 8. **Applied / Interview / Offer** move to the tracker.
- **Commits:** `feat: add refresh pipeline`, `feat: add job lifecycle and tracker`

### Stage 11: Stats (`stats.py`)
- Every number is a **count** from your own database. Learning gaps say "share of N relevant jobs" and warn when N is small. Nothing tells you that you *must* learn something.
- **Commit:** `feat: add market, gap and tracker stats`

### Stage 12: Front end (`templates/`, `static/`)
- **One page, four views.** `main.js` shows one `<section>` at a time based on `location.hash`. That's a "hash router", the simplest single-page app pattern there is.
- **ES modules:** `<script type="module">` lets files `import` from each other, so each file has one job.
- **Event delegation:** `dashboard.js` puts **one** click listener on the cards container. It works for every card, including cards drawn later, by checking `event.target.closest("button[data-action]")`.
- **CSS custom properties:** colours are tokens in `:root`, and dark mode just swaps their values.
- **Commit:** `feat: add dashboard UI`

---

## 4. How a job is scored

### Application Fit Score (0–100)
Each factor is scored 0.0–1.0 by its own function, then combined with your weights (Settings):

| Factor | Default weight | Function | What it looks at |
|---|---|---|---|
| Required skills | 40% | `score_skills` | Skills in required vs preferred sentences × your evidence weight. Preferred skills count half. |
| Experience | 20% | `score_experience` | Years requested vs. your web experience: professional + **half** of freelance. Some employers count freelance work and some don't, so half is the honest middle. |
| Portfolio | 15% | `score_portfolio` | Which of your projects and client work use the requested skills. |
| Education | 10% | `score_education` | Degree requirements, and whether "or equivalent experience" is accepted. Your associate degree is treated as *in progress*. |
| Job level | 10% | `score_level` | Senior / mid / junior from the title, the source's level label, and entry-level wording. |
| Location | 5% | `score_location` | Remote (and whether it's open to the US), your area list, elsewhere in Florida, or relocation. |

**Required vs preferred:** `split_requirements()` uses the latest heading ("Nice to have:") *and* words inside the sentence ("…is a plus"). Benefits and "About us" sections are ignored.

**Honesty caps.** Some single facts outweigh everything else:
- Senior title, or 5+ years required → capped at **Poor Match**
- 3–4 years required → capped at **Stretch Match**
- Not really a web role → **Poor Match**
- "Entry-level" title but 3+ years requested → flagged as *possibly misleading*

**Categories:** 75+ Strong · 55+ Possible · 35+ Stretch · below 35 Poor.

### Separate ratings (not part of the fit score)
- **Application difficulty:** points for years requested, missing required skills, long tech lists, specialised tech (AWS, Kubernetes…), strict degrees, required certifications, and seniority. Each reason is listed.
- **Interview competitiveness:** needs **at least two pieces of evidence** from the posting, otherwise it says **"Insufficient evidence"**. There is no free source of applicant counts, and the app says so instead of inventing them.
- **Company hiring context:** based **only on postings JobFisher has stored from that company**. With one posting it says "Insufficient evidence". It gets more useful as your history grows.

### Choosing the 8 (`select_top_jobs`)
1. Only relevant jobs with status New / Viewed / Saved, at or above the minimum fit (default 35).
2. Rank by fit score, **not** by newest.
3. Jobs already on the dashboard get +3 "stickiness" points, so a newcomer must be meaningfully better to replace one (spec section 8).
4. Stale listings get −10 points so old jobs don't fill slots.
5. If fewer than 8 qualify, fewer are shown. Showing 5 good jobs beats padding the list with poor ones.

---

## 5. Decisions and limitations (please read)

| Spec asked for | What was built | Why |
|---|---|---|
| "Evaluated chance of getting the position" | Fit score + gaps, never hiring odds | The data can't determine hiring probability (your own instruction #12). |
| Search LinkedIn / Indeed | Free official APIs + **Add a job manually** | Those sites forbid automated scraping (instruction #16 says permitted methods only). |
| Configurable radius around Lakeland | Real radius via **Adzuna** (free key); other sources use your list of accepted places | The no-key APIs only filter by city name. |
| Public applicant/interview data | "Insufficient evidence" unless the posting itself gives signals | No free, permitted source of applicant volumes exists. |
| Company research (internships, junior history) | Built from JobFisher's own stored postings | Researching companies across the web would need scraping or a paid AI API. |
| Remove expired listings | Inferred: not seen in its source → stale → expired | The APIs don't report when a job closes. |
| AI analysis | Rule-based engine, with clear seams for AI later (section 7) | $0 budget, fully explainable, works offline. |

Only *relevant* postings are stored. Others are counted in "Jobs scanned" and then discarded, which keeps the database focused.

---

## 6. Debugging: where to look

1. **What is failing?** Read the toast message, or *Source details* under Search Summary.
2. **Where is it failing?**
   - **Browser DevTools** (`Cmd + Option + I`): the **Console** tab shows JavaScript errors with file and line numbers. The **Network** tab shows each `/api/...` request: click one to see what was sent and what came back.
   - **Terminal** running `python app.py`: Python errors print here with a traceback. Read it **bottom-up**: the last line is the error, and the lines above show the path through your files.
3. **What error is produced?** Copy the exact message, which is usually specific.
4. **What caused it?** Find the layer where the data stopped looking right (section 2).
5. **Smallest fix?** Change one thing, re-run, and run the tests.

Common ones:
- `ModuleNotFoundError: No module named 'flask'`: the virtual environment isn't active. Run `source venv/bin/activate`.
- A source says *Couldn't connect*: it's the internet or that site, not your code. Other sources still work.
- A source says *data JobFisher couldn't read*: that API changed its format. Compare its JSON to the field names in its `sources/*.py` file.

---

## 7. Future AI integration (free path)

The architecture was designed so AI can be dropped in without rewriting the app:
- `skills.find_skills(text)`: an AI could extract skills more accurately. Same input (text), same output (set of names).
- `matcher.analyze_job(...)`: an AI could write the summary or detect misleading "entry-level" listings, while the rules stay as the fact-checker.
- The raw description is stored for every job, so any AI conclusion can be traced back to the source text.

A **$0** option is [Ollama](https://ollama.com), which runs open models locally, so your resume never leaves your Mac. Anything paid would be discussed with you first.

---

## 8. Try it yourself (exercises)

1. **Predict, then check:** in `matcher.py`, what happens to the fit score if you change `CATEGORIES` so Strong starts at 80? Change it, run the tests, and see which test fails and why.
2. **Add a skill:** add `"Figma Dev Mode"` (or anything) to `SKILL_LIBRARY` in `skills.py`, with a regex. Test it in Python:
   ```python
   from jobfisher.skills import find_skills
   find_skills("Experience with Figma Dev Mode")
   ```
3. **Change the UI:** in `cards.js`, show `job.employment_type` on the card's meta line.
4. **Explain it back:** in your own words, why does `save_resume()` delete the old file *last*?
5. **Bigger:** add a new source. Copy `greenhouse.py`, change the URL and field names, then register it in `sources/__init__.py` and `config.py`.

---

## 9. Git

```bash
cd ~/Desktop/JobSearchDashboard
git init
git add .
git status          # check: data/, venv/ and .env must NOT be listed
git commit -m "feat: initial JobFisher build"
```

`.gitignore` keeps `data/` (your resume and database), `.env` (keys) and `venv/` out of GitHub. Always run `git status` before your first push.
