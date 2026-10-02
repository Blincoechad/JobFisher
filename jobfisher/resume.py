"""
resume.py — Resume File -> Resume Parser -> Structured Candidate Data.

WHAT:  Validates an uploaded PDF, saves it locally, extracts its text with
       pypdf, and turns that text into structured data (sections + skills).
WHY:   The matching engine should never re-read the PDF on every job. We
       extract the useful information ONCE, store it as data, and the rest of
       the app works with that data.
HOW:   save_resume() is the only entry point for uploads. It follows a
       "save new first, delete old last" order so a failed upload can never
       leave you with no resume.

PRIVACY:
  * The PDF is stored in  data/resumes/  on your computer (git-ignored).
  * Text extraction happens locally with pypdf — nothing is sent anywhere.
  * The file persists across restarts until you replace or delete it.
"""

import os
import re
import uuid

from pypdf import PdfReader

from .db import get_connection, now_iso, resume_dir, to_json, from_json
from .skills import find_skills

MAX_BYTES = 5 * 1024 * 1024  # 5 MB is plenty for a resume

# Headings we look for to split the resume into sections.
SECTION_HEADINGS = {
    "summary": ["summary", "profile", "professional summary", "objective", "about me"],
    "experience": ["experience", "work experience", "professional experience",
                   "employment", "employment history", "work history", "relevant experience"],
    "education": ["education", "academic background", "education & training"],
    "projects": ["projects", "portfolio", "selected projects", "personal projects",
                 "relevant projects", "portfolio projects", "client work"],
    "skills": ["skills", "technical skills", "core skills", "technologies", "tools",
               "skills & tools", "technical proficiencies", "core competencies"],
    "certifications": ["certifications", "certificates", "licenses", "licenses & certifications",
                       "awards", "honors", "awards & honors"],
}


class ResumeError(ValueError):
    """A problem the user can fix (wrong file type, unreadable PDF...)."""


# --- Step 1: validate ----------------------------------------------------------

def validate_upload(filename, data):
    """User-provided files can't be trusted, so check them before doing anything."""
    if not filename or not filename.lower().endswith(".pdf"):
        raise ResumeError("Please choose a .pdf file.")
    if not data:
        raise ResumeError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ResumeError("The file is larger than 5 MB.")
    # Every real PDF begins with the bytes "%PDF-". A renamed .docx would not.
    if not data[:1024].lstrip().startswith(b"%PDF-"):
        raise ResumeError("That file doesn't look like a real PDF.")


# --- Step 2: extract text -------------------------------------------------------

def extract_text(path):
    try:
        reader = PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pypdf raises many different error types
        raise ResumeError(f"Couldn't read the PDF ({exc.__class__.__name__}).")
    text = "\n".join(pages).strip()
    if len(text) < 40:
        raise ResumeError(
            "No readable text was found. The PDF may be a scanned image — "
            "export your resume from Word/Google Docs/Canva as a text-based PDF."
        )
    return text


# --- Step 3: parse into structured data ----------------------------------------

def _heading_for(line):
    clean = re.sub(r"[^a-z& ]", "", line.lower()).strip()
    if not clean or len(clean) > 40:
        return None
    for section, names in SECTION_HEADINGS.items():
        if clean in names:
            return section
    return None


def parse_resume_text(text):
    """Split the text into sections and find skills (and where they appear).

    Knowing WHERE a skill appears matters: React listed under "Projects" is
    project experience, not professional experience. The matcher uses this.
    """
    sections = {"header": []}
    current = "header"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = _heading_for(line)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    section_text = {name: "\n".join(lines) for name, lines in sections.items() if lines}

    skills = {}
    for name, body in section_text.items():
        for skill in find_skills(body):
            skills.setdefault(skill, []).append(name)

    return {
        "sections": {k: v for k, v in section_text.items() if k != "header"},
        "section_names": [k for k in section_text if k != "header"],
        "skills": [{"name": s, "found_in": sorted(set(where))} for s, where in sorted(skills.items())],
        "certifications": section_text.get("certifications", "").splitlines(),
        "has_structure": len(section_text) > 1,
    }


# --- Step 4: save / replace / delete --------------------------------------------

def save_resume(filename, data):
    """Validate -> write new file -> extract -> parse -> activate -> remove old."""
    validate_upload(filename, data)
    os.makedirs(resume_dir(), exist_ok=True)

    # We never use your original filename as the path on disk. A random name
    # avoids clashes and blocks tricks like "../../something.pdf".
    stored_name = f"{uuid.uuid4().hex}.pdf"
    path = os.path.join(resume_dir(), stored_name)
    with open(path, "wb") as fh:
        fh.write(data)

    try:
        text = extract_text(path)
        parsed = parse_resume_text(text)
    except ResumeError:
        os.remove(path)  # the NEW file failed — the old resume is untouched
        raise

    display_name = os.path.basename(filename)[:150]
    with get_connection() as conn:  # one transaction: all of this or none of it
        old_rows = conn.execute("SELECT id, stored_name FROM resumes").fetchall()
        conn.execute("UPDATE resumes SET is_active = 0")
        conn.execute(
            "INSERT INTO resumes (original_name, stored_name, size_bytes, uploaded_at, text, parsed_json, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (display_name, stored_name, len(data), now_iso(), text, to_json(parsed)),
        )
        conn.execute("DELETE FROM resumes WHERE is_active = 0")

    # Only now — after the new one is safely stored — remove the old files.
    for row in old_rows:
        _remove_file(row["stored_name"])
    return get_active_resume()


def get_active_resume(include_text=False):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM resumes WHERE is_active = 1").fetchone()
    if row is None:
        return None
    result = {
        "id": row["id"],
        "original_name": row["original_name"],
        "uploaded_at": row["uploaded_at"],
        "size_bytes": row["size_bytes"],
        "parsed": from_json(row["parsed_json"], {}),
    }
    if include_text:
        result["text"] = row["text"]
    return result


def delete_active_resume():
    with get_connection() as conn:
        rows = conn.execute("SELECT stored_name FROM resumes").fetchall()
        conn.execute("DELETE FROM resumes")
    for row in rows:
        _remove_file(row["stored_name"])


def _remove_file(stored_name):
    path = os.path.join(resume_dir(), os.path.basename(stored_name))
    if os.path.exists(path):
        os.remove(path)
