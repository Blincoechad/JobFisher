"""
The Muse — free public jobs API (no key needed, 500 requests/hour).
Docs: https://www.themuse.com/developers/api/v2
Good for: entry-level filter + city filter (Tampa, Orlando, remote).
"""

from ..normalize import html_to_text, iso_date, make_job
from .http import get_json

URL = "https://www.themuse.com/api/public/jobs"


def fetch(cfg, settings):
    jobs = []
    params = {
        "category": cfg.get("categories", []),
        "level": cfg.get("levels", []),
        "location": cfg.get("locations", []),
        "descending": "true",
    }
    for page in range(int(cfg.get("max_pages", 1))):
        data = get_json(URL, {**params, "page": page})
        for item in data.get("results", []):
            locations = [loc.get("name", "") for loc in item.get("locations", [])]
            remote = any("remote" in name.lower() or "flexible" in name.lower() for name in locations)
            cities = [name for name in locations if "remote" not in name.lower() and "flexible" not in name.lower()]
            levels = [lv.get("name", "") for lv in item.get("levels", [])]
            jobs.append(make_job(
                source="The Muse",
                source_id=str(item.get("id")),
                title=item.get("name"),
                company=(item.get("company") or {}).get("name"),
                location=", ".join(cities[:3]) or ("Remote" if remote else ""),
                work_arrangement="Remote" if remote else None,  # "Flexible / Remote" = remote allowed
                remote_region="United States" if remote else None,
                description=html_to_text(item.get("contents")),
                url=(item.get("refs") or {}).get("landing_page"),
                is_direct_url=False,
                date_posted=iso_date(item.get("publication_date")),
                level_hint=", ".join(levels),
            ))
        if page + 1 >= data.get("page_count", 0):
            break
    return jobs
