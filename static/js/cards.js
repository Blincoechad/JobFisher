/*
  cards.js — How ONE job is displayed: the dashboard card and the detail dialog.

  WHAT: functions that take a job object (from the API) and return HTML.
  WHY:  The dashboard and the tracker both show jobs. Putting the job display
        code in one module means a change here updates both places.
  HOW:  renderCard(job) builds an HTML string (every outside value goes
        through esc()). openJobDialog(id) fetches the full job and fills
        the <dialog> element.
*/
import { api } from "./api.js";
import { esc, formatDate, safeUrl, toast, toneClass } from "./format.js";

export const STATUSES = ["New", "Viewed", "Saved", "Applied", "Interview", "Offer", "Rejected",
  "Expired", "Hidden", "No Longer Relevant"];

const FRESHNESS_BADGE = {
  new: '<span class="badge badge-new">New</span>',
  updated: '<span class="badge badge-updated">Updated</span>',
};

function badges(job) {
  let html = FRESHNESS_BADGE[job.freshness] || "";
  if (job.status === "Saved") html += ' <span class="badge badge-saved">Saved</span>';
  if (job.stale) html += ' <span class="badge badge-stale" title="Not seen in its source recently">⚠ Listing may be stale</span>';
  return html;
}

export function gauge(job) {
  const score = Math.round(job.fit_score || 0);
  return `
    <div class="gauge ${toneClass(job.fit_category)}" style="--level:${Math.max(4, score)}%"
         aria-label="Application fit ${score} percent, ${esc(job.fit_category)}">
      <span class="score">${score}<small>%</small></span>
      <span class="cat">${esc(job.fit_category || "Not scored")}</span>
    </div>`;
}

export function renderCard(job) {
  const a = job.analysis || {};
  const strengths = (a.strengths || []).slice(0, 5)
    .map((s) => `<li>${esc(s.skill)} <span class="ev">→ ${esc(s.evidence)}</span></li>`).join("");
  const gaps = (a.gaps || []).slice(0, 4).map((g) => `<li>${esc(g)}</li>`).join("");
  const diff = a.difficulty || {};
  const comp = a.competitiveness || {};
  const hire = a.hiring_context || {};
  const url = safeUrl(job.url);

  return `
  <article class="card" data-id="${job.id}">
    ${gauge(job)}
    <div class="card-body">
      <div>
        <div class="card-title"><h3>${esc(job.title)}</h3> ${badges(job)}</div>
        <div class="meta">
          <span class="company">${esc(job.company)}</span>
          <span>${esc(job.location || "Location not stated")}</span>
          <span>${esc(job.work_arrangement || "Unknown")}</span>
          <span>${job.salary_text ? esc(job.salary_text) : "Salary not listed"}</span>
          <span>${job.date_posted ? "Posted " + formatDate(job.date_posted) : "Post date not listed"}</span>
        </div>
      </div>
      <div class="signals">
        <span class="signal" title="${esc(diff.text)}">${esc(diff.emoji)} <b>${esc(diff.level || "—")}</b> difficulty</span>
        <span class="signal" title="${esc(comp.text)}">${esc(comp.emoji)} ${esc(comp.level || "—")}</span>
        <span class="signal" title="${esc(hire.text)}">${esc(hire.emoji)} ${esc(hire.level || "—")}</span>
      </div>
      <p class="summary">${esc(a.summary)}</p>
      <div class="two-col">
        <div><h4>Main strengths</h4><ul>${strengths || "<li>None identified</li>"}</ul></div>
        <div><h4>Main gaps</h4><ul>${gaps || "<li>No gaps identified in the posting text</li>"}</ul></div>
      </div>
      <p class="portfolio-note">${esc((a.portfolio || {}).note)}</p>
      <div class="card-actions">
        <button class="btn" type="button" data-action="details">See full analysis</button>
        <button class="btn btn-quiet" type="button" data-action="status" data-status="${job.status === "Saved" ? "Viewed" : "Saved"}">
          ${job.status === "Saved" ? "Unsave" : "Save"}</button>
        <button class="btn btn-quiet" type="button" data-action="status" data-status="Hidden">Not interested</button>
        ${url ? `<a class="btn btn-primary apply" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Apply</a>` : ""}
      </div>
    </div>
  </article>`;
}

/* ---------------- Detail dialog ---------------- */

const COMPONENT_LABELS = {
  skills: "Required skills", experience: "Experience", portfolio: "Portfolio",
  education: "Education", level: "Job level", location: "Location",
};

function componentRows(a) {
  const notes = {
    skills: a.skills?.note, experience: a.experience?.note, portfolio: a.portfolio?.note,
    education: a.education?.note, level: a.level?.note, location: a.location?.note,
  };
  return Object.keys(COMPONENT_LABELS).map((key) => {
    const value = Math.round((a.components?.[key] || 0) * 100);
    return `
      <div class="component"><span>${COMPONENT_LABELS[key]} <span class="muted small">(${a.weights?.[key] ?? 0}%)</span></span>
        <div class="bar"><span style="width:${value}%"></span></div><b>${value}%</b></div>
      <p class="component-note">${esc(notes[key])}</p>`;
  }).join("");
}

function skillTable(a) {
  const rows = (a.skills?.rows || []).map((r) => `
    <tr><td>${esc(r.skill)}</td><td>${r.required ? "Required" : "Preferred"}</td>
    <td class="${r.status === "match" ? "ok" : "gap"}">${r.status === "match" ? "✓ " + esc(r.evidence) : "Gap"}</td></tr>`).join("");
  return rows
    ? `<table class="skill-table"><thead><tr><th>Skill</th><th>In posting</th><th>Your evidence</th></tr></thead><tbody>${rows}</tbody></table>`
    : '<p class="muted">No recognisable skills were found in this posting.</p>';
}

function dialogHtml(job) {
  const a = job.analysis || {};
  const app = job.application || {};
  const url = safeUrl(job.url);
  const statusButtons = STATUSES.map((s) =>
    `<button class="btn" type="button" data-set-status="${s}" aria-pressed="${job.status === s}">${s}</button>`).join("");
  return `
    <div class="dialog-head">
      <div>
        <h2 id="job-dialog-title">${esc(job.title)}</h2>
        <div class="meta"><span class="company">${esc(job.company)}</span><span>${esc(job.location || "Location not stated")}</span>
          <span>${esc(job.work_arrangement)}</span><span>${job.salary_text ? esc(job.salary_text) : "Salary not listed"}</span>
          ${job.employment_type ? `<span>${esc(job.employment_type)}</span>` : ""}</div>
        <div class="card-title" style="margin-top:.4rem">${badges(job)}</div>
      </div>
      <button class="btn-close" type="button" data-close aria-label="Close">×</button>
    </div>

    <div class="detail-grid">
      <div>
        <h3>${Math.round(job.fit_score)}% ${esc(job.fit_category)}</h3>
        <p>${esc(a.summary)}</p>
        ${a.caps?.length ? `<ul class="caps">${a.caps.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : ""}
        ${componentRows(a)}
        <p class="muted small">${esc(a.disclaimer)} ${(a.data_notes || []).map(esc).join(" ")}</p>
        <h3 class="subhead">Skills in this posting</h3>
        ${skillTable(a)}
      </div>
      <div>
        <h3 class="subhead">Application difficulty</h3>
        <p>${esc(a.difficulty?.emoji)} ${esc(a.difficulty?.text)}</p>
        <h3 class="subhead">Interview competitiveness</h3>
        <p>${esc(a.competitiveness?.emoji)} ${esc(a.competitiveness?.text)}</p>
        ${(a.competitiveness?.signals || []).length ? `<ul class="small">${a.competitiveness.signals.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>` : ""}
        <h3 class="subhead">Company hiring context</h3>
        <p>${esc(a.hiring_context?.emoji)} <b>${esc(a.hiring_context?.level)}</b>: ${esc(a.hiring_context?.text)}</p>
        <h3 class="subhead">Portfolio relevance</h3>
        <ul class="small">${(a.portfolio?.projects || []).map((p) => `<li><b>${esc(p.name)}</b> (${esc(p.type)}): ${p.skills.map(esc).join(", ")}</li>`).join("") || "<li>No matching projects.</li>"}</ul>

        <h3 class="subhead">Freshness</h3>
        <dl class="dates">
          <dt>First discovered</dt><dd>${formatDate(job.date_discovered)}</dd>
          <dt>Date posted</dt><dd>${formatDate(job.date_posted)}</dd>
          <dt>Last checked</dt><dd>${formatDate(job.last_checked)}</dd>
          <dt>Last confirmed active</dt><dd>${formatDate(job.last_seen_active)}</dd>
          <dt>Status</dt><dd>${esc(job.status)}</dd>
          <dt>Source</dt><dd>${(job.sources || [job.source]).map(esc).join(", ")}</dd>
        </dl>
        <button class="btn btn-quiet" type="button" data-confirm-active>I checked: it's still open</button>

        <h3 class="subhead">Status</h3>
        <div class="status-buttons">${statusButtons}</div>

        <h3 class="subhead">Application notes</h3>
        <form class="app-form manual-form">
          <label>Date applied <input type="date" name="date_applied" value="${esc(app.date_applied || "")}"></label>
          <label>Interview dates (comma separated) <input name="interview_dates" placeholder="2026-10-15, 2026-10-22" value="${esc((app.interview_dates || []).join(", "))}"></label>
          <label>Notes <textarea name="notes" rows="3">${esc(app.notes || "")}</textarea></label>
          <div><button class="btn" type="submit">Save notes</button></div>
        </form>
      </div>
    </div>

    <h3 class="subhead">Original description</h3>
    <div class="description">${esc(job.description)}</div>
    <div class="dialog-actions">
      ${url ? `<a class="btn btn-primary" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Open the posting to apply</a>` : ""}
    </div>`;
}

/* Opens the dialog. `onChange` lets the page that opened it reload its data
   after you change a status (so the dashboard stays in sync). */
export async function openJobDialog(id, onChange) {
  const dialog = document.getElementById("job-dialog");
  const body = document.getElementById("job-dialog-body");
  let job;
  try {
    job = await api(`/api/jobs/${id}?view=1`); // ?view=1 marks New -> Viewed
  } catch (err) {
    toast(err.message, true);
    return;
  }
  body.innerHTML = dialogHtml(job);
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;

  body.querySelector("[data-close]").onclick = () => dialog.close();
  body.querySelectorAll("[data-set-status]").forEach((btn) => {
    btn.onclick = async () => {
      try {
        await api(`/api/jobs/${id}/status`, { method: "POST", body: { status: btn.dataset.setStatus } });
        toast(`Marked as ${btn.dataset.setStatus}`);
        await openJobDialog(id, onChange);
        onChange?.();
      } catch (err) { toast(err.message, true); }
    };
  });
  body.querySelector("[data-confirm-active]").onclick = async () => {
    await api(`/api/jobs/${id}/confirm-active`, { method: "POST" });
    toast("Marked as still active");
    await openJobDialog(id, onChange);
    onChange?.();
  };
  body.querySelector(".app-form").onsubmit = async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await api(`/api/jobs/${id}/application`, {
        method: "POST",
        body: {
          date_applied: form.get("date_applied"),
          interview_dates: form.get("interview_dates").split(",").map((d) => d.trim()).filter(Boolean),
          notes: form.get("notes"),
        },
      });
      toast("Notes saved");
      onChange?.();
    } catch (err) { toast(err.message, true); }
  };
  onChange?.();
}

/* Clicking the dark area outside a dialog closes it. */
export function closeOnBackdrop(dialog) {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
}
