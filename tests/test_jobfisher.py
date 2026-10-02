"""
Automated tests for JobFisher.   Run from the project folder:

    python -m unittest discover tests -v

WHY TESTS? They let you change code with confidence. If a change breaks the
matcher or the refresh pipeline, a test fails and tells you where.

The postings below are FAKE, written only for testing (company "Example Test Co").
They are never shown in the app — the tests use a temporary database that is
deleted afterwards. Your real data/ folder is never touched.
"""

import os
import shutil
import sys
import tempfile
import unittest

TEMP_DIR = tempfile.mkdtemp(prefix="jobfisher-test-")
os.environ["JOBFISHER_DATA_DIR"] = TEMP_DIR  # must be set BEFORE importing the app
os.environ["JOBFISHER_IGNORE_COOLDOWN"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobfisher import config, jobs_store, refresh, resume, stats  # noqa: E402
from jobfisher.candidate import build_candidate  # noqa: E402
from jobfisher.db import get_connection, init_db  # noqa: E402
from jobfisher.matcher import analyze_job, split_requirements  # noqa: E402
from jobfisher.normalize import dedupe_key, html_to_text, make_job  # noqa: E402

JUNIOR_DESC = """About the role:
Example Test Co is hiring a Junior Front-End Developer for our Tampa office (hybrid).
What you'll do:
- Build responsive websites using HTML, CSS and JavaScript
- Maintain WordPress sites
Requirements:
- 0-1 years of experience
- Familiarity with Git
Nice to have:
- React
- TypeScript
Benefits:
- Health insurance"""

SENIOR_DESC = """Requirements:
- 6+ years of professional experience building web applications
- Expert in React, TypeScript, GraphQL, AWS and Kubernetes
- Bachelor's degree in Computer Science required"""

MARKETING_DESC = """We need a Marketing Coordinator to plan social media campaigns, write email newsletters
and occasionally update our website. Requirements: 2 years marketing experience, strong communication."""


def fake_job(title, desc, company="Example Test Co", location="Tampa, FL", source="FakeSource", sid="1", **kw):
    return make_job(source=source, source_id=sid, title=title, company=company, location=location,
                    description=desc, url="https://example.com/job/" + sid, **kw)


def make_pdf(text):
    """Build a tiny but valid text PDF by hand (no extra libraries needed)."""
    lines = text.split("\n")
    content = "BT /F1 11 Tf 50 750 Td 14 TL " + " ".join(
        "(" + ln.replace("(", "[").replace(")", "]") + ") '" for ln in lines) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = "%PDF-1.4\n", []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    return out.encode("latin-1")


def reset_db():
    for name in os.listdir(TEMP_DIR):
        path = os.path.join(TEMP_DIR, name)
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    init_db()


class MatcherTests(unittest.TestCase):
    def setUp(self):
        self.cand = build_candidate(config.DEFAULT_PROFILE, None)
        self.settings = config.DEFAULT_SETTINGS

    def test_split_required_and_preferred(self):
        b = split_requirements(JUNIOR_DESC)
        self.assertTrue(any("React" in s for s in b["preferred"]))
        self.assertTrue(any("Git" in s for s in b["required"]))
        self.assertTrue(any("Health" in s for s in b["ignored"]))

    def test_junior_role_is_strong(self):
        a = analyze_job(fake_job("Junior Front-End Developer", JUNIOR_DESC, work_arrangement="Hybrid"),
                        self.cand, self.settings)
        self.assertTrue(a["relevant"])
        self.assertEqual(a["fit_category"], "Strong Match")
        self.assertIn("TypeScript (preferred)", a["gaps"])

    def test_senior_role_is_capped_and_honest(self):
        a = analyze_job(fake_job("Senior Front-End Engineer", SENIOR_DESC), self.cand, self.settings)
        self.assertEqual(a["fit_category"], "Poor Match")
        self.assertEqual(a["experience"]["required_years"], 6)
        self.assertIn(a["difficulty"]["level"], ("High", "Very High"))
        # React must NOT be presented as professional experience.
        react = [r for r in a["skills"]["rows"] if r["skill"] == "React"][0]
        self.assertNotIn("Professional", react["evidence"])

    def test_generic_marketing_job_not_relevant(self):
        a = analyze_job(fake_job("Marketing Coordinator", MARKETING_DESC), self.cand, self.settings)
        self.assertFalse(a["relevant"])

    def test_misleading_entry_level_flagged(self):
        desc = "Requirements:\n- 4+ years of experience with JavaScript and React\n- HTML and CSS"
        a = analyze_job(fake_job("Entry Level Web Developer", desc), self.cand, self.settings)
        self.assertTrue(any("misleading" in c for c in a["caps"]))
        self.assertLessEqual(a["fit_score"], 54)

    def test_no_hiring_promises_in_text(self):
        a = analyze_job(fake_job("Junior Web Developer", JUNIOR_DESC), self.cand, self.settings)
        text = str(a).lower()
        for phrase in ("you will get", "chance of being hired", "guaranteed"):
            self.assertNotIn(phrase, text)

    def test_remote_restricted_region(self):
        job = fake_job("Front End Developer", JUNIOR_DESC, location="Remote", work_arrangement="Remote",
                       remote_region="Europe only")
        a = analyze_job(job, self.cand, self.settings)
        self.assertLess(a["location"]["score"], 0.5)

    def test_competitiveness_needs_evidence(self):
        desc = "Build websites with HTML and CSS."
        a = analyze_job(fake_job("Web Designer", desc, location=""), self.cand, self.settings)
        self.assertEqual(a["competitiveness"]["level"], "Insufficient evidence")


class NormalizeTests(unittest.TestCase):
    def test_html_to_text_keeps_structure(self):
        text = html_to_text("<p><strong>Requirements</strong></p><ul><li>HTML</li><li>CSS</li></ul>")
        self.assertIn("Requirements:", text)
        self.assertIn("• HTML", text)

    def test_dedupe_key_ignores_noise(self):
        a = make_job(title="Front-End Developer (Remote)", company="Acme, Inc.", location="Remote", work_arrangement="Remote")
        b = make_job(title="Front End Developer", company="Acme", location="Anywhere", work_arrangement="Remote")
        self.assertEqual(dedupe_key(a), dedupe_key(b))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        reset_db()

    def run_with(self, jobs):
        return refresh.run_refresh(sources={"fake": lambda cfg, s: list(jobs)})

    def test_refresh_stores_ranks_and_tracks_freshness(self):
        jobs = [fake_job("Junior Front-End Developer", JUNIOR_DESC, sid="1", work_arrangement="Hybrid"),
                fake_job("Senior Front-End Engineer", SENIOR_DESC, sid="2"),
                fake_job("Marketing Coordinator", MARKETING_DESC, sid="3")]
        summary = self.run_with(jobs)
        self.assertEqual(summary["scanned"], 3)
        self.assertEqual(summary["relevant"], 2)       # marketing job filtered out
        self.assertEqual(summary["new_count"], 2)
        self.assertEqual(summary["displayed"], 1)      # senior job is below the minimum fit
        top = jobs_store.top_jobs()
        self.assertEqual(top[0]["title"], "Junior Front-End Developer")
        self.assertEqual(top[0]["freshness"], "new")

        # Second refresh with the same job: not "new" any more.
        summary = self.run_with(jobs)
        self.assertEqual(summary["new_count"], 0)
        self.assertEqual(jobs_store.top_jobs()[0]["freshness"], "seen")

        # The employer edits the posting -> "updated".
        edited = [fake_job("Junior Front-End Developer", JUNIOR_DESC + "\n- Webflow is a plus", sid="1",
                           work_arrangement="Hybrid")]
        summary = self.run_with(edited)
        self.assertEqual(summary["updated_count"], 1)
        self.assertEqual(jobs_store.top_jobs()[0]["freshness"], "updated")

    def test_duplicates_merge_and_prefer_direct_url(self):
        a = fake_job("Junior Web Developer", JUNIOR_DESC, source="Aggregator", sid="9")
        b = fake_job("Junior Web Developer", JUNIOR_DESC, source="Greenhouse", sid="77", is_direct_url=True)
        b["url"] = "https://careers.example.com/apply/77"
        self.run_with([a, b])
        jobs = jobs_store.list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["url"], "https://careers.example.com/apply/77")
        self.assertEqual(sorted(jobs[0]["sources"]), ["Aggregator", "Greenhouse"])

    def test_rejected_job_never_returns_to_top(self):
        self.run_with([fake_job("Junior Web Developer", JUNIOR_DESC, sid="5")])
        job_id = jobs_store.top_jobs()[0]["id"]
        jobs_store.set_status(job_id, "Rejected")
        jobs_store.select_top_jobs()
        self.run_with([fake_job("Junior Web Developer", JUNIOR_DESC, sid="5")])
        self.assertEqual(jobs_store.top_jobs(), [])
        self.assertEqual(jobs_store.get_job(job_id)["status"], "Rejected")

    def test_applied_moves_to_tracker(self):
        self.run_with([fake_job("Junior Web Developer", JUNIOR_DESC, sid="6")])
        job_id = jobs_store.top_jobs()[0]["id"]
        jobs_store.set_status(job_id, "Applied")
        jobs_store.set_status(job_id, "Interview")
        t = stats.tracker()
        self.assertEqual(t["applications_submitted"], 1)
        self.assertEqual(t["interviews_received"], 1)
        self.assertEqual(t["interview_rate"], 100)

    def test_failing_source_does_not_break_refresh(self):
        def broken(cfg, s):
            raise ConnectionError("network down")
        summary = refresh.run_refresh(sources={"broken": broken,
                                               "fake": lambda c, s: [fake_job("Web Designer", JUNIOR_DESC, sid="7")]})
        statuses = {r["source"]: r["status"] for r in summary["source_report"]}
        self.assertEqual(statuses["broken"], "error")
        self.assertEqual(summary["new_count"], 1)

    def test_keeps_previous_jobs_when_nothing_new(self):
        self.run_with([fake_job("Junior Web Developer", JUNIOR_DESC, sid="8")])
        summary = self.run_with([])
        self.assertEqual(summary["new_count"], 0)
        self.assertEqual(len(jobs_store.top_jobs()), 1)

    def test_stickiness_keeps_current_top(self):
        """A newcomer must be meaningfully better (more than the stickiness
        bonus) to replace a job that's already on the dashboard."""
        from jobfisher.profile_store import save_settings
        save_settings({"display": {"top_n": 1}})
        now = "2026-10-02T12:00:00+00:00"
        with get_connection() as conn:
            for key, score, top in (("a", 80, 1), ("b", 82, 0)):
                conn.execute("INSERT INTO jobs (dedupe_key, title, company, date_discovered, last_seen_active, "
                             "is_relevant, fit_score, in_top8, status) VALUES (?, ?, 'Example Test Co', ?, ?, 1, ?, ?, 'New')",
                             (key, key, now, now, score, top))
        jobs_store.select_top_jobs()
        self.assertEqual([j["title"] for j in jobs_store.top_jobs()], ["a"])   # 82 isn't enough
        with get_connection() as conn:
            conn.execute("UPDATE jobs SET fit_score = 90 WHERE dedupe_key = 'b'")
        jobs_store.select_top_jobs()
        self.assertEqual([j["title"] for j in jobs_store.top_jobs()], ["b"])   # 90 is a real improvement

    def test_manual_job(self):
        job = jobs_store.add_manual_job({"title": "Junior Web Designer", "company": "Example Test Co",
                                         "location": "Lakeland, FL", "description": JUNIOR_DESC,
                                         "url": "https://example.com/apply"})
        self.assertTrue(job["is_manual"])
        self.assertTrue(job["in_top8"])
        with self.assertRaises(ValueError):
            jobs_store.add_manual_job({"title": "x", "company": "y", "description": "too short"})


class SourceParserTests(unittest.TestCase):
    """Each source turns its own JSON format into our job shape. We can't call
    the real APIs in a test, so we feed each parser a small sample shaped like
    that API's documented response and check the mapping."""

    def patch(self, module, payload):
        original = module.get_json
        module.get_json = lambda url, params=None: payload
        self.addCleanup(setattr, module, "get_json", original)

    def test_parsers(self):
        from jobfisher.sources import greenhouse, jobicy, lever, remotive, themuse
        settings = config.DEFAULT_SETTINGS
        self.patch(themuse, {"page_count": 1, "results": [{
            "id": 1, "name": "Junior Web Developer", "contents": "<p>HTML and CSS</p>",
            "publication_date": "2026-09-30T10:00:00Z", "locations": [{"name": "Flexible / Remote"}],
            "levels": [{"name": "Entry Level"}], "company": {"name": "Example Test Co"},
            "refs": {"landing_page": "https://example.com/a"}}]})
        job = themuse.fetch(settings["sources"]["themuse"], settings)[0]
        self.assertEqual((job["work_arrangement"], job["level_hint"], job["date_posted"]),
                         ("Remote", "Entry Level", "2026-09-30"))

        self.patch(remotive, {"jobs": [{"id": 2, "title": "Front End Dev", "company_name": "Example Test Co",
                                        "job_type": "full_time", "candidate_required_location": "USA Only",
                                        "salary": "", "description": "<p>React</p>", "url": "https://example.com/b",
                                        "publication_date": "2026-09-29T00:00:00"}]})
        job = remotive.fetch(settings["sources"]["remotive"], settings)[0]
        self.assertIsNone(job["salary_text"])          # empty salary stays empty — never invented
        self.assertEqual(job["employment_type"], "Full-time")

        self.patch(jobicy, {"jobs": [{"id": 3, "jobTitle": "Web Designer", "companyName": "Example Test Co",
                                      "jobGeo": "USA", "jobLevel": "Entry", "jobType": ["full-time"],
                                      "jobDescription": "<p>Figma</p>", "url": "https://example.com/c",
                                      "pubDate": "2026-09-28 10:00:00", "salaryMin": 50000, "salaryMax": 60000,
                                      "salaryCurrency": "USD", "salaryPeriod": "year"}]})
        job = jobicy.fetch({"tags": ["frontend"], "geo": "usa"}, settings)[0]
        self.assertEqual(job["salary_text"], "$50,000 – $60,000 / year")

        self.patch(greenhouse, {"jobs": [{"id": 4, "title": "UI Developer", "location": {"name": "Tampa, FL"},
                                          "absolute_url": "https://example.com/d",
                                          "content": "&lt;p&gt;JavaScript&lt;/p&gt;", "updated_at": "2026-09-27T00:00:00Z"}]})
        job = greenhouse.fetch({"boards": ["exampletestco"]}, settings)[0]
        self.assertTrue(job["is_direct_url"])
        self.assertEqual(job["description"], "JavaScript")

        self.patch(lever, [{"id": "5", "text": "Web Developer", "hostedUrl": "https://example.com/e",
                            "createdAt": 1790900000000, "workplaceType": "hybrid",
                            "categories": {"location": "Orlando, FL", "commitment": "Full-time"},
                            "descriptionPlain": "Build sites.", "lists": [{"text": "Requirements",
                                                                         "content": "<li>HTML</li>"}]}])
        job = lever.fetch({"companies": ["exampletestco"]}, settings)[0]
        self.assertEqual(job["work_arrangement"], "Hybrid")
        self.assertIn("Requirements:", job["description"])

    def test_adzuna_skips_without_key_and_drops_predicted_salary(self):
        from jobfisher.sources import adzuna
        from jobfisher.sources.http import SourceSkipped
        os.environ.pop("ADZUNA_APP_ID", None)
        with self.assertRaises(SourceSkipped):
            adzuna.fetch(config.DEFAULT_SETTINGS["sources"]["adzuna"], config.DEFAULT_SETTINGS)
        os.environ.update({"ADZUNA_APP_ID": "x", "ADZUNA_APP_KEY": "y"})
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in ("ADZUNA_APP_ID", "ADZUNA_APP_KEY")])
        self.patch(adzuna, {"results": [{"id": 6, "title": "Web Developer", "company": {"display_name": "Example Test Co"},
                                         "location": {"display_name": "Lakeland, Polk County"},
                                         "salary_min": 45000, "salary_max": 45000, "salary_is_predicted": "1",
                                         "description": "HTML CSS", "redirect_url": "https://example.com/f",
                                         "created": "2026-09-30T00:00:00Z"}]})
        job = adzuna.fetch({"what": ["web developer"]}, config.DEFAULT_SETTINGS)[0]
        self.assertIsNone(job["salary_text"])   # Adzuna's estimate is discarded


class ResumeTests(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_upload_parse_and_replace(self):
        pdf = make_pdf("Test Person\nSKILLS\nHTML, CSS, JavaScript, Figma\nPROJECTS\nPortfolio site built with React\n"
                       "EDUCATION\nAssociate of Science, in progress")
        saved = resume.save_resume("Test_Resume.pdf", pdf)
        names = {s["name"]: s["found_in"] for s in saved["parsed"]["skills"]}
        self.assertIn("projects", names["React"])
        self.assertIn("skills", names["HTML"])
        first_files = os.listdir(os.path.join(TEMP_DIR, "resumes"))

        # A bad replacement must NOT remove the existing resume.
        with self.assertRaises(resume.ResumeError):
            resume.save_resume("fake.pdf", b"not a pdf at all")
        self.assertEqual(resume.get_active_resume()["original_name"], "Test_Resume.pdf")
        self.assertEqual(os.listdir(os.path.join(TEMP_DIR, "resumes")), first_files)

        # A good replacement swaps it and removes the old file.
        resume.save_resume("Test_Resume_v2.pdf", pdf)
        self.assertEqual(resume.get_active_resume()["original_name"], "Test_Resume_v2.pdf")
        self.assertEqual(len(os.listdir(os.path.join(TEMP_DIR, "resumes"))), 1)

        # Resume evidence changes the candidate profile labels.
        cand = jobs_store.current_candidate()
        self.assertTrue(cand["has_resume"])
        self.assertTrue(cand["skills"]["Figma"]["on_resume"])

        resume.delete_active_resume()
        self.assertIsNone(resume.get_active_resume())
        self.assertEqual(os.listdir(os.path.join(TEMP_DIR, "resumes")), [])

    def test_rejects_non_pdf(self):
        with self.assertRaises(resume.ResumeError):
            resume.save_resume("resume.docx", b"PK....")


class ApiTests(unittest.TestCase):
    def setUp(self):
        reset_db()
        import app as app_module
        self.client = app_module.app.test_client()

    def test_endpoints(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        data = self.client.get("/api/dashboard").get_json()
        self.assertIn("top_jobs", data)
        profile = self.client.get("/api/profile").get_json()
        self.assertEqual(profile["name"], "Chad Blincoe")
        bad = self.client.put("/api/profile", json={"skills": "not a list"})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.client.put("/api/settings", json={"weights": {"skills": -1}}).status_code, 400)
        r = self.client.post("/api/jobs/manual", json={"title": "Junior Web Developer", "company": "Example Test Co",
                                                       "location": "Tampa, FL", "description": JUNIOR_DESC})
        self.assertEqual(r.status_code, 201)
        job_id = r.get_json()["id"]
        self.assertEqual(self.client.get(f"/api/jobs/{job_id}?view=1").get_json()["status"], "Viewed")
        self.assertEqual(self.client.post(f"/api/jobs/{job_id}/status", json={"status": "Bogus"}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/jobs/{job_id}/status", json={"status": "Saved"}).get_json()["status"], "Saved")
        r = self.client.post(f"/api/jobs/{job_id}/application", json={"date_applied": "2026-10-02", "notes": "Sent portfolio"})
        self.assertEqual(r.get_json()["application"]["notes"], "Sent portfolio")
        self.assertEqual(self.client.get("/api/jobs/9999").status_code, 404)
        import io
        r = self.client.post("/api/resume", data={"resume": (io.BytesIO(make_pdf("SKILLS\nHTML CSS JavaScript and more text here")), "r.pdf")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201)


def tearDownModule():
    shutil.rmtree(TEMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
