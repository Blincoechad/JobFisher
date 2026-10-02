/*
  tracker.js — The full job history table with filters.

  The filter form's values become URL query parameters:
    /api/jobs?status=Applied&q=tampa&sort=newest
  The server does the filtering in SQL, and we just draw the rows it returns.
*/
import { api } from "./api.js";
import { openJobDialog, STATUSES } from "./cards.js";
import { esc, formatDate, toast, toneClass } from "./format.js";

const form = () => document.getElementById("tracker-filters");

export async function loadTracker() {
  const params = new URLSearchParams(new FormData(form()));
  try {
    const [jobs, dashboard] = await Promise.all([api(`/api/jobs?${params}`), api("/api/dashboard")]);
    renderRows(jobs);
    renderStats(dashboard.tracker);
  } catch (err) {
    toast(err.message, true);
  }
}

function renderRows(jobs) {
  const body = document.getElementById("tracker-rows");
  if (!jobs.length) {
    body.innerHTML = '<tr><td colspan="5" class="muted">No jobs match these filters. Clear the filters, or press Refresh jobs to search.</td></tr>';
    return;
  }
  body.innerHTML = jobs.map((job) => `
    <tr>
      <td><button class="link-btn" type="button" data-id="${job.id}">${esc(job.title)}</button>
        <div class="muted small">${esc(job.company)}, ${esc(job.location || job.work_arrangement)}</div>${job.stale ? '<div class="small badge-stale">⚠ Listing may be stale</div>' : ""}</td>
      <td><span class="fit-pill ${toneClass(job.fit_category)}">${Math.round(job.fit_score)}%</span>
        <div class="muted small">${esc(job.fit_category)}</div></td>
      <td>${esc(job.status)}</td>
      <td>${formatDate(job.date_discovered)}</td>
      <td>${formatDate(job.last_seen_active)}</td>
    </tr>`).join("");
}

function renderStats(t) {
  const missing = t.common_missing_skills_in_applications.map((m) => `${esc(m.skill)} (${m.count})`).join(", ");
  document.getElementById("tracker-stats").innerHTML = `
    <dl class="stat-row">
      <div><dt>Jobs viewed</dt><dd>${t.jobs_viewed}</dd></div>
      <div><dt>Applications</dt><dd>${t.applications_submitted}</dd></div>
      <div><dt>Interviews</dt><dd>${t.interviews_received}</dd></div>
      <div><dt>Interview rate</dt><dd>${t.interview_rate == null ? "—" : t.interview_rate + "%"}</dd></div>
      <div><dt>Avg. fit applied</dt><dd>${t.average_fit_of_applications == null ? "—" : t.average_fit_of_applications + "%"}</dd></div>
    </dl>
    ${missing ? `<p class="small muted" style="margin-top:.5rem">Skills most often missing in jobs you applied to: ${missing}</p>` : ""}`;
}

export function wireTracker() {
  const select = form().elements.status;
  select.insertAdjacentHTML("beforeend", STATUSES.map((s) => `<option>${s}</option>`).join(""));
  form().addEventListener("input", debounce(loadTracker, 250));
  form().addEventListener("submit", (e) => e.preventDefault());
  document.getElementById("tracker-rows").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-id]");
    if (button) openJobDialog(button.dataset.id, loadTracker);
  });
}

/* Waits until you stop typing for `ms` before searching, instead of sending
   a request on every keystroke. */
function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
