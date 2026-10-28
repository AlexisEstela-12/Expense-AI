import { getSession, getCsrfToken, clearSession } from "../auth/sessionStore.js";

export const API = "http://127.0.0.1:8000";

export async function apiFetch(url, options = {}, { sessionRequired = true, csrf = null } = {}) {
  const session = getSession();
  if (sessionRequired && session.status !== "authenticated") {
    throw new Error("La sesión finalizó. Inicia sesión nuevamente.");
  }
  const method = (options.method || "GET").toUpperCase();
  const headers = { ...options.headers };
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = csrf ?? getCsrfToken();
    if (token) headers["X-CSRF-Token"] = token;
  }
  const response = await fetch(url, { ...options, headers, credentials: "include" });
  if (sessionRequired && session.generation !== getSession().generation) {
    throw new Error("La sesión finalizó. Inicia sesión nuevamente.");
  }
  if (sessionRequired && response.status === 401) {
    clearSession(session.generation);
    throw new Error("La sesión finalizó. Inicia sesión nuevamente.");
  }
  if (sessionRequired && response.status === 403) {
    throw new Error("Solicitud rechazada por seguridad. No se reintentó la operación. Comprueba tu sesión antes de continuar.");
  }
  return response;
}

export const get = (path) => apiFetch(`${API}/${path}`);

export const postJson = (path, payload) =>
  apiFetch(`${API}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const postWithoutBody = (path) =>
  apiFetch(`${API}/${path}`, { method: "POST" });
