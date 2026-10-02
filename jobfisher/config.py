"""
config.py — Default settings and the starting ("seed") profile.

WHAT:  Plain Python dictionaries holding the defaults.
WHY:   The first time JobFisher runs, the database is empty. These defaults get
       copied into the database once. After that, you edit them from the
       Profile and Settings pages and the DATABASE copy becomes the real one.
HOW:   profile_store.py reads the database. If nothing is there yet, it saves
       these defaults first.

IMPORTANT — honesty rule:
  The seed profile below was built from your project spec and from what you have
  told Claude about your work. It is the *supplemental* source. Your uploaded
  resume is the *authoritative* source. Anything not confirmed by the resume is
  labelled "profile summary only" in the match explanations. Review and edit it
  on the Profile page — remove anything that is not accurate.
"""

DEFAULT_SETTINGS = {
    # Application Fit Score weights (spec section 12). They are percentages
    # and should add up to 100 — the Settings page shows the total.
    "weights": {
        "skills": 40,       # Required skill match
        "experience": 20,   # Experience level match
        "portfolio": 15,    # Portfolio / client project relevance
        "education": 10,    # Education requirement match
        "level": 10,        # Does the job genuinely look entry-level/junior?
        "location": 5,      # Location / work arrangement fit
    },
    "locations": {
        "home": "Lakeland, FL",
        # Radius is used by sources that support it (Adzuna). Other free sources
        # only filter by city name, so we also keep a list of accepted places.
        "radius_miles": 50,
        "accepted_places": [
            "Lakeland", "Polk County", "Winter Haven", "Auburndale", "Bartow",
            "Plant City", "Haines City", "Mulberry", "Brandon", "Tampa",
            "Orlando", "Kissimmee", "Clearwater", "St. Petersburg", "Wesley Chapel",
            "Lake Mary", "Sanford", "Central Florida",
        ],
        "accept_remote": True,
        # Remote jobs only count if they're open to someone in the US.
        "remote_ok_regions": [
            "us", "usa", "u.s.", "united states", "north america", "americas",
            "worldwide", "anywhere", "global", "remote", "us only", "florida",
        ],
        "arrangements": ["Remote", "Hybrid", "On-site"],
    },
    "freshness": {
        "stale_after_days": 14,   # not seen for this long  -> "Listing may be stale"
        "expire_after_days": 30,  # not seen for this long  -> status Expired (unless you're tracking it)
    },
    "display": {
        "top_n": 8,               # how many cards on the dashboard
        "min_fit_score": 35,      # below this a job never fills a dashboard slot
        # "Do not randomly replace jobs": a job already on the dashboard gets this
        # many bonus points when ranking, so a newcomer must be meaningfully better.
        "stickiness_points": 3,
    },
    "sources": {
        "themuse": {
            "enabled": True,
            "label": "The Muse",
            "categories": ["Software Engineering", "Design and UX", "Computer and IT"],
            "levels": ["Entry Level", "Internship"],
            "locations": ["Tampa, FL", "Orlando, FL", "Lakeland, FL", "Flexible / Remote"],
            "max_pages": 3,
            "cooldown_hours": 0,
        },
        "remotive": {
            "enabled": True,
            "label": "Remotive",
            "categories": ["software-dev", "design"],
            # Remotive asks callers to fetch at most ~4 times per day.
            "cooldown_hours": 6,
        },
        "jobicy": {
            "enabled": True,
            "label": "Jobicy",
            "geo": "usa",
            "tags": ["frontend", "wordpress", "web designer", "web developer"],
            # Jobicy asks callers not to poll more than once per hour.
            "cooldown_hours": 1,
        },
        "adzuna": {
            "enabled": True,   # only runs if ADZUNA_APP_ID / ADZUNA_APP_KEY are in .env
            "label": "Adzuna",
            "what": ["web developer", "front end developer", "web designer", "wordpress"],
            "max_days_old": 30,
            "cooldown_hours": 0,
        },
        "greenhouse": {
            "enabled": True,
            "label": "Greenhouse company boards",
            # Board tokens of companies you want to watch. Find one by visiting a
            # company's careers page hosted at boards.greenhouse.io/<token>.
            "boards": [],
            "cooldown_hours": 0,
        },
        "lever": {
            "enabled": True,
            "label": "Lever company boards",
            # Company slugs from jobs.lever.co/<slug>.
            "companies": [],
            "cooldown_hours": 0,
        },
    },
}


# Skill names here must match canonical names in skills.py so the matcher can
# recognise them. "source": "summary" means it comes from this seed profile,
# not from the resume.
def _skills(category, names):
    return [{"name": n, "category": category, "source": "summary"} for n in names]


DEFAULT_PROFILE = {
    "name": "Chad Blincoe",
    "headline": "Entry-level front-end developer / web designer",
    "target_roles": {
        "primary": [
            "Entry-level Front-End Developer", "Junior Front-End Developer",
            "Entry-level Web Developer", "Junior Web Developer",
            "Web Designer / Developer", "Front-End Web Designer",
        ],
        "secondary": [
            "WordPress Designer", "WordPress Developer", "Website Coordinator",
            "Website Administrator", "Digital Content Specialist",
            "Ecommerce Website Specialist", "Junior UI Developer",
            "Web Content Specialist", "Digital Marketing/Web Specialist",
        ],
    },
    "skills": (
        _skills("Front-End", ["HTML", "CSS", "JavaScript", "Responsive Web Design",
                              "DOM Manipulation"])
        + _skills("Frameworks / Development", ["React", "Vite", "Flask", "Python",
                                               "REST APIs", "SQL"])
        + _skills("CMS / Website Builders", ["WordPress", "Elementor", "Blocksy", "Webflow"])
        + _skills("Design", ["Figma", "Photoshop", "Illustrator", "Adobe Creative Suite",
                             "UI Design", "Visual Design"])
        + _skills("Development Tools", ["Git", "GitHub", "VS Code", "Vercel"])
    ),
    # Honest skill-level notes. The matcher uses "developing" to avoid
    # over-claiming: e.g. Python/Flask/SQL are basic, so they're marked here.
    "developing_skills": ["Python", "Flask", "REST APIs", "SQL", "React"],
    "education": [
        {
            "school": "Hillsborough Community College",
            "credential": "Associate of Science",
            "field": "Internet Services Technology (web design & development)",
            "level": "associate",
            "status": "in_progress",
            "expected": "Fall 2027",
            "gpa": "4.0",
            "coursework": ["HTML", "CSS", "JavaScript", "Web Authoring", "Web Scripting",
                           "Multimedia", "Digital Design", "Web Development"],
        }
    ],
    # type is one of: professional | freelance | academic
    # is_web: true only when the role itself was web design/development work.
    "experience": [
        {
            "title": "Freelance Web Designer / Developer",
            "organization": "Pixel Designs (self-employed)",
            "type": "freelance",
            "start": "2026-01",
            "end": "",
            "is_web": True,
            "technologies": ["HTML", "CSS", "Responsive Web Design", "Vercel", "Git", "GitHub"],
            "description": "Client website work (first client in 2026, via professor referral).",
        },
        {
            "title": "Project Manager / Sales",
            "organization": "Restore Masters",
            "type": "professional",
            "start": "",
            "end": "",
            "is_web": False,
            "technologies": [],
            "description": "Project management and sales; involvement with marketing, websites and digital content.",
            "transferable": ["Project Management", "Client Communication", "Sales"],
        },
        {
            "title": "Server",
            "organization": "Ford's Garage (Lakeland)",
            "type": "professional",
            "start": "",
            "end": "",
            "is_web": False,
            "technologies": [],
            "description": "Current hospitality role while transitioning into web work.",
            "transferable": ["Customer Service", "Teamwork"],
        },
    ],
    # type is one of: personal | client | academic | team
    "projects": [
        {
            "name": "Pixel Designs Portfolio",
            "type": "personal",
            "description": "Personal brand portfolio site with responsive layouts, a contact form and a chatbot widget experiment.",
            "technologies": ["HTML", "CSS", "JavaScript", "Responsive Web Design", "Git", "GitHub"],
            "url": "https://github.com/blincoechad/PortfolioLandingPage",
        },
        {
            "name": "Seely's Site Build",
            "type": "client",
            "description": "Static client website on Vercel; security headers and performance work.",
            "technologies": ["HTML", "CSS", "Vercel", "Web Performance", "Git", "GitHub"],
            "url": "https://seelys-site-build.vercel.app",
        },
        {
            "name": "VanguardAI / Vanguard Intelligence",
            "type": "team",
            "description": "Team risk-intelligence dashboard (front-end role). Built in React/Vite, later rebuilt with Flask/Jinja2; integrated the SAM.gov API.",
            "technologies": ["React", "Vite", "Flask", "Python", "JavaScript", "HTML", "CSS",
                             "REST APIs", "Responsive Web Design", "Git", "GitHub"],
            "url": "https://github.com/Blincoechad/VanguardIntelligence",
        },
    ],
}
