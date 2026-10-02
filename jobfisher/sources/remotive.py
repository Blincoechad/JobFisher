"""
Remotive — free public remote-jobs API (no key).
Docs: https://github.com/remotive-com/remote-jobs-api
Terms: credit Remotive and link back to the listing (we keep their URL);
call at most ~4 times a day (cooldown_hours = 6 in settings).
"""

from ..normalize import html_to_text, iso_date, make_job
from .http import get_json

URL = "https://remotive.com/api/remote-jobs"
JOB_TYPES = {"full_time": "Full-time", "part_time": "Part-time", "contract": "Contract",
             "freelance": "Freelance", "internship": "Internship"}


def fetch(cfg, settings):
    jobs = []
    for category in cfg.get("categories", ["software-dev"])[:2]:  # max 2 calls per minute allowed
        data = get_json(URL, {"category": category})
        for item in data.get("jobs", []):
            jobs.append(make_job(
                source="Remotive",
                source_id=str(item.get("id")),
                title=item.get("title"),
                company=item.get("company_name"),
                location="Remote",
                work_arrangement="Remote",
                remote_region=item.get("candidate_required_location"),
                employment_type=JOB_TYPES.get(item.get("job_type"), item.get("job_type")),
                salary_text=(item.get("salary") or "").strip() or None,  # as written by the employer
                description=html_to_text(item.get("description")),
                url=item.get("url"),
                is_direct_url=False,
                date_posted=iso_date(item.get("publication_date")),
            ))
    return jobs
