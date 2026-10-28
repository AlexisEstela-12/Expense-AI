import { API, apiFetch } from "./client.js";
import { getSession, clearSession, acceptSession, sessionUnavailable } from "../auth/sessionStore.js";

export async function restoreSession({ signal } = {}) {
  const generation = getSession().generation;
  try {
    const response = await apiFetch(`${API}/auth/session`, { signal }, { sessionRequired: false });
    if (signal?.aborted) return;
    if (response.status === 401) {
      clearSession(generation);
      return;
    }
    if (!response.ok) throw new Error("Sesión no disponible.");
    const data = await response.json();
    if (!signal?.aborted) acceptSession(data, generation);
  } catch (error) {
    if (!signal?.aborted) sessionUnavailable(generation);
  }
}

export async function login(username, password) {
  const generation = getSession().generation;
  let response;
  try {
    response = await apiFetch(`${API}/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }, { sessionRequired: false, csrf: "login" });
  } catch {
    throw new Error("No se pudo conectar para iniciar sesión.");
  }
  if (response.status === 401) throw new Error("Usuario o contraseña incorrectos.");
  if (response.status === 429) throw new Error("Demasiados intentos. Inténtalo más tarde.");
  if (response.status === 403) throw new Error("Inicio de sesión rechazado por seguridad. Comprueba el origen permitido.");
  if (!response.ok) throw new Error("No se pudo iniciar sesión.");
  try {
    if (!acceptSession(await response.json(), generation)) {
      throw new Error();
    }
  } catch {
    throw new Error("No se pudo confirmar la sesión.");
  }
}

export async function logout() {
  const generation = getSession().generation;
  try {
    const response = await apiFetch(`${API}/auth/logout`, { method: "POST" });
    if (!response.ok) throw new Error();
    clearSession(generation);
  } catch {
    if (getSession().status === "anonymous") return;
    throw new Error("No se pudo confirmar el cierre de sesión. No se ha reintentado. Vuelve a intentarlo manualmente.");
  }
}
