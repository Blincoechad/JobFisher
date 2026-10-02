"""
Adzuna — free developer API (needs a free key in .env). Supports a real
radius search around Lakeland, which the other free sources can't do.
Docs: https://developer.adzuna.com/docs/search

Honesty note: Adzuna sometimes returns an ESTIMATED salary
(salary_is_predicted = "1"). We discard those — only employer-stated
salaries are shown. Adzuna also only returns a description snippet, so the
analysis for these jobs is marked as limited.
"""

import os

from ..normalize import format_salary, html_to_text, iso_date, make_job
from .http import SourceSkipped, get_json

URL = "https://api.adzuna.com/v1/api/jobs/us/search/1"
CONTRACT = {"full_time": "Full-time", "part_time": "Part-time"}


def fetch(cfg, settings):
    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()
    if not app_id or not app_key:
        raise SourceSkipped("No Adzuna key in .env (optional — see .env.example).")

    locs = settings["locations"]
    jobs = []
    for what in cfg.get("what", []):
        data = get_json(URL, {
            "app_id": app_id, "app_key": app_key,
            "what": what,
            "where": locs.get("home", "Lakeland, FL"),
            "distance": round(float(locs.get("radius_miles", 50)) * 1.609),  # Adzuna uses km
            "max_days_old": cfg.get("max_days_old", 30),
            "results_per_page": 50,
            "content-type": "application/json",
        })
        for item in data.get("results", []):
            stated = str(item.get("salary_is_predicted", "1")) == "0"
            jobs.append(make_job(
                source="Adzuna",
                source_id=str(item.get("id")),
                title=html_to_text(item.get("title")),
                company=(item.get("company") or {}).get("display_name"),
                location=(item.get("location") or {}).get("display_name"),
                employment_type=CONTRACT.get(item.get("contract_time")),
                salary_text=format_salary(item.get("salary_min"), item.get("salary_max"), "USD", "year") if stated else None,
                salary_min=item.get("salary_min") if stated else None,
                salary_max=item.get("salary_max") if stated else None,
                description=html_to_text(item.get("description")),
                url=item.get("redirect_url"),
                is_direct_url=False,
                date_posted=iso_date(item.get("created")),
            ))
    return jobs
