# 🎣 JobFisher

A private, personal job-search dashboard. Press **Refresh jobs** and JobFisher searches free job APIs for web design and development openings, scores each one against your resume and profile, and shows the **8 strongest current opportunities**, with an honest explanation of why each one fits and where the gaps are.

JobFisher measures how well a posting lines up with your documented experience. **It does not predict whether you'll be hired.**

---

## Quick start (Mac)

You need Python 3.9 or newer. macOS includes it; check with `python3 --version` in Terminal.

```bash
cd ~/Desktop/JobSearchDashboard
bash start.sh
```

The first run creates a virtual environment (`venv/`) and installs the 3 dependencies. After that it just starts the server. Then open **http://127.0.0.1:5050** in your browser.

To stop the server, press `Ctrl + C` in Terminal.

<details>
<summary>Doing it by hand instead (what start.sh does)</summary>

```bash
python3 -m venv venv              # an isolated Python just for this project
source venv/bin/activate          # use it in this Terminal window
pip install -r requirements.txt   # Flask, pypdf, requests
python app.py                     # start the server
```
</details>

### First things to do
1. **Profile & resume:** upload your resume PDF. Then review the pre-filled profile and fix anything that's inaccurate. Tick "still developing" on skills you only know at a basic level.
2. **Dashboard:** press **Refresh jobs**.
3. Open a card's **See full analysis** to see the score breakdown, skill-by-skill evidence, and the original posting.
4. Use **Save**, **Not interested**, or the status buttons (Applied, Interview, Rejected…) to manage jobs. The **Tracker** tab shows everything.

---

## Where jobs come from (all free, no scraping)

| Source | What it adds | Notes |
|---|---|---|
| The Muse API | Entry-level jobs in Tampa, Orlando, Lakeland + remote | No key needed |
| Remotive API | Remote software and design jobs | Max ~4 searches/day, so JobFisher enforces a 6-hour cooldown |
| Jobicy API | Remote jobs open to the USA | 1-hour cooldown |
| Adzuna API | A real **radius search** around Lakeland | **Optional.** Needs a free key (below) |
| Greenhouse / Lever | Specific companies' own career pages | Add company tokens in Settings |
| Add a job manually | Anything you find on LinkedIn, Indeed, etc. | Those sites don't allow automated access |

**Optional Adzuna key:** sign up at https://developer.adzuna.com, copy `.env.example` to a new file named `.env`, and paste your `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`. Restart the app.

---

## Privacy: where your data lives

| What | Where | Persists after restart? | How to replace / delete |
|---|---|---|---|
| Resume PDF | `data/resumes/` (random file name) | Yes | Profile page → **Replace resume** / **Delete resume** |
| Text extracted from resume | `data/jobfisher.db` | Yes | Same as above (deleted together) |
| Jobs, statuses, notes, profile, settings | `data/jobfisher.db` | Yes | Delete the `data/` folder to start completely fresh |

* The resume is read **locally** with `pypdf`. It is never sent to any website or AI service.
* The server only listens on `127.0.0.1`, so only your computer can open the dashboard.
* `data/` and `.env` are listed in `.gitignore`, so they never get committed to GitHub.
* A new resume is saved and verified **before** the old one is removed, so a failed upload never leaves you without a resume.

---

## Running the tests

```bash
source venv/bin/activate
python -m unittest discover tests -v
```

23 tests cover the matcher, the refresh pipeline (new/updated/seen, duplicates, rejected jobs, failing sources), source parsers, resume upload/replace/delete, and the API. They use a temporary database and never touch `data/`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Address already in use` | Another app is on port 5050. Add `JOBFISHER_PORT=5051` to `.env`. |
| A source shows **error** in *Source details* | Read its message. Usually it's the internet connection, or a rate limit (it recovers after the cooldown). Other sources keep working. |
| "No readable text was found" on resume upload | The PDF is an image (scanned). Export it again from Word, Google Docs or Canva as a regular PDF. |
| Scores look wrong after editing your profile | Saving the profile re-scores everything automatically. Check the job's **See full analysis** to see which factor caused it. |
| Want a clean slate | Stop the server and delete the `data/` folder. |

The **[Learning guide](docs/LEARNING_GUIDE.md)** explains how every part of the app works and why it was built that way.
