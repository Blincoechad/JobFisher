"""
candidate.py — Builds the "Structured Candidate Profile".

WHAT:  Combines your two sources of truth into one object the matcher can use:
         1. Uploaded resume  (authoritative)
         2. Profile summary  (supplemental context)
WHY:   The matcher needs to know not just WHETHER you have a skill, but WHAT
       KIND of evidence backs it up. "React in a team project" is not the same
       as "React at a job for 3 years" — and the app must never pretend it is.
HOW:   For every skill we collect evidence (where it shows up) and pick a
       weight. Stronger evidence = higher weight in the Skill Match score.
"""

from datetime import date

from .skills import canonical_name, find_skills

# How much a skill counts, by the strongest evidence we have for it.
# Professional work counts fully; a skill only listed in the summary counts less.
EVIDENCE_RANK = [
    # (kind,            label shown on the card,                   weight)
    ("professional",    "Professional experience",                 1.00),
    ("freelance",       "Client/freelance experience",             1.00),
    ("project",         "Project experience",                      0.90),
    ("academic",        "Academic coursework",                     0.85),
    ("resume",          "Listed on resume",                        0.80),
    ("summary",         "Profile summary only (not on resume)",    0.60),
]
IMPLIED_SKILLS = [
    ("WordPress", "CMS (general)"), ("Webflow", "CMS (general)"), ("Drupal", "CMS (general)"),
    ("Squarespace", "CMS (general)"), ("Wix", "CMS (general)"), ("Shopify", "CMS (general)"),
    ("Photoshop", "Adobe Creative Suite"), ("Illustrator", "Adobe Creative Suite"),
    ("GitHub", "Git"),
]

EVIDENCE_INFO = {kind: (label, weight) for kind, label, weight in EVIDENCE_RANK}
EVIDENCE_ORDER = [kind for kind, _, _ in EVIDENCE_RANK]


def _years_since(yyyy_mm):
    """'2026-01' -> years between then and today (e.g. 0.75)."""
    try:
        year, month = [int(x) for x in yyyy_mm.split("-")[:2]]
    except (ValueError, AttributeError):
        return 0.0
    today = date.today()
    months = (today.year - year) * 12 + (today.month - month)
    return max(0.0, months / 12.0)


def _duration(entry):
    start = entry.get("start") or ""
    end = entry.get("end") or ""
    if not start:
        return 0.0
    total = _years_since(start)
    if end:
        total -= _years_since(end)
    return max(0.0, total)


def build_candidate(profile, resume):
    """Return the structured candidate profile used by matcher.py."""
    skills = {}  # name -> {"kinds": set(), "where": [labels]}

    def add(name, kind, where):
        name = canonical_name(name)
        entry = skills.setdefault(name, {"kinds": set(), "where": []})
        entry["kinds"].add(kind)
        if where and where not in entry["where"]:
            entry["where"].append(where)

    has_resume = bool(resume and resume.get("parsed"))

    # Source 1 — resume. Where a skill appears tells us what kind of evidence it is.
    if has_resume:
        section_kind = {"experience": "resume", "projects": "project", "education": "academic",
                        "skills": "resume", "summary": "resume", "certifications": "resume"}
        for item in resume["parsed"].get("skills", []):
            for section in item.get("found_in", []):
                kind = section_kind.get(section, "resume")
                add(item["name"], kind, f"Resume — {section} section")

    # Source 2 — profile summary (skills list, experience, projects, coursework).
    for skill in profile.get("skills", []):
        add(skill["name"], "summary", "Profile skills list")

    for exp in profile.get("experience", []):
        kind = exp.get("type", "professional")
        if kind == "professional" and not exp.get("is_web"):
            # A non-web job does not give professional evidence for web skills,
            # but its transferable skills still count.
            for t in exp.get("transferable", []):
                add(t, "professional", f"{exp.get('title')} at {exp.get('organization')}")
            continue
        for tech in exp.get("technologies", []) + exp.get("transferable", []):
            add(tech, kind, f"{exp.get('title')} — {exp.get('organization')}")

    for proj in profile.get("projects", []):
        kind = "freelance" if proj.get("type") == "client" else "project"
        for tech in proj.get("technologies", []):
            add(tech, kind, f"{proj.get('name')} ({proj.get('type')} project)")

    for edu in profile.get("education", []):
        for course in edu.get("coursework", []):
            # Only coursework that names a recognisable skill counts (e.g. "JavaScript").
            for skill in find_skills(course):
                add(skill, "academic", f"Coursework — {edu.get('school')}")

    # Some skills imply a broader one: WordPress experience IS CMS experience.
    # The broader skill inherits the same evidence (never stronger evidence).
    for specific, broad in IMPLIED_SKILLS:
        if specific in skills:
            for kind in skills[specific]["kinds"]:
                add(broad, kind, f"Implied by {specific}")

    developing = {canonical_name(s) for s in profile.get("developing_skills", [])}

    # Pick the strongest evidence for each skill and give it a weight.
    resolved = {}
    for name, info in skills.items():
        kinds = info["kinds"]
        best = next(k for k in EVIDENCE_ORDER if k in kinds)
        label, weight = EVIDENCE_INFO[best]
        if best == "summary" and not has_resume:
            weight = 0.80  # no resume yet: the summary is the best we have
            label = "Profile summary (no resume uploaded yet)"
        on_resume = any(w.startswith("Resume") for w in info["where"])
        if has_resume and not on_resume and best != "summary":
            # Backed by your profile, but the authoritative resume doesn't mention it.
            weight *= 0.9
            label += " (not on resume)"
        if name in developing:
            weight *= 0.85
            label += " — still developing"
        resolved[name] = {
            "evidence": best,
            "label": label,
            "weight": round(weight, 2),
            "on_resume": on_resume,
            "where": info["where"],
        }

    # Experience totals — kept separate on purpose (spec: never blur these).
    professional_web_years = sum(_duration(e) for e in profile.get("experience", [])
                                 if e.get("type") == "professional" and e.get("is_web"))
    freelance_years = sum(_duration(e) for e in profile.get("experience", [])
                          if e.get("type") == "freelance")
    undated_web = [e.get("title") for e in profile.get("experience", [])
                   if e.get("is_web") and not e.get("start")]

    levels = [e.get("level", "") for e in profile.get("education", [])]
    in_progress = any(e.get("status") == "in_progress" for e in profile.get("education", []))
    rank = {"high_school": 1, "certificate": 1, "associate": 2, "bachelor": 3, "master": 4}
    highest = max(levels, key=lambda lv: rank.get(lv, 0)) if levels else ""

    return {
        "skills": resolved,
        "has_resume": has_resume,
        "professional_web_years": round(professional_web_years, 2),
        "freelance_years": round(freelance_years, 2),
        "undated_web_roles": undated_web,
        "education": {
            "highest": highest,
            "in_progress": in_progress,
            "summary": "; ".join(
                f"{e.get('credential', '')} — {e.get('field', '')} ({'in progress, expected ' + e.get('expected', '') if e.get('status') == 'in_progress' else 'completed'})"
                for e in profile.get("education", [])
            ),
        },
        "projects": profile.get("projects", []),
        "experience": profile.get("experience", []),
        "certifications": (resume or {}).get("parsed", {}).get("certifications", []) if has_resume else [],
    }
