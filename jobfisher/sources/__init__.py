"""
sources/ — One small file per job source.

Every source module exposes the same function:

    fetch(source_settings, app_settings) -> list of jobs (in normalize.make_job shape)

Because they all share that "contract", refresh.py can loop over them without
caring how each one works inside. Adding a new source = add a file + one line
in SOURCES below.

Only official, free, public APIs/feeds are used — no scraping of sites that
forbid it (e.g. LinkedIn, Indeed). For those, use "Add a job manually".
"""

from . import adzuna, greenhouse, jobicy, lever, remotive, themuse

SOURCES = {
    "themuse": themuse.fetch,
    "remotive": remotive.fetch,
    "jobicy": jobicy.fetch,
    "adzuna": adzuna.fetch,
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
}
