"""
normalize.py — Turn every source's different format into ONE job shape.

WHAT:  Helpers that clean HTML, detect Remote/Hybrid/On-site, format salary,
       and build the "dedupe key" used to spot the same job on two sites.
WHY:   The Muse calls the title "name", Remotive calls it "title", Jobicy calls
       it "jobTitle"... If every part of the app had to know all of those
       formats, it would be a mess. Each source file converts ITS format into
       the shape returned by make_job(), and everything downstream only knows
       that one shape. This is called "normalizing" the data.
"""

import hashlib
import html
import re
from html.parser import HTMLParser

# The one job shape every source must produce. Listing it here documents it.
JOB_FIELDS = [
    "source", "source_id", "title", "company", "location", "work_arrangement",
    "remote_region", "employment_type", "salary_text", "salary_min", "salary_max",
    "description", "url", "is_direct_url", "date_posted", "level_hint",
]


def make_job(**fields):
    job = {name: fields.get(name) for name in JOB_FIELDS}
    job["title"] = clean_spaces(job["title"] or "")
    job["company"] = clean_spaces(job["company"] or "Unknown company")
    job["location"] = clean_spaces(job["location"] or "")
    job["description"] = job["description"] or ""
    if not job["work_arrangement"]:
        job["work_arrangement"] = detect_arrangement(job["location"], job["title"], job["description"])
    return job


# --- HTML -> readable text ------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Walks the HTML tags and keeps the text, adding line breaks where
    block elements (paragraphs, list items, headings) end. Headings get a ':'
    so the matcher can recognise them as section titles."""

    BLOCK = {"p", "div", "br", "li", "ul", "ol", "tr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6"}
    HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.in_heading = False
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("• ")
        if tag in self.HEADINGS:
            self.in_heading = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag in self.HEADINGS:
            self.in_heading = False
            last = "".join(self.parts).rstrip()
            if last and last[-1] not in ":.?!":
                self.parts.append(":")
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(raw):
    if not raw:
        return ""
    raw = html.unescape(raw) if "&lt;" in raw else raw  # Greenhouse double-escapes HTML
    # A paragraph that is ONLY bold text is usually a heading ("<p><strong>Requirements</strong></p>")
    raw = re.sub(r"<p>\s*<(strong|b)>([^<]{2,60}?)</\1>\s*</p>", r"<h4>\2</h4>", raw, flags=re.I)
    parser = _TextExtractor()
    parser.feed(raw)
    text = html.unescape("".join(parser.parts))
    lines = [clean_spaces(line) for line in text.splitlines()]
    out = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


def clean_spaces(text):
    return re.sub(r"\s+", " ", text or "").strip()


# --- Work arrangement ------------------------------------------------------------

def detect_arrangement(location, title, description):
    loc = f"{location} {title}".lower()
    desc = (description or "").lower()[:3000]
    if "hybrid" in loc or re.search(r"\bhybrid\b", desc):
        return "Hybrid"
    if re.search(r"\b(remote|anywhere|work from home|wfh|distributed)\b", loc):
        return "Remote"
    if re.search(r"\b(fully remote|100% remote|remote position|remote role|this is a remote)\b", desc):
        return "Remote"
    if re.search(r"\b(on-?site|in-?office|in office|in person)\b", loc + " " + desc):
        return "On-site"
    if location:
        return "On-site"
    return "Unknown"


# --- Salary -----------------------------------------------------------------------

def format_salary(minimum, maximum, currency="USD", period=""):
    """Only ever called with numbers the SOURCE provided. We never estimate."""
    def fmt(n):
        try:
            n = float(n)
        except (TypeError, ValueError):
            return None
        return f"${n:,.0f}" if currency in ("USD", "$", "", None) else f"{n:,.0f} {currency}"
    lo, hi = fmt(minimum), fmt(maximum)
    suffix = f" / {period}" if period else ""
    if lo and hi and lo != hi:
        return f"{lo} – {hi}{suffix}"
    if lo or hi:
        return f"{lo or hi}{suffix}"
    return None


# --- Duplicate detection -------------------------------------------------------------

_COMPANY_SUFFIX = re.compile(r"\b(inc|llc|ltd|corp|corporation|co|company|group|gmbh|plc)\b\.?", re.I)
_TITLE_NOISE = re.compile(r"\(.*?\)|\b(remote|hybrid|on-?site|us|usa)\b", re.I)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def dedupe_key(job):
    """company + title + city, stripped of punctuation and noise words.
    'Acme, Inc.' / 'Front-End Developer (Remote)' / 'Tampa, FL'
       -> 'acme|frontenddeveloper|tampa' """
    company = _slug(_COMPANY_SUFFIX.sub("", job.get("company", "")))
    title = _slug(_TITLE_NOISE.sub("", job.get("title", "")))
    if job.get("work_arrangement") == "Remote":
        city = "remote"
    else:
        city = _slug((job.get("location") or "").split(",")[0])
    return f"{company}|{title}|{city}"


def content_hash(job):
    """Fingerprint of the parts of a posting that matter. If it changes between
    refreshes, the employer edited the listing -> we mark it 'Updated'."""
    basis = "|".join([job.get("title", ""), job.get("location", ""), job.get("salary_text") or "",
                      clean_spaces(job.get("description", ""))])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def iso_date(value):
    """Turn the many date formats sources use into 'YYYY-MM-DD' (or None)."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):  # Lever uses milliseconds since 1970
        from datetime import datetime, timezone
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()
    match = re.match(r"(\d{4}-\d{2}-\d{2})", str(value))
    return match.group(1) if match else None
