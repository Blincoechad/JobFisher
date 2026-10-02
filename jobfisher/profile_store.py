"""
profile_store.py — Load and save your profile and the app settings.

WHAT:  Four small functions: get/save profile, get/save settings.
WHY:   The rest of the app should not care HOW the profile is stored. If we ever
       moved from SQLite to something else, only this file would change.
HOW:   Each is a single JSON document in a one-row table. On first run we copy
       the defaults from config.py into the database.
"""

import copy

from . import config
from .db import get_connection, now_iso, to_json, from_json


def deep_merge(defaults, saved):
    """Return defaults with saved values laid on top.

    Why: if a future version of JobFisher adds a new setting, your saved
    settings won't have it yet. Merging means the new key gets its default
    value while everything you changed is kept.
    """
    result = copy.deepcopy(defaults)
    for key, value in (saved or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# --- Profile -------------------------------------------------------------------

def get_profile():
    with get_connection() as conn:
        row = conn.execute("SELECT data_json FROM profile WHERE id = 1").fetchone()
    if row is None:
        save_profile(config.DEFAULT_PROFILE)
        return copy.deepcopy(config.DEFAULT_PROFILE)
    return from_json(row["data_json"], copy.deepcopy(config.DEFAULT_PROFILE))


def save_profile(profile):
    validate_profile(profile)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO profile (id, data_json, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET data_json = excluded.data_json, "
            "updated_at = excluded.updated_at",
            (to_json(profile), now_iso()),
        )


def validate_profile(profile):
    """User-provided data can't be assumed valid — check the shape before saving."""
    if not isinstance(profile, dict):
        raise ValueError("Profile must be an object.")
    for key in ("skills", "education", "experience", "projects"):
        if not isinstance(profile.get(key, []), list):
            raise ValueError(f"Profile field '{key}' must be a list.")
    for skill in profile.get("skills", []):
        if not isinstance(skill, dict) or not str(skill.get("name", "")).strip():
            raise ValueError("Every skill needs a name.")
    for exp in profile.get("experience", []):
        if exp.get("type") not in ("professional", "freelance", "academic"):
            raise ValueError("Experience type must be professional, freelance or academic.")
    for proj in profile.get("projects", []):
        if proj.get("type") not in ("personal", "client", "academic", "team"):
            raise ValueError("Project type must be personal, client, academic or team.")


# --- Settings ------------------------------------------------------------------

def get_settings():
    with get_connection() as conn:
        row = conn.execute("SELECT data_json FROM settings WHERE id = 1").fetchone()
    saved = from_json(row["data_json"], {}) if row else {}
    return deep_merge(config.DEFAULT_SETTINGS, saved)


def save_settings(settings):
    # Merge FIRST, then validate — so saving only part of the settings
    # (e.g. just the display options) still checks the complete result.
    merged = deep_merge(get_settings(), settings)
    weights = merged.get("weights", {})
    for name, value in weights.items():
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"Weight '{name}' must be a positive number.")
    if sum(weights.values()) <= 0:
        raise ValueError("At least one weight must be above zero.")
    display = merged.get("display", {})
    if not 1 <= int(display.get("top_n", 8)) <= 20:
        raise ValueError("Number of dashboard jobs must be between 1 and 20.")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO settings (id, data_json, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET data_json = excluded.data_json, "
            "updated_at = excluded.updated_at",
            (to_json(merged), now_iso()),
        )
    return merged
