"""
matcher.py — The Job Matching Engine.

WHAT:  analyze_job(job, candidate, settings, company_history) reads ONE job
       posting and returns a fully explained analysis:
         * Application Fit Score (0-100) + category (Strong/Possible/Stretch/Poor)
         * Application Difficulty  (separate from fit)
         * Interview Competitiveness (evidence-based, or "Insufficient evidence")
         * Company Hiring Context   (based only on postings JobFisher has seen)
         * Strengths, gaps, portfolio relevance, plain-English summary
WHY:   Every score must be explainable. So instead of one magic number, each
       part of the score is computed by its own small function that ALSO
       returns a human-readable note saying why.
HOW:   1. Split the description into required vs preferred sentences.
       2. Pull out skills, years of experience, education, level, location.
       3. Score each component 0.0-1.0 and combine with your weights.
       4. Apply honesty caps (e.g. a Senior role can never be a "Strong Match").

This is a rule-based engine. It does NOT predict hiring. It measures how
closely the posting's stated requirements align with your documented profile.
"""

import re

from .skills import find_skills, has_flag, SKILL_LIBRARY

WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10}

# --- 1. Splitting the posting into required / preferred / ignored text ----------

PREFERRED_HEADING = re.compile(r"(preferred|nice[- ]to[- ]have|bonus|plus|desired|good to have|extra credit|ideal(ly)?)", re.I)
REQUIRED_HEADING = re.compile(r"(requirement|qualification|must[- ]have|what you('ll)? (need|bring)|you have|who you are|about you|minimum|skills|experience|responsibilit|what you('ll)? do|duties|the role|your role|day[- ]to[- ]day)", re.I)
IGNORE_HEADING = re.compile(r"(benefit|perk|about us|about the company|who we are|our company|equal opportunity|eeo|compensation|salary|pay range|why join|what we offer|we offer|location|how to apply)", re.I)
PREFERRED_SENTENCE = re.compile(r"(preferred|nice[- ]to[- ]have|is a plus|are a plus|a plus\b|bonus|desired|ideally|would be great|helpful|not required)", re.I)


def _is_heading(line):
    """A line is a heading if it ends with ':' (html_to_text adds one to real
    <h2>/<strong> headings), is ALL CAPS, or is a short known heading phrase
    with no skills or numbers in it (so "Experience with React" is NOT a heading)."""
    if len(line) > 60 or line.endswith("."):
        return False
    if line.endswith(":") or (line.isupper() and len(line) > 3):
        return True
    words = line.split()
    known = PREFERRED_HEADING.search(line) or REQUIRED_HEADING.search(line) or IGNORE_HEADING.search(line)
    return bool(len(words) <= 4 and known and not re.search(r"\d", line) and not find_skills(line))


def split_requirements(text):
    """Return {"required": [...sentences], "preferred": [...], "ignored": [...]}.

    Developer thinking: postings have no fixed format, so we use two signals —
    the most recent heading ("Nice to have:") and words inside each sentence
    ("...is a plus"). Text before any heading is treated as required.
    """
    buckets = {"required": [], "preferred": [], "ignored": []}
    mode = "required"
    for raw in (text or "").splitlines():
        line = raw.strip(" \t•*-–·")
        if not line:
            continue
        if _is_heading(line):
            if IGNORE_HEADING.search(line):
                mode = "ignored"
                continue
            if PREFERRED_HEADING.search(line):
                mode = "preferred"
                continue
            if REQUIRED_HEADING.search(line):
                mode = "required"
                continue
        for sentence in re.split(r"(?<=[.;!?])\s+", line):
            if not sentence:
                continue
            if mode == "ignored":
                buckets["ignored"].append(sentence)
            elif mode == "preferred" or PREFERRED_SENTENCE.search(sentence):
                buckets["preferred"].append(sentence)
            else:
                buckets["required"].append(sentence)
    return buckets


# --- 2a. Years of experience ----------------------------------------------------

YEARS_RE = re.compile(
    r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s*\+?\s*"
    r"(?:(?:-|–|to|or)\s*(\d{1,2})\s*\+?\s*)?(?:years?|yrs?)", re.I)
NO_EXPERIENCE_RE = re.compile(r"(no (prior |previous )?experience (is )?(required|necessary|needed)|"
                              r"0\s*(?:-|–|to)\s*\d\s*years|new grad|recent graduate|early[- ]career)", re.I)


def extract_years(sentences):
    """Find the minimum years of experience each sentence asks for; return the
    largest of those (the strictest requirement) plus the sentence it came from."""
    best = None
    best_sentence = ""
    professional = False
    for s in sentences:
        lower = s.lower()
        if "experience" not in lower and "exp." not in lower:
            continue
        # Skip sentences about the company ("we have 20 years of experience").
        if re.search(r"\b(we|our|company|founded|since|in business)\b", lower) and "you" not in lower:
            continue
        for m in YEARS_RE.finditer(s):
            first = m.group(1).lower()
            years = WORD_NUMBERS.get(first) if first in WORD_NUMBERS else int(first)
            if years is None or years > 15:
                continue
            if best is None or years > best:
                best = years
                best_sentence = s.strip()
                professional = bool(re.search(r"professional|industry|work experience|commercial|production", lower))
    return best, best_sentence, professional


def score_experience(buckets, candidate, level_info):
    req_years, req_sentence, professional = extract_years(buckets["required"])
    pref_years, _, _ = extract_years(buckets["preferred"])
    all_text = " ".join(buckets["required"] + buckets["preferred"])
    no_exp = bool(NO_EXPERIENCE_RE.search(all_text))

    prof = candidate["professional_web_years"]
    free = candidate["freelance_years"]
    # Freelance counts half: some employers count it fully, some not at all.
    effective = prof + 0.5 * free
    yours = (f"Your documented web experience: {prof:g} yrs professional, "
             f"{free:.1f} yrs freelance/client, plus academic and project work.")

    if req_years == 0:
        no_exp, req_years = True, None   # "0-1 years" means no prior experience is needed
    if req_years is None:
        if no_exp or level_info["junior"]:
            return {"score": 0.95, "required_years": 0 if no_exp else None, "preferred_years": pref_years,
                    "note": "No years of experience required" + (" (posting says so explicitly)." if no_exp else " — and the role is labelled entry-level/junior."),
                    "detail": yours}
        return {"score": 0.65, "required_years": None, "preferred_years": pref_years,
                "note": "The posting doesn't state an experience requirement (uncertain).",
                "detail": yours}

    gap = req_years - effective
    if gap <= 0:
        score = 1.0
    elif gap <= 0.75:
        score = 0.7
    elif gap <= 1.5:
        score = 0.45
    elif gap <= 2.5:
        score = 0.25
    elif gap <= 4:
        score = 0.1
    else:
        score = 0.0
    kind = "professional " if professional else ""
    note = f"Posting asks for {req_years}+ years of {kind}experience. "
    if score < 1:
        note += "Your web experience is mostly freelance, academic and project-based, so this is a gap."
    return {"score": score, "required_years": req_years, "preferred_years": pref_years,
            "note": note.strip(), "detail": yours, "source_sentence": req_sentence}


# --- 2b. Education ---------------------------------------------------------------

BACHELOR_RE = re.compile(r"(bachelor'?s?|\bb\.s\.|\bb\.a\.|\bbs/ba\b|\bba/bs\b|\bbs or ba\b|four[- ]year degree|4[- ]year degree|undergraduate degree|university degree|college degree)", re.I)
MASTER_RE = re.compile(r"(master'?s degree|\bmba\b|\bph\.?d\b|graduate degree)", re.I)
ASSOCIATE_RE = re.compile(r"(associate'?s? degree|two[- ]year degree|2[- ]year degree|\ba\.?a\.?s?\.? degree)", re.I)
DEGREE_RE = re.compile(r"\bdegree\b", re.I)
EQUIVALENT_RE = re.compile(r"(or equivalent|equivalent (work |practical |professional )?experience|or related experience|in lieu of|degree not required|no degree required|comparable experience|or equivalent combination)", re.I)
HIGH_SCHOOL_RE = re.compile(r"(high school|\bged\b)", re.I)


def score_education(buckets, candidate):
    req_text = " ".join(buckets["required"])
    pref_text = " ".join(buckets["preferred"])
    all_text = req_text + " " + pref_text
    equivalent = bool(EQUIVALENT_RE.search(all_text))
    yours = candidate["education"]["summary"] or "No education entered in your profile."

    def needs(regex):
        if regex.search(req_text):
            return "required"
        if regex.search(pref_text):
            return "preferred"
        return None

    master, bachelor, associate, generic = needs(MASTER_RE), needs(BACHELOR_RE), needs(ASSOCIATE_RE), needs(DEGREE_RE)
    if master == "required" and not equivalent:
        return {"score": 0.05, "requirement": "Master's degree required", "note": "Posting requires a graduate degree.", "detail": yours}
    if bachelor == "required" and not equivalent:
        return {"score": 0.25, "requirement": "Bachelor's degree required",
                "note": "Posting requires a bachelor's degree with no 'equivalent experience' option. Your associate degree is in progress.", "detail": yours}
    if bachelor == "required" and equivalent:
        return {"score": 0.65, "requirement": "Bachelor's or equivalent experience",
                "note": "Bachelor's requested, but the posting accepts equivalent experience — your coursework and projects may count (uncertain).", "detail": yours}
    if bachelor == "preferred" or master == "preferred":
        return {"score": 0.75, "requirement": "Degree preferred", "note": "A degree is preferred, not required.", "detail": yours}
    if associate:
        return {"score": 0.8, "requirement": f"Associate degree {associate}",
                "note": "Associate degree requested — yours is in progress (expected Fall 2027), so it isn't completed yet.", "detail": yours}
    if generic == "required" and not equivalent:
        return {"score": 0.5, "requirement": "Degree required (level not stated)",
                "note": "A degree is required but the level isn't stated (uncertain). Yours is in progress.", "detail": yours}
    if generic:
        return {"score": 0.8, "requirement": "Degree mentioned", "note": "A degree is mentioned but not strictly required.", "detail": yours}
    if HIGH_SCHOOL_RE.search(all_text):
        return {"score": 1.0, "requirement": "High school / GED", "note": "Education requirement is met.", "detail": yours}
    return {"score": 1.0, "requirement": "Not stated", "note": "No education requirement stated.", "detail": yours}


# --- 2c. Job level (is it really entry-level?) ----------------------------------

SENIOR_RE = re.compile(r"\b(senior|sr\.?|lead|principal|staff|manager|director|head of|architect|vp|chief)\b", re.I)
JUNIOR_TITLE_RE = re.compile(r"\b(junior|jr\.?|entry[- ]level|entry|apprentice(ship)?|intern(ship)?|graduate|trainee|associate)\b|\b(developer|designer|engineer|specialist)\s+i\b", re.I)
MID_RE = re.compile(r"\b(mid[- ]level|intermediate|ii|iii)\b", re.I)
ENTRY_TEXT_RE = re.compile(r"(entry[- ]level|junior|recent graduates?|new grads?|early[- ]career|no experience required|training provided|we will train)", re.I)


def score_level(job, description):
    title = job.get("title", "")
    hint = (job.get("level_hint") or "").lower()
    if SENIOR_RE.search(title) or "senior" in hint or "management" in hint:
        return {"score": 0.0, "label": "Senior / Lead", "junior": False, "senior": True,
                "note": "The title indicates a senior, lead or management role."}
    if JUNIOR_TITLE_RE.search(title) or "entry" in hint or "intern" in hint:
        label = "Internship" if re.search(r"intern", title + hint, re.I) else "Entry-level / Junior"
        return {"score": 1.0, "label": label, "junior": True, "senior": False,
                "note": "The title or source labels this role as entry-level/junior."}
    if MID_RE.search(title) or "mid" in hint:
        return {"score": 0.35, "label": "Mid-level", "junior": False, "senior": False,
                "note": "The title suggests a mid-level role."}
    if ENTRY_TEXT_RE.search(description or ""):
        return {"score": 0.85, "label": "Likely entry-level", "junior": True, "senior": False,
                "note": "The description uses entry-level language, though the title doesn't say so."}
    return {"score": 0.6, "label": "Level not stated", "junior": False, "senior": False,
            "note": "The posting doesn't state a level (uncertain)."}


# --- 2d. Location / work arrangement ----------------------------------------------

def score_location(job, settings):
    loc_settings = settings["locations"]
    arrangement = job.get("work_arrangement") or "Unknown"
    location = job.get("location") or ""
    region = (job.get("remote_region") or "").lower()
    allowed = loc_settings.get("arrangements", ["Remote", "Hybrid", "On-site"])
    places = [p.lower() for p in loc_settings.get("accepted_places", [])]
    home_city = loc_settings.get("home", "").split(",")[0].strip().lower()
    in_area = any(p and p in location.lower() for p in places + [home_city])

    if arrangement != "Unknown" and arrangement not in allowed:
        return {"score": 0.0, "arrangement": arrangement, "note": f"{arrangement} is turned off in your settings."}
    if arrangement == "Remote":
        if not loc_settings.get("accept_remote", True):
            return {"score": 0.0, "arrangement": arrangement, "note": "Remote jobs are turned off in your settings."}
        ok_regions = loc_settings.get("remote_ok_regions", [])
        if region and not any(r in region for r in ok_regions):
            return {"score": 0.1, "arrangement": arrangement,
                    "note": f"Remote, but limited to candidates in: {job.get('remote_region')}."}
        return {"score": 1.0, "arrangement": arrangement, "note": "Remote and open to US-based candidates."}
    if in_area:
        return {"score": 1.0, "arrangement": arrangement, "note": f"{arrangement if arrangement != 'Unknown' else 'Located'} in your search area ({location})."}
    if re.search(r"\b(fl|florida)\b", location, re.I):
        return {"score": 0.45, "arrangement": arrangement, "note": f"In Florida but outside your listed area ({location})."}
    if not location:
        return {"score": 0.4, "arrangement": arrangement, "note": "Location not stated (uncertain)."}
    return {"score": 0.2, "arrangement": arrangement, "note": f"Outside your area ({location}) — would require relocation."}


# --- 2e. Skills and portfolio ---------------------------------------------------

def score_skills(buckets, candidate, extra_names):
    required = find_skills("\n".join(buckets["required"]), extra_names)
    preferred = find_skills("\n".join(buckets["preferred"]), extra_names) - required
    have = candidate["skills"]

    rows = []
    for skill_set, is_required in ((required, True), (preferred, False)):
        for name in sorted(skill_set):
            info = have.get(name)
            rows.append({
                "skill": name,
                "required": is_required,
                "status": "match" if info else "gap",
                "evidence": info["label"] if info else "Not in your resume or profile",
                "weight": info["weight"] if info else 0.0,
            })

    req_rows = [r for r in rows if r["required"]]
    pref_rows = [r for r in rows if not r["required"]]
    denominator = len(req_rows) + 0.5 * len(pref_rows)
    if denominator == 0:
        score = 0.4
        note = "The posting lists no recognisable skills, so skill fit is uncertain."
    else:
        score = (sum(r["weight"] for r in req_rows) + 0.5 * sum(r["weight"] for r in pref_rows)) / denominator
        matched = sum(1 for r in req_rows if r["status"] == "match")
        note = f"You show evidence for {matched} of {len(req_rows)} required skills" + \
               (f" and {sum(1 for r in pref_rows if r['status'] == 'match')} of {len(pref_rows)} preferred skills." if pref_rows else ".")
    return {"score": round(score, 3), "rows": rows, "required": sorted(required),
            "preferred": sorted(preferred), "note": note}


def score_portfolio(skill_info, candidate):
    """Which of your projects / client work demonstrate the skills this job wants?"""
    wanted = set(skill_info["required"]) | set(skill_info["preferred"])
    sources = [(p["name"], p.get("type", "personal"), set(p.get("technologies", []))) for p in candidate["projects"]]
    sources += [(f"{e['title']} — {e['organization']}", e["type"], set(e.get("technologies", [])))
                for e in candidate["experience"] if e.get("type") == "freelance"]

    relevant = []
    demonstrated = set()
    for name, kind, techs in sources:
        overlap = sorted(wanted & techs)
        if overlap:
            relevant.append({"name": name, "type": kind, "skills": overlap})
            demonstrated |= set(overlap)
    relevant.sort(key=lambda p: len(p["skills"]), reverse=True)

    if not wanted:
        return {"score": 0.4, "projects": [], "note": "No recognisable skills to compare with your projects (uncertain)."}
    base = skill_info["required"] or sorted(wanted)
    score = min(1.0, len(demonstrated & set(base)) / max(1, len(base)))
    if relevant:
        note = "Relevant work: " + "; ".join(f"{p['name']} ({', '.join(p['skills'][:4])})" for p in relevant[:3])
    else:
        note = "None of your listed projects demonstrate the skills this posting emphasises."
    return {"score": round(score, 3), "projects": relevant[:4], "note": note}


# --- 2f. Is this even a web design/development job? -------------------------------

WEB_TITLE_RE = re.compile(
    r"(front[- ]?end|web ?(developer|designer|design|development|specialist|coordinator|administrator|"
    r"content|producer|master|programmer|engineer|editor|manager|marketing)|website|wordpress|webflow|"
    r"\bui\b|ui/ux|ux/ui|user interface|shopify|e-?commerce|digital content|html|javascript|react|"
    r"web\b)", re.I)
NON_WEB_TITLE_RE = re.compile(
    r"(back[- ]?end|devops|data (scientist|engineer|analyst)|machine learning|\bml\b|\bai engineer|"
    r"site reliability|\bsre\b|android|\bios\b|embedded|security engineer|network|firmware|"
    r"mechanical|electrical|civil|nurse|sales (rep|representative|executive)|account executive|"
    r"recruiter|accountant|qa (engineer|analyst)|test engineer|salesforce)", re.I)
GENERAL_DEV_TITLE_RE = re.compile(r"(software (developer|engineer)|full[- ]?stack|application developer|programmer)", re.I)


def judge_relevance(job, skill_info):
    title = job.get("title", "")
    core = [s for s in skill_info["required"] + skill_info["preferred"] if has_flag(s, "core")]
    if NON_WEB_TITLE_RE.search(title) and not re.search(r"front[- ]?end|web", title, re.I):
        return False, "Title points to a non-web specialty."
    if WEB_TITLE_RE.search(title):
        return True, "Title is a web design/development role."
    if GENERAL_DEV_TITLE_RE.search(title) and len(core) >= 3:
        return True, f"General developer title, but it emphasises web skills ({', '.join(core[:4])})."
    if len(core) >= 3:
        return True, f"Not a web title, but web work is central ({', '.join(core[:4])})."
    return False, "Doesn't appear to be primarily web design/development work."


# --- 3. Difficulty, competitiveness, hiring context ---------------------------------

def rate_difficulty(exp, edu, level, skill_info, candidate_certs, description):
    points = 0
    reasons = []
    years = exp.get("required_years")
    if years:
        add = 1 if years <= 1 else 2 if years == 2 else 3 if years <= 4 else 4
        points += add
        reasons.append(f"asks for {years}+ years of experience")
    missing = [r["skill"] for r in skill_info["rows"] if r["required"] and r["status"] == "gap"]
    if missing:
        points += 1 if len(missing) <= 2 else 2 if len(missing) <= 4 else 3
        reasons.append(f"{len(missing)} required skill(s) missing ({', '.join(missing[:4])})")
    if len(skill_info["required"]) > 10:
        points += 1
        reasons.append(f"a long list of required technologies ({len(skill_info['required'])})")
    specialized = [s for s in skill_info["required"] if has_flag(s, "specialized")]
    if specialized:
        points += 1
        reasons.append(f"specialized technology ({', '.join(specialized[:3])})")
    if edu["score"] <= 0.5:
        points += 2
        reasons.append(edu["requirement"].lower())
    if re.search(r"(certification|certified|license) (is )?required|must (be|hold) (a )?(certified|license)", description or "", re.I):
        points += 1
        reasons.append("a required certification/license")
    if level["senior"]:
        points += 3
        reasons.append("senior-level title")

    if points <= 2:
        level_name, emoji = "Low", "🟢"
    elif points <= 4:
        level_name, emoji = "Moderate", "🟡"
    elif points <= 7:
        level_name, emoji = "High", "🟠"
    else:
        level_name, emoji = "Very High", "🔴"

    lead = "Listed as junior/entry-level" if level["junior"] else "Not labelled entry-level"
    if reasons:
        text = f"{level_name} — {lead}. Factors: " + "; ".join(reasons) + "."
    else:
        text = f"{level_name} — {lead}, and its stated requirements line up with your documented profile."
    return {"level": level_name, "emoji": emoji, "points": points, "reasons": reasons, "text": text}


def rate_competitiveness(job, exp, edu, level, skill_info, location):
    signals = []
    score = 0
    if location["arrangement"] == "Remote":
        score += 1
        signals.append("Remote roles generally draw applicants from a much wider area (general pattern, not data about this posting).")
    elif location["score"] >= 1.0:
        score -= 1
        signals.append("Local hybrid/on-site roles draw from a smaller local applicant pool (general pattern).")
    years = exp.get("required_years")
    if years is not None and years >= 3:
        score += 1
        signals.append(f"{years}+ years requested — candidates with professional experience are favoured.")
    if level["senior"]:
        score += 2
        signals.append("Senior-level title.")
    if edu["score"] <= 0.25:
        score += 1
        signals.append("Strict degree requirement.")
    specialized = [s for s in skill_info["required"] if has_flag(s, "specialized")]
    if len(specialized) >= 2:
        score += 1
        signals.append("Unusually specialized technology stack.")
    missing = [r for r in skill_info["rows"] if r["required"] and r["status"] == "gap"]
    if len(missing) >= 3:
        score += 1
        signals.append(f"For your profile specifically: {len(missing)} required skills are missing.")

    note = "No public applicant-volume data is available, so this is based only on the posting text."
    if len(signals) < 2:
        return {"level": "Insufficient evidence", "emoji": "⚪", "signals": signals, "text": "Insufficient evidence. " + note}
    if score <= -1:
        name, emoji = "Lower apparent competition", "🟢"
    elif score == 0:
        name, emoji = "Moderate competition", "🟡"
    elif score <= 2:
        name, emoji = "Higher competition", "🟠"
    else:
        name, emoji = "Very competitive", "🔴"
    return {"level": name, "emoji": emoji, "signals": signals, "text": f"{name}. {note}"}


def rate_hiring_context(job, exp, level, company_history):
    """Uses ONLY postings JobFisher has actually stored for this company."""
    company = job.get("company", "this company")
    postings = list(company_history or []) + [{
        "title": job.get("title", ""), "required_years": exp.get("required_years"),
        "junior": level["junior"], "senior": level["senior"],
    }]
    junior = [p for p in postings if p.get("junior") or re.search(r"intern|apprentic", p.get("title", ""), re.I)]
    experienced = [p for p in postings if p.get("senior") or (p.get("required_years") or 0) >= 3]
    internships = [p for p in postings if re.search(r"intern|apprentic", p.get("title", ""), re.I)]

    this_years = exp.get("required_years")
    tail = f" However, this specific position requests {this_years}+ years of experience." if this_years and this_years >= 2 else ""
    basis = f" (Based on {len(postings)} posting(s) from {company} seen by JobFisher.)"

    if len(postings) < 2:
        return {"level": "Insufficient evidence", "emoji": "⚪",
                "text": f"Only one posting from {company} has been seen so far — not enough to judge their hiring patterns.{tail}"}
    if len(junior) >= 2 and not experienced:
        extra = " including internship/apprenticeship roles" if internships else ""
        return {"level": "Entry-Level Friendly Evidence", "emoji": "🟢",
                "text": f"{company} has posted multiple junior/entry-level roles{extra}.{tail}{basis}"}
    if experienced and not junior and len(experienced) >= 2:
        return {"level": "Experience Focused", "emoji": "🟠",
                "text": f"{company}'s postings mostly ask for several years of experience or senior titles.{tail}{basis}"}
    return {"level": "Mixed Evidence", "emoji": "🟡",
            "text": f"{company} posts a mix of junior and experienced roles.{tail}{basis}"}


# --- 4. Put it all together ---------------------------------------------------------

CATEGORIES = [(75, "Strong Match"), (55, "Possible Match"), (35, "Stretch Match"), (0, "Poor Match")]

COMPONENT_GAP_PHRASES = {
    "skills": "required skills that your profile doesn't document yet",
    "experience": "the requested experience level",
    "portfolio": "limited portfolio evidence for the skills requested",
    "education": "the education requirement",
    "level": "the role's seniority level",
    "location": "the location / work arrangement",
}


def analyze_job(job, candidate, settings, company_history=None):
    description = job.get("description") or ""
    buckets = split_requirements(description)
    extra_names = list(candidate["skills"].keys())

    level = score_level(job, description)
    skill_info = score_skills(buckets, candidate, extra_names)
    exp = score_experience(buckets, candidate, level)
    edu = score_education(buckets, candidate)
    loc = score_location(job, settings)
    portfolio = score_portfolio(skill_info, candidate)
    relevant, relevance_reason = judge_relevance(job, skill_info)

    components = {"skills": skill_info["score"], "experience": exp["score"], "portfolio": portfolio["score"],
                  "education": edu["score"], "level": level["score"], "location": loc["score"]}
    weights = settings["weights"]
    total_weight = sum(weights.get(k, 0) for k in components) or 1
    raw = sum(components[k] * weights.get(k, 0) for k in components) / total_weight * 100

    # Honesty caps: some single facts outweigh everything else.
    caps = []
    score = raw
    years = exp.get("required_years") or 0
    if level["senior"]:
        score = min(score, 34); caps.append("Senior-level role — capped at Poor Match.")
    if years >= 5:
        score = min(score, 34); caps.append(f"{years}+ years required — capped at Poor Match.")
    elif years >= 3:
        score = min(score, 54); caps.append(f"{years}+ years required — capped at Stretch Match.")
    if not relevant:
        score = min(score, 34); caps.append("Not primarily a web design/development role — capped at Poor Match.")
    if level["junior"] and years >= 3:
        caps.append(f"Labelled entry-level/junior but asks for {years}+ years — possibly misleading.")
    score = round(score)
    category = next(name for floor, name in CATEGORIES if score >= floor)

    strengths = [r for r in skill_info["rows"] if r["status"] == "match"]
    strengths.sort(key=lambda r: (not r["required"], -r["weight"]))
    gaps = [f"{r['skill']}" + (" (required)" if r["required"] else " (preferred)")
            for r in skill_info["rows"] if r["status"] == "gap"]
    if exp.get("required_years"):
        if exp["score"] < 1:
            gaps.insert(0, f"{exp['required_years']}+ years experience requested")
    if edu["score"] <= 0.65:
        gaps.append(edu["requirement"])

    # Plain-English summary — careful wording: alignment, never hiring odds.
    weakest = max(components, key=lambda k: (1 - components[k]) * weights.get(k, 0))
    if category == "Strong Match":
        summary = "This posting aligns closely with the experience currently documented in your profile."
    elif category == "Possible Match":
        summary = "There are meaningful gaps, but this posting looks reasonably attainable based on your documented profile."
    elif category == "Stretch Match":
        summary = "This posting contains significant requirements beyond your current documented experience."
    else:
        summary = "This posting requires experience or qualifications substantially outside your current background."
    if components[weakest] < 0.75:
        summary += f" The largest gap is {COMPONENT_GAP_PHRASES[weakest]}."
    if not relevant:
        summary = f"{relevance_reason} " + summary

    data_notes = []
    if len(description) < 400:
        data_notes.append("Only a short description was available, so this analysis is limited.")
    if not candidate["has_resume"]:
        data_notes.append("No resume uploaded yet — skills are judged from your profile summary only.")

    return {
        "fit_score": score,
        "raw_score": round(raw, 1),
        "fit_category": category,
        "summary": summary,
        "relevant": relevant,
        "relevance_reason": relevance_reason,
        "components": {k: round(v, 3) for k, v in components.items()},
        "weights": {k: weights.get(k, 0) for k in components},
        "skills": skill_info,
        "strengths": [{"skill": r["skill"], "evidence": r["evidence"], "required": r["required"]} for r in strengths],
        "gaps": gaps,
        "experience": exp,
        "education": edu,
        "level": level,
        "location": loc,
        "portfolio": portfolio,
        "difficulty": rate_difficulty(exp, edu, level, skill_info, candidate.get("certifications"), description),
        "competitiveness": rate_competitiveness(job, exp, edu, level, skill_info, loc),
        "hiring_context": rate_hiring_context(job, exp, level, company_history),
        "caps": caps,
        "data_notes": data_notes,
        "disclaimer": "Estimates job-to-profile alignment from the posting text. It does not predict hiring outcomes.",
    }
