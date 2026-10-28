// No browser/backend services: mocked fetch and real React server rendering.
import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { createRequire } from "node:module";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { transformSync } from "esbuild";

const require = createRequire(import.meta.url);
const root = path.resolve("src");
const csrf = "a".repeat(64);
const data = { user: { id: 1, username: "fictitious" }, csrf_token: csrf, expires_at: "2030-01-01T00:00:00Z" };
const reply = (status, body = {}) => new Response(JSON.stringify(body), { status });

function fixture() {
  const modules = new Map();
  const calls = [];
  let fetchResult = () => reply(200, data);
  function load(filename) {
    filename = path.resolve(root, filename);
    if (modules.has(filename)) return modules.get(filename).exports;
    const module = { exports: {} };
    modules.set(filename, module);
    const code = transformSync(fs.readFileSync(filename, "utf8"), {
      loader: filename.endsWith(".jsx") ? "jsx" : "js", format: "cjs",
    }).code;
    const context = { module, exports: module.exports, console, Date, AbortController,
      setTimeout, clearTimeout,
      fetch: async (...args) => { calls.push(args); return fetchResult(...args); },
      require: (specifier) => specifier.startsWith(".")
        ? load(path.resolve(path.dirname(filename), specifier)) : require(specifier),
    };
    for (const name of ["localStorage", "sessionStorage"]) {
      Object.defineProperty(context, name, { get() { throw Error("Storage forbidden"); } });
    }
    vm.runInNewContext(code, context, { filename });
    return module.exports;
  }
  const store = load("auth/sessionStore.js");
  const auth = load("api/auth.js");
  return { load, store, auth, calls,
    fetch: (callback) => { fetchResult = callback; },
    authenticate: () => store.acceptSession(data, store.getSession().generation),
    render: () => renderToStaticMarkup(React.createElement(load("App.jsx").default)),
  };
}

test("initial and unavailable states never render financial screens or chat", () => {
  const f = fixture();
  assert.match(f.render(), /Comprobando sesión/);
  assert.doesNotMatch(f.render(), /Resumen financiero|Chat financiero/);
  f.store.sessionUnavailable(f.store.getSession().generation);
  assert.doesNotMatch(f.render(), /Resumen financiero|Chat financiero/);
  assert.equal(f.calls.length, 0);
});

test("401 restore shows login without sending financial requests", async () => {
  const f = fixture();
  f.fetch(() => reply(401));
  await f.auth.restoreSession();
  assert.equal(f.store.getSession().status, "anonymous");
  assert.match(f.render(), /Iniciar sesión/);
  assert.match(f.render(), /type="password"/);
  assert.doesNotMatch(f.render(), /Resumen financiero|Chat financiero/);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0][0], "http://127.0.0.1:8000/auth/session");
  assert.equal(f.calls[0][1].credentials, "include");
});

test("valid login sends exact auth payload, cookies and public CSRF marker", async () => {
  const f = fixture();
  f.store.clearSession();
  await f.auth.login("fictitious", " Fictitious password ");
  const [url, options] = f.calls[0];
  assert.equal(url, "http://127.0.0.1:8000/auth/login");
  assert.equal(options.method, "POST");
  assert.equal(options.credentials, "include");
  assert.equal(options.headers["X-CSRF-Token"], "login");
  assert.equal(options.headers.Origin, undefined);
  assert.equal(options.body, JSON.stringify({ username: "fictitious", password: " Fictitious password " }));
  assert.equal(f.store.getSession().status, "authenticated");
  assert.equal(JSON.stringify(f.store.getSession()).includes(csrf), false);
  assert.equal(JSON.stringify(f.store.getSession()).includes("password"), false);
  assert.match(f.render(), /Resumen financiero/);
  assert.match(f.render(), /Chat financiero/);
});

test("invalid login never accepts session or echoes the submitted password", async () => {
  const f = fixture();
  f.store.clearSession();
  f.fetch(() => reply(401, { detail: "Fictitious password" }));
  await assert.rejects(f.auth.login("fictitious", "Fictitious password"), /Usuario o contraseña incorrectos/);
  assert.equal(f.store.getSession().status, "anonymous");
  assert.equal(f.store.getCsrfToken(), null);
  assert.equal(f.calls.length, 1);
});

test("reload restores identity and in-memory CSRF using cookies", async () => {
  const f = fixture();
  await f.auth.restoreSession();
  assert.equal(f.store.getSession().status, "authenticated");
  assert.equal(f.store.getCsrfToken(), csrf);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0][1].headers["X-CSRF-Token"], undefined);
});

test("all 21 financial/chat requests preserve URLs, methods and bodies", async () => {
  const f = fixture();
  f.authenticate();
  const api = f.load("api/resources.js");
  const payload = { amount: "10.25", date: "2026-10-27", currency: "PEN" };
  const cases = [
    ["getSummary", "summary"], ["getMovements", "movements"],
    ["getBudgets", "budgets"], ["getCategories", "categories"],
    ["getReimbursements", "reimbursements"], ["getRecurringPayments", "recurring-payments"],
    ["getSavingsGoals", "savings-goals"], ["getNotifications", "notifications"],
    ["createMovement", "movements", [payload], payload],
    ["createExchange", "exchanges", [payload], payload],
    ["createBudget", "budgets", [payload], payload],
    ["createReimbursementRequest", "reimbursements", [payload], payload],
    ["completeReimbursementRequest", "reimbursements/7/complete", [7, payload], payload],
    ["createRecurringPaymentRequest", "recurring-payments", [payload], payload],
    ["payRecurringPaymentRequest", "recurring-payments/7/pay", [7, payload], payload],
    ["createSavingsGoalRequest", "savings-goals", [payload], payload],
    ["addSavingsContributionRequest", "savings-goals/7/contributions", [7, payload], payload],
    ["cancelSavingsGoalRequest", "savings-goals/7/cancel", [7]],
    ["useSavingsGoalRequest", "savings-goals/7/use", [7]],
    ["createCategoryRequest", "categories", [payload], payload],
  ];
  for (const [name, resource, args, body] of cases) {
    await api[name](...(args || []));
    const [url, options] = f.calls.at(-1);
    assert.equal(url, `http://127.0.0.1:8000/${resource}`);
    assert.equal(options.method || "GET", args ? "POST" : "GET");
    assert.equal(options.body, body ? JSON.stringify(body) : undefined);
    assert.equal(options.credentials, "include");
    assert.equal(options.headers["X-CSRF-Token"], args ? csrf : undefined);
    assert.equal(options.headers.Origin, undefined);
  }
  const controller = new AbortController();
  await f.load("api/chat.js").requestFinancialChat("Pregunta ficticia", controller.signal);
  const [url, options] = f.calls.at(-1);
  assert.equal(url, "http://127.0.0.1:8000/api/chat/tools");
  assert.equal(options.body, JSON.stringify({ message: "Pregunta ficticia" }));
  assert.equal(options.method, "POST");
  assert.equal(options.credentials, "include");
  assert.equal(options.headers["X-CSRF-Token"], csrf);
  assert.equal(options.signal, controller.signal);
  assert.equal(f.calls.length, 21);
});

test("a financial 401 clears identity/CSRF and removes financial/chat subtree", async () => {
  const f = fixture();
  f.authenticate();
  assert.match(f.render(), /Chat financiero/);
  f.fetch(() => reply(401));
  await assert.rejects(f.load("api/resources.js").getSummary(), /sesión finalizó/);
  assert.equal(f.store.getSession().status, "anonymous");
  assert.equal(f.store.getSession().user, null);
  assert.equal(f.store.getCsrfToken(), null);
  assert.doesNotMatch(f.render(), /Resumen financiero|Chat financiero/);
  await assert.rejects(f.load("api/resources.js").createBudget({}), /sesión finalizó/);
  assert.equal(f.calls.length, 1);
});

test("chat 401 also removes the authenticated subtree", async () => {
  const f = fixture();
  f.authenticate();
  f.fetch(() => reply(401));
  await assert.rejects(f.load("api/chat.js").requestFinancialChat("Ficticio"), /sesión finalizó/);
  assert.doesNotMatch(f.render(), /Chat financiero/);
});

test("CSRF 403 never retries a financial write or chat", async () => {
  const f = fixture();
  f.authenticate();
  f.fetch(() => reply(403));
  await assert.rejects(f.load("api/resources.js").createMovement({ amount: "1.00" }), /No se reintentó/);
  assert.equal(f.calls.length, 1);
  await assert.rejects(f.load("api/chat.js").requestFinancialChat("Ficticio"), /No se reintentó/);
  assert.equal(f.calls.length, 2);
  assert.equal(f.store.getSession().status, "authenticated");
});

test("logout calls backend once with cookie/CSRF, then removes chat and financial state", async () => {
  const f = fixture();
  f.authenticate();
  const oldGeneration = f.store.getSession().generation;
  f.fetch(() => reply(200, { status: "ok" }));
  await f.auth.logout();
  const [url, options] = f.calls[0];
  assert.equal(url, "http://127.0.0.1:8000/auth/logout");
  assert.equal(options.method, "POST");
  assert.equal(options.credentials, "include");
  assert.equal(options.headers["X-CSRF-Token"], csrf);
  assert.equal(f.store.getCsrfToken(), null);
  assert.doesNotMatch(f.render(), /Resumen financiero|Chat financiero/);
  f.authenticate();
  assert.ok(f.store.getSession().generation > oldGeneration);
});

test("failed logout does not claim backend revocation or silently retry", async () => {
  const f = fixture();
  f.authenticate();
  f.fetch(() => { throw Error("Network unavailable"); });
  await assert.rejects(f.auth.logout(), /No se pudo confirmar/);
  assert.equal(f.store.getSession().status, "authenticated");
  assert.equal(f.calls.length, 1);
});

test("late financial responses cannot cross session generations", async () => {
  const f = fixture();
  f.authenticate();
  let finish;
  f.fetch(() => new Promise((resolve) => { finish = resolve; }));
  const pending = f.load("api/resources.js").getSummary();
  f.store.clearSession();
  f.authenticate();
  finish(reply(401));
  await assert.rejects(pending, /sesión finalizó/);
  assert.equal(f.store.getSession().status, "authenticated");
});

test("late restore cannot resurrect a cleared session; bad responses fail closed", async () => {
  const f = fixture();
  let finish;
  f.fetch(() => new Promise((resolve) => { finish = resolve; }));
  const pending = f.auth.restoreSession();
  f.store.clearSession();
  finish(reply(200, data));
  await pending;
  assert.equal(f.store.getSession().status, "anonymous");
  f.fetch(() => reply(200, { user: { id: 1 }, csrf_token: "invalid" }));
  await f.auth.restoreSession();
  assert.equal(f.store.getSession().status, "unavailable");
  assert.doesNotMatch(f.render(), /Resumen financiero|Chat financiero/);
});
