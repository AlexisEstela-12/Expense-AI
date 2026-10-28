import React, { useState } from "react";
import { Wallet } from "lucide-react";
import { login } from "../api/auth.js";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError("");
    try {
      await login(username, password);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setPassword("");
      setPending(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="panel auth-panel" aria-labelledby="login-title">
        <div className="auth-brand"><Wallet size={27} /><strong>Expense AI</strong></div>
        <h1 id="login-title">Iniciar sesión</h1>
        <p className="muted">Accede a tus finanzas personales.</p>
        {error && <div className="message error" role="alert">{error}</div>}
        <form className="form-grid auth-form" onSubmit={submit} aria-busy={pending}>
          <label htmlFor="login-user">Usuario
            <input id="login-user" name="username" autoComplete="username" maxLength={128}
              value={username} onChange={(event) => setUsername(event.target.value)} required disabled={pending} />
          </label>
          <label htmlFor="login-password">Contraseña
            <input id="login-password" name="password" type="password" autoComplete="current-password" maxLength={1024}
              value={password} onChange={(event) => setPassword(event.target.value)} required disabled={pending} />
          </label>
          <button className="primary" type="submit" disabled={pending}>{pending ? "Iniciando sesión…" : "Entrar"}</button>
        </form>
      </section>
    </main>
  );
}
