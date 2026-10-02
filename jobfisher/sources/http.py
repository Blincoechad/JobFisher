"""Shared HTTP helper so every source behaves politely and consistently."""

import requests

HEADERS = {"User-Agent": "JobFisher/1.0 (personal job-search dashboard; non-commercial)"}
TIMEOUT = 20  # seconds — never let one slow site freeze the whole refresh


class SourceSkipped(Exception):
    """Raised when a source can't run (e.g. no API key). Not an error."""


def get_json(url, params=None):
    response = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()  # turns 404/500 responses into exceptions
    return response.json()
