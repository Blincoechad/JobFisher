/*
  format.js — small helpers for turning data into safe, readable text.

  SECURITY NOTE — escapeHtml():
  Job descriptions come from other websites. If we put that text into the page
  with innerHTML without escaping, a posting containing <script> or <img onerror=...>
  could run code in your dashboard (this attack is called XSS). escapeHtml()
  converts < > & " ' into harmless text. Rule of thumb: ANY outside text that
  goes into an HTML string passes through esc() first.
*/
export function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/* Only allow real web links in href attributes (blocks "javascript:" URLs). */
export function safeUrl(url) {
  return /^https?:\/\//i.test(url || "") ? url : "";
}

/* The server stores UTC times; the browser shows them in your local time. */
export function formatDate(iso) {
  if (!iso) return "—";
  const date = iso.length === 10 ? new Date(iso + "T12:00:00") : new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  const day = formatDate(iso);
  const time = date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${day} at ${time}`;
}

export function timeAgo(iso) {
  if (!iso) return "never";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

/* "Strong Match" -> "tone-strong" (a CSS class that sets the colour). */
export function toneClass(category) {
  const word = (category || "poor").split(" ")[0].toLowerCase();
  return `tone-${["strong", "possible", "stretch"].includes(word) ? word : "poor"}`;
}

export function money(n) {
  return n == null ? "—" : "$" + Math.round(n).toLocaleString();
}

let toastTimer;
export function toast(message, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.toggle("is-error", isError);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), isError ? 6000 : 3000);
}
