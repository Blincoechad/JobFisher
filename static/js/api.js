/*
  api.js — the ONE place the browser talks to the Flask server.

  WHAT: a small wrapper around fetch().
  WHY:  every request needs the same things — send JSON, read JSON back, and
        turn server errors into a JavaScript Error with a readable message.
        Writing that once here keeps every other file short.
  HOW:  await api("/api/jobs")                       -> GET
        await api("/api/profile", { method: "PUT", body: profile })
        await api("/api/resume", { method: "POST", form: formData })  (file upload)
*/
export async function api(path, { method = "GET", body, form } = {}) {
  const options = { method, headers: {} };
  if (form) {
    options.body = form; // the browser sets the multipart headers for file uploads
  } else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error("Can't reach the JobFisher server. Is `python app.py` still running?");
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error((data && data.error) || `Request failed (${response.status}).`);
  }
  return data;
}
