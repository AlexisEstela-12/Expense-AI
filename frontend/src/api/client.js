export const API = "http://127.0.0.1:8000";

export const get = (path) => fetch(`${API}/${path}`);

export const postJson = (path, payload) =>
  fetch(`${API}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const postWithoutBody = (path) =>
  fetch(`${API}/${path}`, { method: "POST" });
