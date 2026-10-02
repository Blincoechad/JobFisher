/*
  main.js — The entry point. It runs once when the page loads and:
    1. connects each view's event listeners ("wiring")
    2. shows the right view for the URL hash (#dashboard, #tracker, ...)
    3. handles the "Add a job manually" dialog, which several views share

  Why a hash router? Changing location.hash doesn't reload the page, and the
  browser's Back button still works. It's the simplest "single-page app"
  pattern there is — no React Router needed.
*/
import { api } from "./api.js";
import { closeOnBackdrop, openJobDialog } from "./cards.js";
import { loadDashboard, wireDashboard } from "./dashboard.js";
import { toast } from "./format.js";
import { loadProfile, wireProfile } from "./profile.js";
import { loadSettings, wireSettings } from "./settings.js";
import { loadTracker, wireTracker } from "./tracker.js";

const VIEWS = {
  dashboard: loadDashboard,
  tracker: loadTracker,
  profile: loadProfile,
  settings: loadSettings,
};

function showView() {
  const name = location.hash.slice(1) in VIEWS ? location.hash.slice(1) : "dashboard";
  for (const view of Object.keys(VIEWS)) {
    document.getElementById(`view-${view}`).hidden = view !== name;
  }
  document.querySelectorAll(".tabs a").forEach((a) => {
    if (a.dataset.tab === name) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  VIEWS[name](); // load fresh data for the view you just opened
  window.scrollTo(0, 0);
}

function wireManualDialog() {
  const dialog = document.getElementById("manual-dialog");
  const form = document.getElementById("manual-form");
  const errorEl = document.getElementById("manual-error");
  closeOnBackdrop(dialog);
  closeOnBackdrop(document.getElementById("job-dialog"));

  document.querySelectorAll("[data-open-manual]").forEach((btn) =>
    btn.addEventListener("click", () => {
      errorEl.hidden = true;
      dialog.showModal();
    }));
  dialog.querySelectorAll("[data-close]").forEach((btn) => btn.addEventListener("click", () => dialog.close()));

  form.addEventListener("submit", async (event) => {
    event.preventDefault(); // stop the <form method="dialog"> from just closing
    const data = Object.fromEntries(new FormData(form));
    try {
      const job = await api("/api/jobs/manual", { method: "POST", body: data });
      dialog.close();
      form.reset();
      toast(`Added and scored: ${job.fit_score}% ${job.fit_category}`);
      showView();
      openJobDialog(job.id, showView);
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });
}

wireDashboard();
wireTracker();
wireProfile();
wireSettings();
wireManualDialog();
window.addEventListener("hashchange", showView);
showView();
