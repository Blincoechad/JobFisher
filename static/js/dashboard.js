/*
  dashboard.js — The main view: the strongest jobs plus the summary panels.

  Flow:
    loadDashboard()  -> GET  /api/dashboard -> renderDashboard(data)
    refreshJobs()    -> POST /api/refresh   -> renderDashboard(data)

  The server sends ALL dashboard data in one response, so one request
  redraws the whole view.
*/
import { api } from "./api.js";
import { openJobDialog, renderCard } from "./cards.js";
import { esc, formatDateTime, money, timeAgo, toast } from "./format.js";

let lastRefreshIso = null;

export async function loadDashboard() {
  try {
    renderDashboard(await api("/api/dashboard"));
  } catch (err) {
    toast(err.message, true);
  }
}

export async function refreshJobs() {
  const button = document.getElementById("refresh-btn");
  const progress = document.getElementById("search-progress");
  button.disabled = true;
  button.classList.add("is-spinning");
  progress.hidden = false;
  try {
    const data = await api("/api/refresh", { method: "POST" });
    renderDashboard(data);
    const r = data.last_refresh || {};
    const failed = (r.source_report || []).filter((s) => s.status === "error").length;
    toast(`Found ${r.new_count ?? 0} new job${r.new_count === 1 ? "" : "s"}` + (failed ? `. ${failed} source(s) failed; see Source details.` : "."), failed > 0);
  } catch (err) {
    toast(err.message, true);
  } finally {
    button.disabled = false;
    button.classList.remove("is-spinning");
    progress.hidden = true;
  }
}

function renderDashboard(data) {
  const jobs = data.top_jobs || [];
  const topN = data.settings?.top_n || 8;
  lastRefreshIso = data.last_refresh?.finished_at || null;
  updateLastRefreshed();

  const title = document.getElementById("dash-title");
  const sub = document.getElementById("dash-sub");
  if (jobs.length) {
    title.textContent = jobs.length >= topN
      ? `Here are the ${topN} strongest currently available jobs for you`
      : `Here ${jobs.length === 1 ? "is the strongest job" : `are the ${jobs.length} strongest jobs`} that meet your minimum fit`;
    sub.textContent = "Ranked by how closely each posting lines up with your documented experience. These are alignment estimates, not hiring predictions.";
  } else {
    title.textContent = "No matches on the line yet";
    sub.textContent = "";
  }

  document.getElementById("resume-nudge").hidden = Boolean(data.resume);

  const cards = document.getElementById("job-cards");
  cards.innerHTML = jobs.length ? jobs.map(renderCard).join("") : emptyState(data.last_refresh);

  renderSummary(data.last_refresh);
  renderMarket(data.market);
  renderGaps(data.gaps);
  renderTrackerSummary(data.tracker);
}

function emptyState(lastRefresh) {
  if (!lastRefresh) {
    return `<div class="empty"><h2>Run your first search</h2>
      <p>Press <b>Refresh jobs</b> to search The Muse, Remotive and Jobicy for web design and development openings, then score each one against your profile.</p>
      <p class="muted">Before you do, it's worth uploading your resume on the <a href="#profile">Profile &amp; resume</a> page so the scores use it.</p></div>`;
  }
  return `<div class="empty"><h2>Nothing meets your minimum fit right now</h2>
    <p>The last search found ${lastRefresh.relevant} relevant posting(s), but none scored above your minimum. Try again later, add company boards in <a href="#settings">Settings</a>, or add a posting you found yourself with <b>Add a job manually</b>.</p></div>`;
}

export function updateLastRefreshed() {
  const el = document.getElementById("last-refreshed");
  el.textContent = lastRefreshIso ? `Last refreshed ${timeAgo(lastRefreshIso)}` : "Not refreshed yet";
  el.title = lastRefreshIso ? `Last updated: ${formatDateTime(lastRefreshIso)}` : "";
}

function renderSummary(r) {
  const list = document.getElementById("search-summary");
  const report = document.querySelector("#source-report ul");
  if (!r) {
    list.innerHTML = '<p class="muted">No searches yet.</p>';
    report.innerHTML = "";
    return;
  }
  const stats = [["Jobs scanned", r.scanned], ["Relevant jobs", r.relevant], ["New jobs", r.new_count],
    ["Updated", r.updated_count], ["Strong matches", r.strong], ["Displayed", r.displayed]];
  list.innerHTML = stats.map(([label, value]) => `<div><dt>${label}</dt><dd>${value ?? 0}</dd></div>`).join("");
  report.innerHTML = (r.source_report || []).map((s) =>
    `<li><b>${esc(s.source)}</b>: <span class="st-${esc(s.status)}">${esc(s.status)}</span>. ${esc(s.message)}</li>`).join("")
    + `<li class="muted">Last updated: ${formatDateTime(r.finished_at)}</li>`;
}

function bars(items, valueKey, labelKey, cls = "") {
  const max = Math.max(...items.map((i) => i[valueKey]), 1);
  return `<ul class="bars ${cls}">${items.map((i) => `
    <li><span>${esc(i[labelKey])}</span><span class="muted">${i.percent != null ? i.percent + "%" : i[valueKey]}</span>
      <span class="bar"><span style="width:${Math.round((100 * i[valueKey]) / max)}%"></span></span></li>`).join("")}</ul>`;
}

function renderMarket(m) {
  const el = document.getElementById("market");
  if (!m || !m.job_count) {
    el.innerHTML = '<p class="muted">Market trends appear after your first search.</p>';
    return;
  }
  const salary = m.salary.count
    ? `${money(m.salary.low)} to ${money(m.salary.high)} (median ${money(m.salary.median)}), from ${m.salary.count} posting(s) that list pay`
    : "None of the current postings list a salary.";
  el.innerHTML = `
    <dl class="kv"><dt>Relevant active jobs</dt><dd>${m.job_count}</dd>
      <dt>Labelled entry-level</dt><dd>${m.entry_level_count}</dd></dl>
    <h3 class="subhead">Most requested skills</h3>${bars(m.top_skills.slice(0, 6), "count", "skill")}
    <h3 class="subhead">Experience asked for</h3>
    <dl class="kv">${m.experience.map((e) => `<dt>${esc(e.bucket)}</dt><dd>${e.count}</dd>`).join("")}</dl>
    <h3 class="subhead">Salary range</h3><p class="small">${salary}</p>
    <h3 class="subhead">Most common titles</h3>
    <ul class="small">${m.top_titles.map((t) => `<li>${esc(t.title)} (${t.count})</li>`).join("")}</ul>`;
}

function renderGaps(g) {
  const el = document.getElementById("gaps");
  if (!g || !g.job_count) {
    el.innerHTML = '<p class="muted">After a search, skills that keep showing up in relevant jobs but aren\'t in your profile will be listed here.</p>';
    return;
  }
  if (!g.gaps.length) {
    el.innerHTML = '<p>Every skill in the current relevant postings appears in your profile or resume.</p>';
    return;
  }
  el.innerHTML = bars(g.gaps, "count", "skill", "gap-bars") +
    `<p class="muted small" style="margin-top:.75rem">Share of ${g.job_count} relevant job(s) that mention each skill.
     ${g.enough_data ? "" : "That's a small sample, so treat these as early signals."} This is evidence to weigh, not a list of things you must learn.</p>`;
}

function renderTrackerSummary(t) {
  const el = document.getElementById("tracker-summary");
  const c = t.counts;
  el.innerHTML = `
    <dl class="stat-row">
      <div><dt>Applied</dt><dd>${t.applications_submitted}</dd></div>
      <div><dt>Interviews</dt><dd>${t.interviews_received}</dd></div>
      <div><dt>Rejected</dt><dd>${c.Rejected}</dd></div>
      <div><dt>Active</dt><dd>${t.active}</dd></div>
    </dl>
    <dl class="kv" style="margin-top:1rem">
      <dt>Saved for later</dt><dd>${c.Saved}</dd>
      <dt>Offers</dt><dd>${c.Offer}</dd>
      <dt>Interview rate</dt><dd>${t.interview_rate == null ? "—" : t.interview_rate + "%"}</dd>
      <dt>Average fit of applications</dt><dd>${t.average_fit_of_applications == null ? "—" : t.average_fit_of_applications + "%"}</dd>
    </dl>
    <p class="small" style="margin-top:.75rem"><a href="#tracker">Open the tracker</a></p>`;
}

/* Event delegation: ONE click listener on the cards container handles the
   buttons on every card, even cards added later. Each button says what it
   does with data-action, and the card says which job with data-id. */
export function wireDashboard() {
  document.getElementById("job-cards").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const id = button.closest(".card").dataset.id;
    if (button.dataset.action === "details") {
      openJobDialog(id, loadDashboard);
    } else if (button.dataset.action === "status") {
      try {
        await api(`/api/jobs/${id}/status`, { method: "POST", body: { status: button.dataset.status } });
        toast(button.dataset.status === "Hidden" ? "Hidden. It won't be recommended again." : `Marked as ${button.dataset.status}`);
        loadDashboard();
      } catch (err) { toast(err.message, true); }
    }
  });
  document.getElementById("refresh-btn").addEventListener("click", refreshJobs);
  setInterval(updateLastRefreshed, 60_000); // keep "12 minutes ago" accurate
}
