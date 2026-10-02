"""
Greenhouse job boards — many companies host their careers page on Greenhouse,
which offers a free, public, read-only API for exactly this purpose.
Add a company's board token in Settings (boards.greenhouse.io/<token>).
These are DIRECT company listings, so their URLs are preferred over aggregators.
"""

from ..normalize import html_to_text, iso_date, make_job
from .http import SourceSkipped, get_json

URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


def fetch(cfg, settings):
    boards = [b.strip() for b in cfg.get("boards", []) if b.strip()]
    if not boards:
        raise SourceSkipped("No company boards added yet (optional — add them in Settings).")
    jobs = []
    for board in boards:
        data = get_json(URL.format(board=board), {"content": "true"})
        for item in data.get("jobs", []):
            jobs.append(make_job(
                source="Greenhouse",
                source_id=f"{board}-{item.get('id')}",
                title=item.get("title"),
                company=item.get("company_name") or board.replace("-", " ").title(),
                location=(item.get("location") or {}).get("name"),
                description=html_to_text(item.get("content")),
                url=item.get("absolute_url"),
                is_direct_url=True,
                date_posted=iso_date(item.get("first_published") or item.get("updated_at")),
            ))
    return jobs
