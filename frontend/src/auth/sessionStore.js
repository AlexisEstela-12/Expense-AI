// Memory only. No cookies, browser storage, credentials or tokens are persisted.
let csrfToken = null;
let snapshot = Object.freeze({ status: "checking", user: null, generation: 0 });
const listeners = new Set();

export const getSession = () => snapshot;
export const getCsrfToken = () => csrfToken;
export const subscribeSession = (listener) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

function publish(status, user = null, token = null) {
  csrfToken = token;
  snapshot = Object.freeze({ status, user, generation: snapshot.generation + 1 });
  for (const listener of listeners) listener();
}

export function clearSession(expectedGeneration = snapshot.generation) {
  if (expectedGeneration === snapshot.generation) publish("anonymous");
}

export function sessionUnavailable(expectedGeneration) {
  if (expectedGeneration === snapshot.generation) publish("unavailable");
}

export function acceptSession(data, expectedGeneration) {
  if (expectedGeneration !== snapshot.generation) return false;
  if (data?.user?.id !== 1 || typeof data.user.username !== "string" ||
      !data.user.username || typeof data.csrf_token !== "string" ||
      !/^[0-9a-f]{64}$/.test(data.csrf_token) ||
      typeof data.expires_at !== "string" || !Number.isFinite(Date.parse(data.expires_at))) {
    throw new Error("La respuesta de sesión no es válida.");
  }
  publish("authenticated", Object.freeze({ id: data.user.id, username: data.user.username }), data.csrf_token);
  return true;
}
