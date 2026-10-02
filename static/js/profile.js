/*
  profile.js — The Profile & resume page.

  Two separate things live here, on purpose:
    1. The RESUME (a PDF you upload)       -> POST/DELETE /api/resume
    2. The PROFILE (editable summary data) -> GET/PUT    /api/profile

  Developer mindset: we keep the profile in ONE JavaScript object (`profile`).
  The form displays it; when you click Save, we read the form back into a
  fresh object and send it to the server. The UI displays the data — it
  doesn't own it. The server is the source of truth.
*/
import { api } from "./api.js";
import { esc, formatDate, toast } from "./format.js";

let profile = null;
let resumeSkills = new Set();

const SKILL_CATEGORIES = ["Front-End", "Frameworks / Development", "CMS / Website Builders", "Design",
  "Development Tools", "Marketing / Content", "Transferable", "Other"];

/* Field definitions for each repeatable section. One generic renderer
   (renderList) draws all three sections from these descriptions, instead of
   writing three nearly identical form builders. */
const LIST_FIELDS = {
  experience: [
    { key: "title", label: "Job title" },
    { key: "organization", label: "Organization" },
    { key: "type", label: "Type", options: ["professional", "freelance", "academic"] },
    { key: "is_web", label: "This was a web design/development role", checkbox: true },
    { key: "start", label: "Start (YYYY-MM)", placeholder: "YYYY-MM" },
    { key: "end", label: "End (YYYY-MM, blank if current)", placeholder: "YYYY-MM" },
    { key: "technologies", label: "Technologies used (comma separated)", list: true },
    { key: "transferable", label: "Transferable skills (comma separated)", list: true },
    { key: "description", label: "Description", textarea: true },
  ],
  projects: [
    { key: "name", label: "Project name" },
    { key: "type", label: "Type", options: ["personal", "client", "academic", "team"] },
    { key: "url", label: "URL" },
    { key: "technologies", label: "Technologies / skills demonstrated (comma separated)", list: true },
    { key: "description", label: "Description", textarea: true },
  ],
  education: [
    { key: "school", label: "School" },
    { key: "credential", label: "Credential" },
    { key: "field", label: "Field of study" },
    { key: "level", label: "Level", options: ["high_school", "certificate", "associate", "bachelor", "master"] },
    { key: "status", label: "Status", options: ["in_progress", "completed"] },
    { key: "expected", label: "Expected / completed" },
    { key: "gpa", label: "GPA" },
    { key: "coursework", label: "Relevant coursework (comma separated)", list: true },
  ],
};

export async function loadProfile() {
  try {
    const [p, resume] = await Promise.all([api("/api/profile"), api("/api/resume")]);
    profile = p;
    resumeSkills = new Set((resume?.parsed?.skills || []).map((s) => s.name));
    renderResume(resume);
    renderProfile();
  } catch (err) {
    toast(err.message, true);
  }
}

/* ---------------- Resume ---------------- */

function renderResume(resume) {
  const box = document.getElementById("resume-box");
  const submit = document.querySelector("#resume-form button[type=submit]");
  if (!resume) {
    box.innerHTML = '<p>No resume uploaded yet. Upload a text-based PDF (exported from Word, Google Docs or Canva).</p>';
    submit.textContent = "Upload resume";
    return;
  }
  submit.textContent = "Replace resume";
  const parsed = resume.parsed || {};
  const sections = (parsed.section_names || []).join(", ") || "none detected";
  const skills = (parsed.skills || []).map((s) => `<span class="chip">${esc(s.name)} <span class="muted small">${esc(s.found_in.join(", "))}</span></span>`).join("");
  box.innerHTML = `
    <div class="resume-current">
      <span class="file">${esc(resume.original_name)}</span>
      <span class="muted">Uploaded ${formatDate(resume.uploaded_at)}</span>
      <span class="muted">${Math.round(resume.size_bytes / 1024)} KB</span>
      <button class="btn btn-quiet" type="button" id="delete-resume">Delete resume</button>
    </div>
    <p class="small">Sections found: ${esc(sections)}.${parsed.has_structure ? "" : " Headings weren't recognised, so skills are treated as “listed on resume”."}</p>
    <h3 class="subhead">Skills found on your resume (and the section they're in)</h3>
    <div class="chips">${skills || '<span class="muted">No recognised skills found.</span>'}</div>
    <details class="extracted"><summary>Show the text JobFisher read from your PDF</summary><pre id="resume-text">Loading…</pre></details>`;

  box.querySelector("details").addEventListener("toggle", async (event) => {
    if (!event.target.open) return;
    const full = await api("/api/resume?text=1");
    document.getElementById("resume-text").textContent = full?.text || "";
  }, { once: true });

  document.getElementById("delete-resume").onclick = async () => {
    if (!confirm("Delete your resume from JobFisher? The file is removed from data/resumes/.")) return;
    await api("/api/resume", { method: "DELETE" });
    toast("Resume deleted");
    loadProfile();
  };
}

async function uploadResume(event) {
  event.preventDefault();
  const form = event.target;
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    await api("/api/resume", { method: "POST", form: new FormData(form) });
    toast("Resume saved. Every job has been re-scored.");
    form.reset();
    loadProfile();
  } catch (err) {
    toast(err.message, true); // e.g. "That file doesn't look like a real PDF."
  } finally {
    button.disabled = false;
  }
}

/* ---------------- Profile ---------------- */

function renderProfile() {
  const form = document.getElementById("profile-form");
  form.elements.name.value = profile.name || "";
  form.elements.headline.value = profile.headline || "";
  renderSkills();
  for (const section of Object.keys(LIST_FIELDS)) renderList(section);
}

function renderSkills() {
  const developing = new Set(profile.developing_skills || []);
  const groups = {};
  for (const skill of profile.skills) {
    (groups[skill.category || "Other"] ||= []).push(skill);
  }
  document.getElementById("skills-editor").innerHTML = Object.entries(groups).map(([cat, skills]) => `
    <div class="skill-group"><h3>${esc(cat)}</h3><div class="chips">
      ${skills.map((s) => `
        <span class="chip ${resumeSkills.has(s.name) ? "on-resume" : ""}" title="${resumeSkills.has(s.name) ? "Also on your resume" : "Profile only"}">
          ${esc(s.name)}
          <label><input type="checkbox" data-developing="${esc(s.name)}" ${developing.has(s.name) ? "checked" : ""}> still developing</label>
          <button type="button" data-remove-skill="${esc(s.name)}" aria-label="Remove ${esc(s.name)}">×</button>
        </span>`).join("")}
    </div></div>`).join("");
}

function renderList(section) {
  const container = document.getElementById(`${section}-editor`);
  const fields = LIST_FIELDS[section];
  container.innerHTML = (profile[section] || []).map((item, index) => `
    <div class="list-item" data-section="${section}" data-index="${index}">
      <div class="list-item-head">
        <strong>${esc(item.title || item.name || item.school || "New entry")}</strong>
        <button class="btn btn-quiet" type="button" data-remove-item>Remove</button>
      </div>
      <div class="grid-2">${fields.map((f) => fieldHtml(f, item[f.key])).join("")}</div>
    </div>`).join("") || '<p class="muted">Nothing added yet.</p>';
}

function fieldHtml(field, value) {
  const name = `data-key="${field.key}"`;
  if (field.checkbox) {
    return `<label class="check"><input type="checkbox" ${name} ${value ? "checked" : ""}> ${esc(field.label)}</label>`;
  }
  if (field.options) {
    const opts = field.options.map((o) => `<option ${o === value ? "selected" : ""}>${o}</option>`).join("");
    return `<label>${esc(field.label)}<select ${name}>${opts}</select></label>`;
  }
  const text = field.list ? (value || []).join(", ") : value ?? "";
  if (field.textarea) {
    return `<label style="grid-column:1/-1">${esc(field.label)}<textarea rows="2" ${name}>${esc(text)}</textarea></label>`;
  }
  return `<label>${esc(field.label)}<input ${name} value="${esc(text)}" placeholder="${esc(field.placeholder || "")}"></label>`;
}

/* Read every list item's inputs back into plain objects. */
function collectList(section) {
  return [...document.querySelectorAll(`.list-item[data-section="${section}"]`)].map((el) => {
    const original = profile[section][Number(el.dataset.index)] || {};
    const item = { ...original };
    for (const field of LIST_FIELDS[section]) {
      const input = el.querySelector(`[data-key="${field.key}"]`);
      if (field.checkbox) item[field.key] = input.checked;
      else if (field.list) item[field.key] = input.value.split(",").map((v) => v.trim()).filter(Boolean);
      else item[field.key] = input.value.trim();
    }
    return item;
  });
}

function syncFromForm() {
  // Before re-drawing a section, copy what's typed into the object so nothing is lost.
  for (const section of Object.keys(LIST_FIELDS)) profile[section] = collectList(section);
  profile.developing_skills = [...document.querySelectorAll("[data-developing]:checked")].map((c) => c.dataset.developing);
}

async function saveProfile(event) {
  event.preventDefault();
  syncFromForm();
  const form = event.target;
  profile.name = form.elements.name.value.trim();
  profile.headline = form.elements.headline.value.trim();
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    profile = await api("/api/profile", { method: "PUT", body: profile });
    toast("Profile saved. Every job has been re-scored.");
    renderProfile();
  } catch (err) {
    toast(err.message, true);
  } finally {
    button.disabled = false;
  }
}

export function wireProfile() {
  document.getElementById("resume-form").addEventListener("submit", uploadResume);
  document.getElementById("profile-form").addEventListener("submit", saveProfile);
  document.getElementById("new-skill-cat").innerHTML = SKILL_CATEGORIES.map((c) => `<option>${c}</option>`).join("");

  document.getElementById("add-skill-btn").addEventListener("click", () => {
    const input = document.getElementById("new-skill-name");
    const name = input.value.trim();
    if (!name) return;
    if (profile.skills.some((s) => s.name.toLowerCase() === name.toLowerCase())) {
      toast(`${name} is already in your skills.`, true);
      return;
    }
    syncFromForm();
    profile.skills.push({ name, category: document.getElementById("new-skill-cat").value, source: "summary" });
    input.value = "";
    renderSkills();
    toast(`Added ${name}. Remember to save.`);
  });

  document.getElementById("profile-form").addEventListener("click", (event) => {
    const removeSkill = event.target.closest("[data-remove-skill]");
    if (removeSkill) {
      syncFromForm();
      profile.skills = profile.skills.filter((s) => s.name !== removeSkill.dataset.removeSkill);
      renderSkills();
      return;
    }
    const removeItem = event.target.closest("[data-remove-item]");
    if (removeItem) {
      const item = removeItem.closest(".list-item");
      syncFromForm();
      profile[item.dataset.section].splice(Number(item.dataset.index), 1);
      renderList(item.dataset.section);
      return;
    }
    const add = event.target.closest("[data-add]");
    if (add) {
      syncFromForm();
      const section = add.dataset.add;
      const blank = { experience: { type: "professional", is_web: false, technologies: [], transferable: [] },
        projects: { type: "personal", technologies: [] },
        education: { level: "associate", status: "in_progress", coursework: [] } }[section];
      profile[section].push(blank);
      renderList(section);
    }
  });
}
