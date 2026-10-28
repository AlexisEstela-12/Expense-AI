import React, { useEffect, useSyncExternalStore } from "react";
import { getSession, subscribeSession } from "../auth/sessionStore.js";
import { restoreSession } from "../api/auth.js";
import Login from "./Login.jsx";

export default function AuthGate({ children }) {
  const session = useSyncExternalStore(subscribeSession, getSession, getSession);
  useEffect(() => {
    const controller = new AbortController();
    restoreSession({ signal: controller.signal });
    return () => controller.abort();
  }, []);

  if (session.status === "authenticated") {
    // A new session always receives a fresh financial/chat subtree, even when
    // React batches logout/login transitions before the next browser paint.
    return <React.Fragment key={session.generation}>{children}</React.Fragment>;
  }
  if (session.status === "anonymous") return <Login />;
  return (
    <main className="auth-shell"><section className="panel auth-panel">
      {session.status === "checking" ? <p role="status">Comprobando sesión…</p> : <>
        <p role="alert">No se pudo comprobar la sesión. Tus datos permanecen cerrados.</p>
        <button className="secondary" onClick={() => restoreSession()}>Volver a comprobar</button>
      </>}
    </section></main>
  );
}
