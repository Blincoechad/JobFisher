"""
skills.py — The skill dictionary: how JobFisher recognises skills in text.

WHAT:  A dictionary that maps a canonical skill name ("JavaScript") to the
       regular expressions that detect it in text ("javascript", "ES6", ...).
WHY:   Job postings and resumes write the same skill many ways: "React",
       "React.js", "ReactJS". Normalising them to ONE name lets us compare a job
       against your profile reliably.
HOW:   find_skills(text) runs every pattern against the text and returns the
       set of canonical names it found.

Developer mindset: this is a "rule-based" extractor. It is predictable and easy
to debug (you can see exactly which pattern matched). Later, an AI model could
replace find_skills() — the rest of the app would not need to change, because
it only depends on the function's input (text) and output (set of names).

Regex quick guide:  \\b = word boundary,  (?:a|b) = a or b,  ? = optional,
                    \\s* = any spaces,  (?!x) = "not followed by x".
"""

import re

# Each entry: canonical name -> (category, [regex patterns], flags)
# flags: "core" = core web design/dev skill (used to judge if a job is really a
#        web job); "specialized" = niche/advanced (raises application difficulty).
SKILL_LIBRARY = {
    # --- Front-end core ---
    "HTML": ("Front-End", [r"\bhtml5?\b"], {"core"}),
    "CSS": ("Front-End", [r"\bcss3?\b"], {"core"}),
    "JavaScript": ("Front-End", [r"\bjavascript\b", r"\becmascript\b", r"\bes6\b", r"\bvanilla js\b"], {"core"}),
    "TypeScript": ("Front-End", [r"\btypescript\b"], {"core"}),
    "Responsive Web Design": ("Front-End", [r"\bresponsive (?:web|design|layouts?|websites?|sites?|pages?|development|front|ui|interfaces?|e-?mail)", r"\bmobile[- ]first\b", r"\bmobile[- ]friendly\b"], {"core"}),
    "DOM Manipulation": ("Front-End", [r"\bdom\b"], set()),
    "Accessibility (WCAG)": ("Front-End", [r"\bweb accessibility\b", r"\baccessibility (?:standards|guidelines|best practices|compliance|requirements)", r"\baccessible (?:websites?|web|design|code|markup|interfaces?|experiences?)", r"\bwcag\b", r"\bada complian", r"\bsection 508\b", r"\ba11y\b"], {"core"}),
    "Cross-Browser Compatibility": ("Front-End", [r"\bcross[- ]browser\b"], {"core"}),
    "Web Performance": ("Front-End", [r"\bpage ?speed\b", r"\bsite speed\b", r"\bweb performance\b", r"\bcore web vitals\b"], set()),
    "Sass/SCSS": ("Front-End", [r"\bsass\b", r"\bscss\b", r"\bless\b(?= css)"], {"core"}),
    "Tailwind CSS": ("Front-End", [r"\btailwind\b"], {"core"}),
    "Bootstrap": ("Front-End", [r"\bbootstrap\b"], {"core"}),
    "jQuery": ("Front-End", [r"\bjquery\b"], {"core"}),
    # --- Frameworks / libraries ---
    "React": ("Frameworks / Development", [r"\breact(?:\.?js)?\b(?!\s*native)"], {"core"}),
    "React Native": ("Frameworks / Development", [r"\breact native\b"], {"specialized"}),
    "Redux": ("Frameworks / Development", [r"\bredux\b"], set()),
    "Next.js": ("Frameworks / Development", [r"\bnext\.?js\b"], {"core"}),
    "Vue": ("Frameworks / Development", [r"\bvue(?:\.?js)?\b", r"\bnuxt\b"], {"core"}),
    "Angular": ("Frameworks / Development", [r"\bangular(?:js)?\b"], {"core"}),
    "Svelte": ("Frameworks / Development", [r"\bsvelte(?:kit)?\b"], {"core"}),
    "Vite": ("Frameworks / Development", [r"\bvite\b"], set()),
    "Webpack": ("Frameworks / Development", [r"\bwebpack\b"], set()),
    "Node.js": ("Frameworks / Development", [r"\bnode\.?js\b", r"\bnode/express\b"], set()),
    "Express": ("Frameworks / Development", [r"\bexpress\.?js\b", r"\bnode/express\b"], set()),
    "Python": ("Frameworks / Development", [r"\bpython\b"], set()),
    "Flask": ("Frameworks / Development", [r"\bflask\b"], set()),
    "Django": ("Frameworks / Development", [r"\bdjango\b"], set()),
    "PHP": ("Frameworks / Development", [r"\bphp\b"], set()),
    "Java": ("Frameworks / Development", [r"\bjava\b(?!\s*script)"], {"specialized"}),
    "C#/.NET": ("Frameworks / Development", [r"\bc#", r"(?<![\w.])\.net\b", r"\basp\.net\b", r"\bdotnet\b"], {"specialized"}),
    "Ruby on Rails": ("Frameworks / Development", [r"\bruby\b", r"\brails\b"], {"specialized"}),
    "REST APIs": ("Frameworks / Development", [r"\brest(?:ful)?\b", r"\bapis?\b"], set()),
    "GraphQL": ("Frameworks / Development", [r"\bgraphql\b"], {"specialized"}),
    "SQL": ("Frameworks / Development", [r"\bsql\b"], set()),
    "MySQL": ("Frameworks / Development", [r"\bmysql\b"], set()),
    "PostgreSQL": ("Frameworks / Development", [r"\bpostgres(?:ql)?\b"], set()),
    "MongoDB": ("Frameworks / Development", [r"\bmongo(?:db)?\b"], set()),
    "Testing (Jest/Cypress/etc.)": ("Frameworks / Development", [r"\bjest\b", r"\bcypress\b", r"\bplaywright\b", r"\bunit test", r"\bautomated test", r"\btest[- ]driven\b", r"\bvitest\b", r"\bmocha\b"], set()),
    "Storybook": ("Frameworks / Development", [r"\bstorybook\b"], set()),
    # --- CMS / site builders / ecommerce ---
    "WordPress": ("CMS / Website Builders", [r"\bwordpress\b"], {"core"}),
    "WooCommerce": ("CMS / Website Builders", [r"\bwoocommerce\b"], set()),
    "Elementor": ("CMS / Website Builders", [r"\belementor\b"], {"core"}),
    "Blocksy": ("CMS / Website Builders", [r"\bblocksy\b"], set()),
    "Webflow": ("CMS / Website Builders", [r"\bwebflow\b"], {"core"}),
    "Shopify": ("CMS / Website Builders", [r"\bshopify\b", r"\bliquid\b(?= templat)"], {"core"}),
    "Squarespace": ("CMS / Website Builders", [r"\bsquarespace\b"], {"core"}),
    "Wix": ("CMS / Website Builders", [r"\bwix\b"], {"core"}),
    "Drupal": ("CMS / Website Builders", [r"\bdrupal\b"], {"core"}),
    "Magento": ("CMS / Website Builders", [r"\bmagento\b"], {"specialized"}),
    "HubSpot": ("CMS / Website Builders", [r"\bhubspot\b"], set()),
    "CMS (general)": ("CMS / Website Builders", [r"\bcms\b", r"\bcontent management system"], {"core"}),
    # --- Design ---
    "Figma": ("Design", [r"\bfigma\b"], {"core"}),
    "Photoshop": ("Design", [r"\bphotoshop\b"], set()),
    "Illustrator": ("Design", [r"\billustrator\b"], set()),
    "Adobe Creative Suite": ("Design", [r"\badobe creative (?:suite|cloud)\b", r"\badobe cc\b"], set()),
    "Adobe XD": ("Design", [r"\badobe xd\b"], set()),
    "Sketch": ("Design", [r"\bsketch\b(?= ?(?:app|,|/| or| and))"], set()),
    "InDesign": ("Design", [r"\bindesign\b"], set()),
    "After Effects": ("Design", [r"\bafter effects\b"], set()),
    "Video Editing": ("Design", [r"\bpremiere\b", r"\bvideo editing\b", r"\bfinal cut\b"], set()),
    "Canva": ("Design", [r"\bcanva\b"], set()),
    "UI Design": ("Design", [r"\bui\b", r"\buser interface"], {"core"}),
    "UX Design": ("Design", [r"\bux\b", r"\buser experience"], set()),
    "UX Research": ("Design", [r"\buser research\b", r"\busability test", r"\bux research\b"], set()),
    "Wireframing/Prototyping": ("Design", [r"\bwirefram", r"\bprototyp"], set()),
    "Design Systems": ("Design", [r"\bdesign systems?\b", r"\bcomponent librar"], set()),
    "Visual Design": ("Design", [r"\bvisual design\b"], set()),
    "Graphic Design": ("Design", [r"\bgraphic design\b"], set()),
    # --- Tools ---
    "Git": ("Development Tools", [r"\bgit\b", r"\bversion control\b"], set()),
    "GitHub": ("Development Tools", [r"\bgithub\b"], set()),
    "VS Code": ("Development Tools", [r"\bvs ?code\b", r"\bvisual studio code\b"], set()),
    "Vercel": ("Development Tools", [r"\bvercel\b"], set()),
    "npm": ("Development Tools", [r"\bnpm\b", r"\byarn\b"], set()),
    "CI/CD": ("Development Tools", [r"\bci/cd\b", r"\bcontinuous integration\b", r"\bgithub actions\b"], set()),
    "Docker": ("Development Tools", [r"\bdocker\b"], {"specialized"}),
    "Kubernetes": ("Development Tools", [r"\bkubernetes\b", r"\bk8s\b"], {"specialized"}),
    "AWS": ("Development Tools", [r"\baws\b", r"\bamazon web services\b"], {"specialized"}),
    "Azure": ("Development Tools", [r"\bazure\b"], {"specialized"}),
    "Google Cloud": ("Development Tools", [r"\bgcp\b", r"\bgoogle cloud\b"], {"specialized"}),
    "Linux": ("Development Tools", [r"\blinux\b"], set()),
    "Jira": ("Development Tools", [r"\bjira\b"], set()),
    "Agile/Scrum": ("Development Tools", [r"\bagile\b", r"\bscrum\b"], set()),
    # --- Marketing / content (relevant to hybrid web roles) ---
    "SEO": ("Marketing / Content", [r"\bseo\b", r"\bsearch engine optimi[sz]ation\b"], set()),
    "Google Analytics": ("Marketing / Content", [r"\bgoogle analytics\b", r"\bga4\b"], set()),
    "Google Tag Manager": ("Marketing / Content", [r"\btag manager\b", r"\bgtm\b"], set()),
    "Email Marketing": ("Marketing / Content", [r"\bemail marketing\b", r"\bmailchimp\b", r"\bklaviyo\b", r"\bemail campaigns?\b"], set()),
    "Copywriting": ("Marketing / Content", [r"\bcopywriting\b", r"\bweb copy\b"], set()),
    "Social Media": ("Marketing / Content", [r"\bsocial media\b"], set()),
    "A/B Testing": ("Marketing / Content", [r"\ba/b test"], set()),
    "Salesforce": ("Marketing / Content", [r"\bsalesforce\b"], {"specialized"}),
    # --- Transferable ---
    "Project Management": ("Transferable", [r"\bproject management\b", r"\bmanage projects\b"], set()),
    "Client Communication": ("Transferable", [r"\bclient communication\b", r"\bclient[- ]facing\b", r"\bstakeholder"], set()),
    "Customer Service": ("Transferable", [r"\bcustomer service\b"], set()),
}

_compiled = {}


def _patterns_for(name):
    """Compile (once) and return the regex list for a skill name.
    Unknown names (custom skills you add yourself) get an automatic
    'whole word' pattern so they still work."""
    if name not in _compiled:
        entry = SKILL_LIBRARY.get(name)
        raw = entry[1] if entry else [r"\b" + re.escape(name.lower()) + r"\b"]
        _compiled[name] = [re.compile(p, re.IGNORECASE) for p in raw]
    return _compiled[name]


def category_of(name):
    entry = SKILL_LIBRARY.get(name)
    return entry[0] if entry else "Other"


def has_flag(name, flag):
    entry = SKILL_LIBRARY.get(name)
    return bool(entry and flag in entry[2])


def canonical_name(name):
    """Map what a person typed ('reactjs', 'html5') to the library's name."""
    clean = (name or "").strip()
    for canonical in SKILL_LIBRARY:
        if canonical.lower() == clean.lower():
            return canonical
    for canonical in SKILL_LIBRARY:
        if any(p.fullmatch(clean) for p in _patterns_for(canonical)):
            return canonical
    return clean


def find_skills(text, extra_names=()):
    """Return the set of canonical skill names mentioned in `text`.
    extra_names lets custom profile skills be searched too."""
    if not text:
        return set()
    found = set()
    names = list(SKILL_LIBRARY) + [n for n in extra_names if n not in SKILL_LIBRARY]
    for name in names:
        if any(p.search(text) for p in _patterns_for(name)):
            found.add(name)
    return found
