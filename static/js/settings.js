/*
  settings.js — Scoring weights, locations, freshness rules and job sources.

  The form is generated from the settings object the server sends, then read
  back into the same shape on Save (PUT /api/settings). The server validates
  it, saves it, and re-scores every job with the new rules.
*/
import { api } from "./api.js";
import { esc, toast } from "./format.js";

let settings = null;

const WEIGHT_LABELS = {
  skills: "Required skill match", experience: "Experience match", portfolio: "Portfolio relevance",
  education: "Education match", level: "Job level (entry/junior)", location: "Location / arrangement",
};

// Friendly labels for source options (anything not listed shows its key).
const SOURCE_FIELD_LABELS = {
  categories: "Categories (one per line)", levels: "Levels (one per line)", locations: "Locations (one per line)",
  max_pages: "Pages to read per search (20 jobs each)", cooldown_hours: "Minimum hours between searches",
  tags: "Search keywords (one per line)", geo: "Region", what: "Search terms (one per line)",
  max_days_old: "Ignore postings older than (days)",
  boards: "Company board tokens (one per line), from boards.greenhouse.io/<token>",
  companies: "Company slugs (one per line), from jobs.lever.co/<slug>",
};
const SOURCE_NOTES = {
  remotive: "Remote jobs. Remotive asks for no more than about 4 searches a day, so the cooldown is 6 hours.",
  jobicy: "Remote jobs, filtered to the USA.",
  themuse: "Supports an entry-level filter and city filter.",
  adzuna: "Optional. Searches a real radius around your home city. Needs a free key in a .env file (see .env.example and the README).",
  greenhouse: "Direct company career pages. Their links go straight to the employer's application.",
  lever: "Direct company career pages hosted on Lever.",
};

const lines = (list) => esc((list || []).join("\n"));
const fromLines = (text) => text.split("\n").map((v) => v.trim()).filter(Boolean);

export async function loadSettings() {
  try {
    settings = await api("/api/settings");
    render();
  } catch (err) {
    toast(err.message, true);
  }
}

function render() {
  const s = settings;
  const form = document.getElementById("settings-form");
  form.innerHTML = `
    <fieldset>
      <legend>Fit score weights</legend>
      <p class="muted small">How much each factor counts toward the Application Fit Score. They should add up to 100.</p>
      <div class="grid-3">
        ${Object.entries(WEIGHT_LABELS).map(([key, label]) => `
          <label>${label}<input type="number" min="0" max="100" step="1" data-weight="${key}" value="${s.weights[key] ?? 0}"></label>`).join("")}
      </div>
      <p class="weights-total" id="weights-total"></p>
    </fieldset>

    <fieldset>
      <legend>Where to look</legend>
      <div class="grid-2">
        <label>Home city <input name="home" value="${esc(s.locations.home)}"></label>
        <label>Radius in miles (used by Adzuna) <input name="radius_miles" type="number" min="5" max="200" value="${s.locations.radius_miles}"></label>
      </div>
      <div class="grid-2">
        <label>Places that count as “in your area” (one per line)<textarea name="accepted_places" rows="7">${lines(s.locations.accepted_places)}</textarea></label>
        <label>Remote regions you're eligible for (one per line)<textarea name="remote_ok_regions" rows="7">${lines(s.locations.remote_ok_regions)}</textarea></label>
      </div>
      <p class="muted small">Work arrangements to include:</p>
      <div class="chips">
        ${["Remote", "Hybrid", "On-site"].map((a) => `<label class="check"><input type="checkbox" data-arrangement="${a}" ${s.locations.arrangements.includes(a) ? "checked" : ""}> ${a}</label>`).join("")}
      </div>
    </fieldset>

    <fieldset>
      <legend>Dashboard and freshness</legend>
      <div class="grid-3">
        <label>Jobs on the dashboard <input name="top_n" type="number" min="1" max="20" value="${s.display.top_n}"></label>
        <label>Minimum fit score to be shown <input name="min_fit_score" type="number" min="0" max="100" value="${s.display.min_fit_score}"></label>
        <label>Bonus points for jobs already shown <input name="stickiness_points" type="number" min="0" max="20" value="${s.display.stickiness_points}"></label>
        <label>Flag as stale after (days unseen) <input name="stale_after_days" type="number" min="1" value="${s.freshness.stale_after_days}"></label>
        <label>Mark expired after (days unseen) <input name="expire_after_days" type="number" min="2" value="${s.freshness.expire_after_days}"></label>
      </div>
    </fieldset>

    <fieldset>
      <legend>Job sources</legend>
      <p class="muted small">Only free, official APIs are used. LinkedIn and Indeed don't allow automated searching, so use “Add a job manually” for postings you find there.</p>
      ${Object.entries(s.sources).map(([key, cfg]) => sourceHtml(key, cfg)).join("")}
    </fieldset>

    <div class="save-bar">
      <span class="muted small">Saving re-scores every stored job with the new settings.</span>
      <button class="btn btn-primary" type="submit">Save settings</button>
    </div>`;
  updateTotal();
}

function sourceHtml(key, cfg) {
  const fields = Object.entries(cfg).filter(([k]) => !["enabled", "label"].includes(k)).map(([k, v]) => {
    const label = SOURCE_FIELD_LABELS[k] || k;
    if (Array.isArray(v)) {
      return `<label>${esc(label)}<textarea rows="3" data-source="${key}" data-field="${k}" data-type="list">${lines(v)}</textarea></label>`;
    }
    const type = typeof v === "number" ? "number" : "text";
    return `<label>${esc(label)}<input type="${type}" min="0" data-source="${key}" data-field="${k}" data-type="${type}" value="${esc(v)}"></label>`;
  }).join("");
  return `
    <div class="source-row">
      <label class="check"><input type="checkbox" data-source="${key}" data-field="enabled" data-type="bool" ${cfg.enabled ? "checked" : ""}>
        <b>${esc(cfg.label || key)}</b></label>
      <p class="muted small" style="margin:0">${esc(SOURCE_NOTES[key] || "")}</p>
      <div class="grid-2">${fields}</div>
    </div>`;
}

function updateTotal() {
  const total = [...document.querySelectorAll("[data-weight]")].reduce((sum, el) => sum + Number(el.value || 0), 0);
  const el = document.getElementById("weights-total");
  el.textContent = `Total: ${total}${total === 100 ? "" : " (scores are scaled, but 100 keeps the percentages easy to read)"}`;
  el.classList.toggle("off", total !== 100);
}

async function save(event) {
  event.preventDefault();
  const f = event.target.elements;
  const next = structuredClone(settings);
  document.querySelectorAll("[data-weight]").forEach((el) => (next.weights[el.dataset.weight] = Number(el.value || 0)));
  next.locations.home = f.home.value.trim();
  next.locations.radius_miles = Number(f.radius_miles.value);
  next.locations.accepted_places = fromLines(f.accepted_places.value);
  next.locations.remote_ok_regions = fromLines(f.remote_ok_regions.value).map((r) => r.toLowerCase());
  next.locations.arrangements = [...document.querySelectorAll("[data-arrangement]:checked")].map((el) => el.dataset.arrangement);
  next.display.top_n = Number(f.top_n.value);
  next.display.min_fit_score = Number(f.min_fit_score.value);
  next.display.stickiness_points = Number(f.stickiness_points.value);
  next.freshness.stale_after_days = Number(f.stale_after_days.value);
  next.freshness.expire_after_days = Number(f.expire_after_days.value);
  document.querySelectorAll("[data-source]").forEach((el) => {
    const cfg = next.sources[el.dataset.source];
    const type = el.dataset.type;
    cfg[el.dataset.field] = type === "bool" ? el.checked : type === "list" ? fromLines(el.value)
      : type === "number" ? Number(el.value || 0) : el.value.trim();
  });
  try {
    settings = await api("/api/settings", { method: "PUT", body: next });
    toast("Settings saved. Jobs have been re-scored.");
    render();
  } catch (err) {
    toast(err.message, true);
  }
}

export function wireSettings() {
  const form = document.getElementById("settings-form");
  form.addEventListener("submit", save);
  form.addEventListener("input", (event) => {
    if (event.target.matches("[data-weight]")) updateTotal();
  });
}
