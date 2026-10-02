"""
Lever job boards — another common careers-page host with a free public
postings API. Add company slugs in Settings (jobs.lever.co/<slug>).
"""

from ..normalize import format_salary, html_to_text, iso_date, make_job
from .http import SourceSkipped, get_json

URL = "https://api.lever.co/v0/postings/{company}"
WORKPLACE = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site", "on-site": "On-site"}


def fetch(cfg, settings):
    companies = [c.strip() for c in cfg.get("companies", []) if c.strip()]
    if not companies:
        raise SourceSkipped("No company boards added yet (optional — add them in Settings).")
    jobs = []
    for company in companies:
        data = get_json(URL.format(company=company), {"mode": "json"})
        for item in data if isinstance(data, list) else []:
            parts = [item.get("descriptionPlain") or ""]
            for section in item.get("lists", []):
                parts.append(f"{section.get('text', '')}:")
                parts.append(html_to_text(section.get("content")))
            parts.append(item.get("additionalPlain") or "")
            categories = item.get("categories") or {}
            pay = item.get("salaryRange") or {}
            jobs.append(make_job(
                source="Lever",
                source_id=f"{company}-{item.get('id')}",
                title=item.get("text"),
                company=company.replace("-", " ").title(),
                location=categories.get("location"),
                work_arrangement=WORKPLACE.get((item.get("workplaceType") or "").lower()),
                employment_type=categories.get("commitment"),
                salary_text=format_salary(pay.get("min"), pay.get("max"), pay.get("currency") or "USD",
                                          (pay.get("interval") or "").replace("-", " ")) if pay else None,
                salary_min=pay.get("min"),
                salary_max=pay.get("max"),
                description="\n".join(p for p in parts if p),
                url=item.get("hostedUrl") or item.get("applyUrl"),
                is_direct_url=True,
                date_posted=iso_date(item.get("createdAt")),
            ))
    return jobs
