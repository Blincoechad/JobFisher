"""
Jobicy — free public remote-jobs API (no key).
Docs: https://jobicy.com/jobs-rss-feed
Terms: keep Jobicy as the source and use their job URL; poll at most hourly.
"""

from ..normalize import format_salary, html_to_text, iso_date, make_job
from .http import get_json

URL = "https://jobicy.com/api/v2/remote-jobs"


def fetch(cfg, settings):
    jobs = []
    for tag in cfg.get("tags", []) or [""]:
        params = {"count": 100, "geo": cfg.get("geo", "usa")}
        if tag:
            params["tag"] = tag
        data = get_json(URL, params)
        for item in data.get("jobs", []):
            salary = format_salary(
                item.get("salaryMin") or item.get("annualSalaryMin"),
                item.get("salaryMax") or item.get("annualSalaryMax"),
                item.get("salaryCurrency") or "USD",
                item.get("salaryPeriod") or "",
            )
            types = item.get("jobType") or []
            jobs.append(make_job(
                source="Jobicy",
                source_id=str(item.get("id")),
                title=html_to_text(item.get("jobTitle")),
                company=item.get("companyName"),
                location="Remote",
                work_arrangement="Remote",
                remote_region=item.get("jobGeo"),
                employment_type=", ".join(types) if isinstance(types, list) else types,
                salary_text=salary,
                salary_min=item.get("salaryMin") or item.get("annualSalaryMin"),
                salary_max=item.get("salaryMax") or item.get("annualSalaryMax"),
                description=html_to_text(item.get("jobDescription") or item.get("jobExcerpt")),
                url=item.get("url"),
                is_direct_url=False,
                date_posted=iso_date(item.get("pubDate")),
                level_hint=item.get("jobLevel"),
            ))
    return jobs
