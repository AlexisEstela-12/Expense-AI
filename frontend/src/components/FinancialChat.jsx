import React, { useEffect, useRef, useState } from "react";
import { Send, MessageSquare } from "lucide-react";
import { requestFinancialChat } from "../api/chat.js";

const SUGGESTIONS = [
  "¿Cuánto dinero tengo disponible en soles y dólares?",
  "¿Cuánto gasté este mes en soles y dólares?",
  "¿Cuánto gasté el mes pasado?",
  "¿En qué categoría gasté más este mes?",
  "¿Cuáles son mis tres principales categorías de gastos?",
  "¿Cuánto gasté en alimentación este mes?",
  "¿Cómo van mis presupuestos este mes?",
  "¿Qué presupuestos excedí este mes?",
  "¿Cuánto queda de mi presupuesto de Alimentación en soles?",
];
const BALANCE_ROWS = [
  ["balances", "Total"],
  ["reserved", "Reservado"],
  ["spendable", "Disponible"],
];

const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const isAmount = (value) => typeof value === "string" && /^-?\d+\.\d{2}$/.test(value);

function hasCurrencies(group) {
  return isObject(group) && Object.keys(group).length > 0 &&
    Object.entries(group).every(([currency, value]) =>
      ["PEN", "USD"].includes(currency) && isAmount(value));
}

function hasBalances(data) {
  if (!isObject(data) || !hasCurrencies(data.balances)) return false;
  const currencies = Object.keys(data.balances);
  return BALANCE_ROWS.every(([key]) => hasCurrencies(data[key]) &&
    Object.keys(data[key]).length === currencies.length &&
    currencies.every((currency) => isAmount(data[key][currency])));
}

function utcDate(value) {
  if (typeof value !== "string" || !/^(?!0000)\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T00:00:00.000Z`);
  return !isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value ? date : null;
}

function inclusiveEndDate(exclusive) {
  const date = utcDate(exclusive);
  if (!date) return null;
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toISOString().slice(0, 10);
}

function hasSpending(data) {
  if (!isObject(data) || !hasCurrencies(data.totals) ||
      !["PEN", "USD", "BOTH"].includes(data.currency) ||
      data.basis !== "gross_expenses_excluding_exchanges" ||
      !isObject(data.period) || data.period.timezone !== "America/Lima") return false;
  const currencies = data.currency === "BOTH" ? ["PEN", "USD"] : [data.currency];
  if (Object.keys(data.totals).length !== currencies.length ||
      !currencies.every((currency) => isAmount(data.totals[currency]))) return false;
  const start = utcDate(data.period.start_date);
  const end = utcDate(data.period.end_date_exclusive);
  const asOf = utcDate(data.period.as_of);
  if (!start || !end || !asOf) return false;
  const tomorrow = new Date(asOf.getTime());
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  return start < end && start <= asOf && end <= tomorrow;
}

function hasCategorySpending(data) {
  if (!isObject(data) || !["PEN", "USD", "BOTH"].includes(data.currency) ||
      data.basis !== "gross_expenses_excluding_exchanges" ||
      !Number.isInteger(data.limit) || data.limit < 1 || data.limit > 20 ||
      !["ok", "category_no_spending", "category_not_found", "ambiguous_category"].includes(data.status) ||
      !(data.category === null || (typeof data.category === "string" && data.category.trim())) ||
      !isObject(data.groups) || !isObject(data.period) || data.period.timezone !== "America/Lima") return false;
  const start = utcDate(data.period.start_date);
  const end = utcDate(data.period.end_date_exclusive);
  const asOf = utcDate(data.period.as_of);
  if (!start || !end || !asOf) return false;
  const tomorrow = new Date(asOf.getTime());
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  if (start >= end || start > asOf || end > tomorrow) return false;

  const unresolved = ["category_not_found", "ambiguous_category"].includes(data.status);
  if (unresolved) return data.category !== null && Object.keys(data.groups).length === 0;
  if (data.status === "category_no_spending" && data.category === null) return false;
  const currencies = data.currency === "BOTH" ? ["PEN", "USD"] : [data.currency];
  if (Object.keys(data.groups).length !== currencies.length ||
      !currencies.every((currency) => Object.hasOwn(data.groups, currency))) return false;
  return currencies.every((currency) => {
    const group = data.groups[currency];
    if (!isObject(group) || !Array.isArray(group.categories) ||
        group.categories.length > data.limit || typeof group.has_more !== "boolean") return false;
    if (data.category !== null && (group.categories.length > 1 || group.has_more)) return false;
    if (data.status === "category_no_spending" && group.categories.length) return false;
    return group.categories.every((entry) => isObject(entry) &&
      typeof entry.category === "string" && !!entry.category.trim() && isAmount(entry.amount));
  });
}

function hasBudgetStatus(data) {
  if (!isObject(data) || !["PEN", "USD", "BOTH"].includes(data.currency) ||
      data.basis !== "gross_expenses_excluding_exchanges" ||
      !["ok", "no_budget"].includes(data.status) ||
      !(data.category === null || (typeof data.category === "string" &&
        !!data.category.trim() && data.category.length <= 80)) ||
      !isObject(data.groups) || !isObject(data.period) ||
      data.period.timezone !== "America/Lima") return false;
  const start = utcDate(data.period.start_date);
  const end = utcDate(data.period.end_date_exclusive);
  const asOf = utcDate(data.period.as_of);
  if (!start || !end || !asOf) return false;
  const tomorrow = new Date(asOf.getTime());
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  if (start >= end || start > asOf || end > tomorrow) return false;
  const currencies = data.currency === "BOTH" ? ["PEN", "USD"] : [data.currency];
  if (Object.keys(data.groups).length !== currencies.length ||
      !currencies.every((currency) => Object.hasOwn(data.groups, currency))) return false;
  const ids = new Set();
  let count = 0;
  for (const currency of currencies) {
    const budgets = data.groups[currency];
    if (!Array.isArray(budgets)) return false;
    for (const budget of budgets) {
      if (!isObject(budget) || !Number.isSafeInteger(budget.id) || budget.id <= 0 ||
          ids.has(budget.id) || typeof budget.category !== "string" ||
          !budget.category.trim() ||
          !["within_budget", "exhausted", "exceeded"].includes(budget.status) ||
          !["limit", "spent", "remaining", "overrun"].every((key) => isAmount(budget[key]))) return false;
      const limit = visualCents(budget.limit);
      const spent = visualCents(budget.spent);
      const remaining = visualCents(budget.remaining);
      const overrun = visualCents(budget.overrun);
      if (limit <= 0n || spent < 0n || remaining < 0n || overrun < 0n ||
          remaining !== (spent < limit ? limit - spent : 0n) ||
          overrun !== (spent > limit ? spent - limit : 0n) ||
          budget.status !== (spent > limit ? "exceeded" : spent === limit ? "exhausted" : "within_budget")) return false;
      ids.add(budget.id);
      count += 1;
    }
  }
  return (data.status === "no_budget") === (count === 0);
}

// Convert only for chart widths; displayed amounts always remain the original strings.
function visualCents(amount) {
  const [whole, fraction] = amount.split(".");
  return BigInt(whole) * 100n + BigInt(whole.startsWith("-") ? `-${fraction}` : fraction);
}

function barWidth(amount, maximum) {
  const cents = visualCents(amount);
  if (maximum <= 0n || cents <= 0n) return "0%";
  const hundredths = cents * 10000n / maximum;
  return `${hundredths / 100n}.${String(hundredths % 100n).padStart(2, "0")}%`;
}

function budgetBarWidth(spent, limit) {
  const spentCents = visualCents(spent);
  const limitCents = visualCents(limit);
  const capped = spentCents > limitCents ? limitCents : spentCents;
  const hundredths = capped * 10000n / limitCents;
  return `${hundredths / 100n}.${String(hundredths % 100n).padStart(2, "0")}%`;
}

function validateToolResponse(data) {
  const fail = () => { throw new Error("La respuesta no tiene el formato esperado. No se mostrarán importes incompletos."); };
  if (!isObject(data) || typeof data.answer !== "string" || !data.answer.trim() ||
      !["llm", "fallback", "unsupported"].includes(data.explanation_source) ||
      ![null, "get_balances", "get_spending_summary", "get_spending_by_category", "get_budget_status"].includes(data.tool_name)) fail();
  if (data.explanation_source === "unsupported") {
    if (data.financial_data !== null || data.tool_name !== null) fail();
  } else if (data.financial_data === null) {
    if (data.explanation_source !== "fallback") fail();
  } else if (data.tool_name === "get_balances") {
    if (!hasBalances(data.financial_data)) fail();
  } else if (data.tool_name === "get_spending_summary") {
    if (!hasSpending(data.financial_data)) fail();
  } else if (data.tool_name === "get_spending_by_category") {
    if (!hasCategorySpending(data.financial_data)) fail();
  } else if (data.tool_name === "get_budget_status") {
    if (!hasBudgetStatus(data.financial_data)) fail();
  } else {
    fail();
  }
  return data;
}

const BUDGET_STATUS_LABELS = {
  within_budget: "Dentro del presupuesto",
  exhausted: "Presupuesto agotado",
  exceeded: "Presupuesto excedido",
};

function BudgetResult({ data }) {
  const currencies = data.currency === "BOTH" ? ["PEN", "USD"] : [data.currency];
  return (
    <div className="chat-result">
      <p className="chat-period">
        <strong>{data.category === null ? "Estado de presupuestos" : `Presupuesto de ${data.category}`}</strong>
        <span>Desde {data.period.start_date} hasta {inclusiveEndDate(data.period.end_date_exclusive)} · {data.period.timezone}</span>
      </p>
      {data.status === "no_budget" ? (
        <p className="chat-category-status">No hay presupuestos para el período y los filtros consultados.</p>
      ) : (
        <div className="chat-balances" aria-label="Estado exacto de los presupuestos por moneda">
          {currencies.map((currency) => (
            <section className="chat-balance-card chat-budget-card" key={currency}>
              <h3>{currency === "PEN" ? "Soles · PEN" : "Dólares · USD"}</h3>
              {data.groups[currency].length ? data.groups[currency].map((budget) => (
                <article className="chat-budget-item" key={budget.id}>
                  <div className="chat-budget-heading">
                    <strong>{budget.category}</strong>
                    <small>Presupuesto #{budget.id}</small>
                  </div>
                  <dl>
                    <div><dt>Asignado</dt><dd>{currency} {budget.limit}</dd></div>
                    <div><dt>Ejecutado</dt><dd>{currency} {budget.spent}</dd></div>
                    <div><dt>Disponible</dt><dd>{currency} {budget.remaining}</dd></div>
                    {budget.status === "exceeded" &&
                      <div><dt>Exceso</dt><dd>{currency} {budget.overrun}</dd></div>}
                  </dl>
                  <div className={`chat-budget-track chat-budget-${budget.status}`} aria-hidden="true">
                    <span style={{ width: budgetBarWidth(budget.spent, budget.limit) }} />
                  </div>
                  <span className={`chat-budget-state chat-budget-state-${budget.status}`}>
                    {BUDGET_STATUS_LABELS[budget.status]}
                  </span>
                </article>
              )) : <p className="chat-category-empty">No hay presupuestos en esta moneda para el período consultado.</p>}
            </section>
          ))}
        </div>
      )}
      <p className="chat-label">El gasto ejecutado es bruto, excluye cambios de divisas y no descuenta reembolsos recibidos.</p>
    </div>
  );
}

function CategoryResult({ data }) {
  const unresolved = ["category_not_found", "ambiguous_category"].includes(data.status);
  const currencies = data.currency === "BOTH" ? ["PEN", "USD"] : [data.currency];
  return (
    <div className="chat-result">
      <p className="chat-period">
        <strong>{data.category === null ? "Gastos por categoría" : `Categoría consultada: ${data.category}`}</strong>
        <span>Desde {data.period.start_date} hasta {inclusiveEndDate(data.period.end_date_exclusive)} · {data.period.timezone}</span>
      </p>
      {unresolved ? (
        <p className="chat-category-status">{data.status === "category_not_found"
          ? "No se encontró esa categoría. Revisa el nombre e inténtalo de nuevo."
          : "El nombre coincide con varias categorías. Especifica la categoría con más detalle."}</p>
      ) : (
        <div className="chat-balances" aria-label="Gastos exactos por categoría y moneda">
          {currencies.map((currency) => {
            const group = data.groups[currency];
            const maximum = group.categories.reduce((max, entry) => {
              const cents = visualCents(entry.amount);
              return cents > max ? cents : max;
            }, 0n);
            return (
              <section className="chat-balance-card chat-category-card" key={currency}>
                <h3>{currency === "PEN" ? "Soles · PEN" : "Dólares · USD"}</h3>
                {group.categories.length ? (
                  <ol className="chat-category-list">
                    {group.categories.map((entry) => (
                      <li className="chat-category-item" key={entry.category}>
                        <div className="chat-category-heading">
                          <span>{entry.category}</span>
                          <strong>{currency} {entry.amount}</strong>
                        </div>
                        <div className="chat-category-track" aria-hidden="true">
                          <span className="chat-category-fill" style={{ width: barWidth(entry.amount, maximum) }} />
                        </div>
                      </li>
                    ))}
                  </ol>
                ) : <p className="chat-category-empty">{data.status === "category_no_spending"
                  ? "Categoría conocida, sin gastos en este período y moneda."
                  : "No se registraron gastos por categoría en este período y moneda."}</p>}
                {group.has_more && <p className="chat-category-more">Hay más categorías fuera de este resultado.</p>}
              </section>
            );
          })}
        </div>
      )}
      <p className="chat-label">Gastos brutos: excluyen cambios de divisas y no descuentan reembolsos recibidos.</p>
    </div>
  );
}

function FinancialResult({ toolName, financialData }) {
  if (!financialData) return null;
  if (toolName === "get_budget_status") return <BudgetResult data={financialData} />;
  if (toolName === "get_spending_by_category") return <CategoryResult data={financialData} />;
  const spending = toolName === "get_spending_summary";
  const currencies = Object.keys(spending ? financialData.totals : financialData.balances);
  return (
    <div className="chat-result">
      {spending && <p className="chat-period">
        <strong>Gastos del período</strong>
        <span>Desde {financialData.period.start_date} hasta {inclusiveEndDate(financialData.period.end_date_exclusive)} · {financialData.period.timezone}</span>
      </p>}
      <div className="chat-balances" aria-label={spending ? "Gastos exactos de esta consulta" : "Saldos exactos de esta consulta"}>
        {currencies.map((currency) => (
          <section className="chat-balance-card" key={currency}>
            <h3>{currency === "PEN" ? "Soles · PEN" : "Dólares · USD"}</h3>
            <dl>{(spending ? [["totals", "Gasto bruto"]] : BALANCE_ROWS).map(([key, label]) => (
              <div key={key} className={key === "spendable" ? "chat-spendable" : ""}>
                <dt>{label}</dt>
                <dd>{currency} {financialData[key][currency]}</dd>
              </div>
            ))}</dl>
          </section>
        ))}
      </div>
      {spending && <p className="chat-label">Gastos brutos: excluyen cambios de divisas y no descuentan reembolsos recibidos.</p>}
    </div>
  );
}

export default function FinancialChat({ api }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      pending.current?.abort();
    };
  }, []);

  async function submit(event) {
    event.preventDefault();
    const message = question.trim();
    if (pending.current) return;
    if (!message || question.length > 1000) {
      setError("Escribe una pregunta de hasta 1000 caracteres.");
      return;
    }

    const controller = new AbortController();
    pending.current = controller;
    setLoading(true);
    setError("");
    setMessages((current) => [...current, { role: "user", text: message }]);
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, 90000);

    try {
      const response = await requestFinancialChat(message, controller.signal, api);
      if (!response.ok) {
        throw new Error(
          response.status === 403
            ? "El chat solo está disponible desde los orígenes locales permitidos."
            : response.status === 422
              ? "La pregunta no es válida. Revisa el texto e inténtalo de nuevo."
              : "No se pudo realizar la consulta financiera. Inténtalo de nuevo más tarde.",
        );
      }
      const data = validateToolResponse(await response.json());
      if (!mounted.current) return;
      setMessages((current) => [...current, {
        role: "assistant",
        text: data.answer,
        source: data.explanation_source,
        toolName: data.tool_name,
        financialData: data.financial_data,
        diagnosticId: typeof data.diagnostic_id === "string" ? data.diagnostic_id : null,
      }]);
      setQuestion("");
    } catch (failure) {
      if (!mounted.current) return;
      setError(timedOut
        ? "La consulta tardó demasiado. Puedes volver a enviarla manualmente."
        : failure.name === "AbortError"
          ? "La consulta fue cancelada."
          : failure instanceof TypeError
            ? "No se pudo conectar con el backend local. Comprueba que esté disponible."
            : failure instanceof SyntaxError
              ? "El backend devolvió una respuesta que no se pudo interpretar."
              : failure.message);
    } finally {
      clearTimeout(timer);
      if (pending.current === controller) pending.current = null;
      if (mounted.current) setLoading(false);
    }
  }

  return (
    <section className="panel financial-chat" aria-label="Chat financiero">
      <div className="panel-title">
        <h2><MessageSquare size={19} /> Consulta de saldos y gastos</h2>
        <span>Solo lectura</span>
      </div>
      <p className="muted">Pregunta por tus saldos o los gastos de un mes. Cada consulta es independiente.</p>
      <div className="chat-history" role="log" aria-label="Historial de consultas" tabIndex={0} aria-live="polite" aria-relevant="additions">
        {!messages.length && <p className="empty">Escribe tu primera pregunta o utiliza la sugerencia.</p>}
        {messages.map((message, index) => (
          <article key={index} className={`chat-message chat-message-${message.role}`}>
            <strong>{message.role === "user" ? "Tú" : message.source === "fallback" ? "Explicación alternativa" : "Asistente IA"}</strong>
            <p className="chat-text">{message.text}</p>
            {message.source === "unsupported" && <span className="chat-label">Consulta no admitida o pendiente de aclaración. Consulta saldos o gastos de un mes por separado.</span>}
            {message.source === "fallback" && <span className="chat-label">
              {message.toolName === "get_budget_status" && message.financialData?.status === "no_budget"
                ? "La consulta no encontró presupuestos para el período y los filtros indicados."
                : message.financialData
                  ? "Los importes de la consulta están disponibles."
                  : "No se obtuvieron datos financieros para esta consulta."}
            </span>}
            <FinancialResult toolName={message.toolName} financialData={message.financialData} />
            {message.source === "fallback" && message.diagnosticId && (
              <small className="chat-reference">Referencia: {message.diagnosticId}</small>
            )}
          </article>
        ))}
      </div>
      {loading && <p className="muted" role="status">Consultando información financiera…</p>}
      {error && <div className="message error" role="alert">{error}</div>}
      <div className="chat-suggestions" aria-label="Preguntas sugeridas">
        {SUGGESTIONS.map((suggestion) => (
          <button key={suggestion} type="button" className="secondary chat-suggestion" disabled={loading} onClick={() => setQuestion(suggestion)}>
            {suggestion}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="chat-form" aria-busy={loading}>
        <label htmlFor="financial-chat-question">Tu pregunta</label>
        <textarea id="financial-chat-question" value={question} maxLength={1000} rows={3}
          disabled={loading} onChange={(event) => setQuestion(event.target.value)}
          placeholder="Pregunta por tus saldos o gastos…" aria-describedby="chat-character-count" required />
        <div className="chat-form-actions">
          <small id="chat-character-count" className="muted">{question.length}/1000 caracteres</small>
          <button type="submit" className="primary" disabled={loading || !question.trim()}>
            <Send size={17} /> {loading ? "Consultando…" : "Enviar"}
          </button>
        </div>
      </form>
    </section>
  );
}
