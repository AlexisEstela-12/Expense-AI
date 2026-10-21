import React, { useEffect, useMemo, useState } from "react";
import {
  LayoutDashboard,
  ArrowLeftRight,
  Wallet,
  Target,
  ReceiptText,
  BarChart3,
  Bell,
  Settings,
  Plus,
  Menu,
  X,
  Repeat2,
  MessageSquare,
} from "lucide-react";
import FinancialChat from "./components/FinancialChat.jsx";
import Notifications from "./components/Notifications.jsx";
import Reports from "./pages/Reports.jsx";
import SettingsPage from "./pages/Settings.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Movements from "./pages/Movements.jsx";
import Budgets from "./pages/Budgets.jsx";
import SavingsGoals from "./pages/SavingsGoals.jsx";
import RecurringPayments from "./pages/RecurringPayments.jsx";
import Reimbursements from "./pages/Reimbursements.jsx";
import Exchanges from "./pages/Exchanges.jsx";
const API = "http://127.0.0.1:8000",
  today = new Date().toLocaleDateString("en-CA"),
  monthNow = today.slice(0, 7);
const money = (n, c = "PEN") =>
  new Intl.NumberFormat("es-PE", {
    style: "currency",
    currency: c,
    minimumFractionDigits: 2,
  }).format(Number(n || 0));
const monthLabel = (m) =>
  new Date(`${m}-02T12:00:00`).toLocaleDateString("es-PE", {
    month: "long",
    year: "numeric",
  });
const colors = [
  "#1f5eac",
  "#3b91d1",
  "#43876d",
  "#d69a35",
  "#8a9bb1",
  "#d16a51",
  "#6973a5",
];
const menu = [
  ["Dashboard", LayoutDashboard],
  ["Movimientos", Wallet],
  ["Cambio de divisas", ArrowLeftRight],
  ["Presupuestos", Target],
  ["Metas de ahorro", Target],
  ["Reembolsos", ReceiptText],
  ["Pagos recurrentes", Repeat2],
  ["Reportes", BarChart3],
  ["Notificaciones", Bell],
  ["Asistente IA", MessageSquare],
];
function App() {
  const [page, setPage] = useState("Dashboard"),
    [mobile, setMobile] = useState(false),
    [month, setMonth] = useState(monthNow),
    [summary, setSummary] = useState({ balances: { PEN: 0, USD: 0 } }),
    [movements, setMovements] = useState([]),
    [budgets, setBudgets] = useState([]),
    [error, setError] = useState(""),
    [categories, setCategories] = useState([]),
    [reimbursementsData, setReimbursementsData] = useState([]),
    [recurringPayments, setRecurringPayments] = useState([]),
    [notifications, setNotifications] = useState([]),
    [savingsGoals, setSavingsGoals] = useState([]),
    [savingsGoalFormData, setSavingsGoalFormData] = useState({
      name: "",
      currency: "PEN",
      target_amount: "",
      target_date: "",
    }),
    [showNewCategory, setShowNewCategory] = useState(false),
    [newCategory, setNewCategory] = useState(""),
    [notice, setNotice] = useState("");
  const [form, setForm] = useState({
    date: today,
    kind: "income",
    currency: "PEN",
    amount: "",
    category: "Sueldo",
    description: "",
  });
  const [fx, setFx] = useState({
    date: today,
    from_currency: "USD",
    amount_out: "",
    amount_in: "",
  });
  const [budget, setBudget] = useState({
    month: monthNow,
    category: "Alimentación",
    currency: "PEN",
    limit_amount: "",
  });
  const [reimbursementForm, setReimbursementForm] = useState({
    date: today,
    currency: "PEN",
    amount: "",
    category: "Gastos laborales",
    description: "",
  });
  const [recurringForm, setRecurringForm] = useState({
    name: "",
    category: "Servicios",
    currency: "PEN",
    amount: "",
    frequency: "monthly",
    next_payment_date: today,
  });
  const load = async () => {
    try {
      const responses = await Promise.all(
        [
          "summary",
          "movements",
          "budgets",
          "categories",
          "reimbursements",
          "recurring-payments",
          "savings-goals",
          "notifications",
        ].map((endpoint) => fetch(`${API}/${endpoint}`)),
      );
      for (const r of responses)
        if (!r.ok) throw Error("No se pudieron cargar los datos");
      const [s, m, b, c, r, rp, sg, n] = await Promise.all(
        responses.map((r) => r.json()),
      );
      setSummary(s);
      setMovements(m);
      setBudgets(b);
      setCategories(c);
      setReimbursementsData(r);
      setRecurringPayments(rp);
      setSavingsGoals(sg);
      setNotifications(n);
      setError("");
    } catch (e) {
      console.error("Error en load():", e);
      setError(`Error al cargar datos: ${e.message}`);
    }
  };
  useEffect(() => {
    load();
  }, []);
  const send = async (path, payload, reset) => {
    setError("");
    setNotice("");
    try {
      const r = await fetch(`${API}/${path}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }),
        data = await r.json();
      if (!r.ok)
        throw Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail),
        );
      reset();
      await load();
      setNotice("Registro guardado correctamente");
    } catch (e) {
      setError(e.message);
    }
  };

  const createReimbursement = async () => {
    setError("");
    setNotice("");

    try {
      const response = await fetch(`${API}/reimbursements`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...reimbursementForm,
          amount: Number(reimbursementForm.amount),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail),
        );
      }

      setReimbursementForm({
        date: today,
        currency: "PEN",
        amount: "",
        category: "Gastos laborales",
        description: "",
      });

      await load();

      setNotice("Gasto reembolsable registrado correctamente.");
    } catch (e) {
      setError(e.message);
    }
  };

  const completeReimbursement = async (id) => {
    setError("");
    setNotice("");

    const reimbursementDate = window.prompt(
      "¿Qué fecha recibiste el reembolso? (AAAA-MM-DD)",
      today,
    );

    if (!reimbursementDate) {
      return;
    }

    try {
      const response = await fetch(`${API}/reimbursements/${id}/complete`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          date: reimbursementDate,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail),
        );
      }

      await load();

      setNotice(
        `Reembolso registrado correctamente con fecha ${reimbursementDate}.`,
      );
    } catch (e) {
      setError(e.message);
    }
  };

  const createRecurringPayment = async () => {
    setError("");
    setNotice("");

    try {
      const response = await fetch(`${API}/recurring-payments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...recurringForm,
          amount: Number(recurringForm.amount),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail),
        );
      }

      setRecurringForm({
        name: "",
        category: "Servicios",
        currency: "PEN",
        amount: "",
        frequency: "monthly",
        next_payment_date: today,
      });

      await load();

      setNotice("Pago recurrente registrado correctamente.");
    } catch (e) {
      setError(e.message);
    }
  };

  const payRecurringPayment = async (id) => {
    setError("");
    setNotice("");

    const paymentDate = window.prompt(
      "¿Qué fecha realizaste el pago? (AAAA-MM-DD)",
      today,
    );

    if (!paymentDate) {
      return;
    }

    try {
      const response = await fetch(`${API}/recurring-payments/${id}/pay`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          date: paymentDate,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail),
        );
      }

      await load();

      setNotice(
        `Pago registrado correctamente. Próximo vencimiento: ${data.next_payment_date}.`,
      );
    } catch (e) {
      setError(e.message);
    }
  };

  async function createSavingsGoal(e) {
    e.preventDefault();
    setError("");
    setNotice("");

    try {
      const response = await fetch(`${API}/savings-goals`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: savingsGoalFormData.name,
          currency: savingsGoalFormData.currency,
          target_amount: Number(savingsGoalFormData.target_amount),
          target_date: savingsGoalFormData.target_date || null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "No se pudo crear la meta de ahorro.");
      }

      setSavingsGoalFormData({
        name: "",
        currency: "PEN",
        target_amount: "",
        target_date: "",
      });

      setNotice("Meta de ahorro creada correctamente.");

      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addSavingsContribution(goal) {
    const amount = window.prompt(
      `¿Cuánto deseas aportar a "${goal.name}" en ${goal.currency}?`,
    );

    if (!amount) return;

    const numericAmount = Number(amount);

    if (!numericAmount || numericAmount <= 0) {
      setError("Ingresa un monto válido.");
      return;
    }

    const contributionDate = window.prompt(
      "Fecha del aporte (AAAA-MM-DD):",
      new Date().toISOString().slice(0, 10),
    );

    if (!contributionDate) return;

    setError("");
    setNotice("");

    try {
      const response = await fetch(
        `${API}/savings-goals/${goal.id}/contributions`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            date: contributionDate,
            amount: numericAmount,
          }),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "No se pudo registrar el aporte.");
      }

      setNotice(`Aporte registrado correctamente en "${goal.name}".`);

      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function cancelSavingsGoal(goal) {
    const confirmed = window.confirm(
      `¿Deseas cancelar la meta "${goal.name}"?\n\nEl dinero reservado volverá a estar disponible y no se registrará ningún gasto.`,
    );

    if (!confirmed) return;

    setError("");
    setNotice("");

    try {
      const response = await fetch(`${API}/savings-goals/${goal.id}/cancel`, {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "No se pudo cancelar la meta.");
      }

      setNotice(
        `Meta "${goal.name}" cancelada. ${goal.currency} ${Number(
          data.released_amount,
        ).toFixed(2)} volvió a estar disponible.`,
      );

      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function useSavingsGoal(goal) {
    const confirmed = window.confirm(
      `¿Deseas utilizar el ahorro de "${goal.name}"?\n\nSe registrará ${goal.currency} ${Number(
        goal.saved_amount,
      ).toFixed(2)} como gasto y la meta quedará cerrada.`,
    );

    if (!confirmed) return;

    setError("");
    setNotice("");

    try {
      const response = await fetch(`${API}/savings-goals/${goal.id}/use`, {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "No se pudo utilizar el ahorro.");
      }

      setNotice(
        `Ahorro de "${goal.name}" utilizado correctamente. Se registraron ${goal.currency} ${Number(
          data.used_amount,
        ).toFixed(2)} como gasto.`,
      );

      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  const inMonth = (m) => m.date?.startsWith(month),
    ordinary = (m) => m.category !== "Cambio de divisas";
  const expenses = movements.filter(
    (m) => inMonth(m) && m.kind === "expense" && ordinary(m),
  );
  const income = movements.filter(
    (m) => inMonth(m) && m.kind === "income" && ordinary(m),
  );
  const reimbursements = movements.filter(
    (m) => inMonth(m) && m.kind === "reimbursement",
  );
  const sum = (items, c) =>
    items
      .filter((m) => m.currency === c)
      .reduce((a, m) => a + Number(m.amount), 0);
  const expensePen = sum(expenses, "PEN"),
    expenseUsd = sum(expenses, "USD"),
    incomePen = sum(income, "PEN"),
    incomeUsd = sum(income, "USD");
  const categoryData = Object.values(
    expenses
      .filter((m) => m.currency === "PEN")
      .reduce((a, m) => {
        a[m.category] ??= { name: m.category, value: 0 };
        a[m.category].value += Number(m.amount);
        return a;
      }, {}),
  ).sort((a, b) => b.value - a.value);
  const monthly = useMemo(() => {
    const a = [];
    for (let i = 5; i >= 0; i--) {
      const d = new Date(
          Number(month.slice(0, 4)),
          Number(month.slice(5)) - 1 - i,
          1,
        ),
        key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      const group = movements.filter(
        (m) => m.date.startsWith(key) && ordinary(m),
      );
      a.push({
        name: d.toLocaleDateString("es-PE", { month: "short" }),
        Ingresos: sum(
          group.filter((m) => m.kind === "income"),
          "PEN",
        ),
        Gastos: sum(
          group.filter((m) => m.kind === "expense"),
          "PEN",
        ),
      });
    }
    return a;
  }, [movements, month]);
  const currentBudgets = budgets.filter((b) => b.month === month),
    alerts = currentBudgets
      .filter((b) => b.alert > 0)
      .sort((a, b) => b.percentage - a.percentage);

  const createNewCategory = async () => {
    const name = newCategory.trim();

    if (!name) {
      setError("Escribe un nombre para la categoría.");
      return;
    }

    setError("");
    setNotice("");

    try {
      const response = await fetch(`${API}/categories`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name,
          kind: form.kind,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "No se pudo crear la categoría.");
      }

      setCategories((current) => [...current, data]);

      setForm({
        ...form,
        category: data.name,
      });

      setNewCategory("");
      setShowNewCategory(false);
      setNotice(`Categoría "${data.name}" creada correctamente.`);
    } catch (e) {
      setError(e.message);
    }
  };

  const open = (p) => {
    setPage(p);
    setMobile(false);
    setError("");
    setNotice("");
  };
  const submitMovement = (e) => {
    e.preventDefault();
    send("movements", form, () =>
      setForm({ ...form, amount: "", description: "" }),
    );
  };
  const submitExchange = (e) => {
    e.preventDefault();
    send("exchanges", fx, () =>
      setFx({ ...fx, amount_out: "", amount_in: "" }),
    );
  };
  const submitBudget = (e) => {
    e.preventDefault();
    send("budgets", budget, () => setBudget({ ...budget, limit_amount: "" }));
  };
  const movementForm = (
    <form onSubmit={submitMovement} className="form-grid">
      <label>
        Fecha
        <input
          required
          type="date"
          value={form.date}
          onChange={(e) => setForm({ ...form, date: e.target.value })}
        />
      </label>
      <label>
        Tipo
        <select
          value={form.kind}
          onChange={(e) =>
            setForm({
              ...form,
              kind: e.target.value,
              category:
                e.target.value === "expense"
                  ? "Alimentación"
                  : e.target.value === "reimbursement"
                    ? "Reembolso laboral"
                    : "Sueldo",
            })
          }
        >
          <option value="income">Ingreso</option>
          <option value="expense">Gasto</option>
          <option value="reimbursement">Reembolso recibido</option>
        </select>
      </label>
      <label>
        Moneda
        <select
          value={form.currency}
          onChange={(e) => setForm({ ...form, currency: e.target.value })}
        >
          <option value="PEN">Soles (PEN)</option>
          <option value="USD">Dólares (USD)</option>
        </select>
      </label>
      <label>
        Monto
        <input
          required
          type="number"
          min="0.01"
          step="0.01"
          placeholder="0.00"
          value={form.amount}
          onChange={(e) => setForm({ ...form, amount: e.target.value })}
        />
      </label>
      <label>
        Categoría
        <select
          required
          value={form.category}
          onChange={(e) => setForm({ ...form, category: e.target.value })}
        >
          {categories
            .filter((c) => c.kind === form.kind)
            .map((c) => (
              <option key={c.id} value={c.name}>
                {c.name}
              </option>
            ))}
        </select>
      </label>
      <div className="category-action">
        {!showNewCategory ? (
          <button
            type="button"
            className="category-add"
            onClick={() => setShowNewCategory(true)}
          >
            <Plus size={15} />
            Nueva categoría
          </button>
        ) : (
          <div className="new-category-box">
            <input
              type="text"
              maxLength="80"
              placeholder="Nombre de la nueva categoría"
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
            />

            <button
              type="button"
              className="secondary"
              onClick={createNewCategory}
            >
              Agregar
            </button>

            <button
              type="button"
              className="category-cancel"
              onClick={() => {
                setShowNewCategory(false);
                setNewCategory("");
              }}
            >
              Cancelar
            </button>
          </div>
        )}
      </div>
      <label>
        Descripción (opcional)
        <input
          maxLength="255"
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
      </label>
      <button className="primary" type="submit">
        Guardar movimiento
      </button>
    </form>
  );
  const budgetForm = (
    <form onSubmit={submitBudget} className="form-grid">
      <label>
        Mes
        <input
          required
          type="month"
          value={budget.month}
          onChange={(e) => setBudget({ ...budget, month: e.target.value })}
        />
      </label>
      <label>
        Categoría
        <select
          required
          value={budget.category}
          onChange={(e) =>
            setBudget({
              ...budget,
              category: e.target.value,
            })
          }
        >
          {categories
            .filter((c) => c.kind === "expense")
            .map((c) => (
              <option key={c.id} value={c.name}>
                {c.name}
              </option>
            ))}
        </select>
      </label>
      <label>
        Moneda
        <select
          value={budget.currency}
          onChange={(e) => setBudget({ ...budget, currency: e.target.value })}
        >
          <option value="PEN">Soles</option>
          <option value="USD">Dólares</option>
        </select>
      </label>
      <label>
        Límite
        <input
          required
          type="number"
          min="0.01"
          step="0.01"
          value={budget.limit_amount}
          onChange={(e) =>
            setBudget({ ...budget, limit_amount: e.target.value })
          }
        />
      </label>
      <button className="primary" type="submit">
        Crear presupuesto
      </button>
    </form>
  );
  const savingsGoalForm = (
    <form className="form-grid" onSubmit={createSavingsGoal}>
      <label>
        Nombre de la meta
        <input
          type="text"
          placeholder="Ej. Viaje, Laptop, Fondo de emergencia"
          value={savingsGoalFormData.name}
          onChange={(e) =>
            setSavingsGoalFormData({
              ...savingsGoalFormData,
              name: e.target.value,
            })
          }
          required
        />
      </label>

      <label>
        Moneda
        <select
          value={savingsGoalFormData.currency}
          onChange={(e) =>
            setSavingsGoalFormData({
              ...savingsGoalFormData,
              currency: e.target.value,
            })
          }
        >
          <option value="PEN">PEN - Soles</option>
          <option value="USD">USD - Dólares</option>
        </select>
      </label>

      <label>
        Monto objetivo
        <input
          type="number"
          min="0.01"
          step="0.01"
          placeholder="0.00"
          value={savingsGoalFormData.target_amount}
          onChange={(e) =>
            setSavingsGoalFormData({
              ...savingsGoalFormData,
              target_amount: e.target.value,
            })
          }
          required
        />
      </label>

      <label>
        Fecha objetivo
        <input
          type="date"
          value={savingsGoalFormData.target_date}
          onChange={(e) =>
            setSavingsGoalFormData({
              ...savingsGoalFormData,
              target_date: e.target.value,
            })
          }
        />
      </label>

      <button className="primary" type="submit">
        Crear meta
      </button>
    </form>
  );
  const budgetList = (
    <div className="budget-list">
      {currentBudgets.length ? (
        currentBudgets.map((b) => (
          <div className="budget-line" key={b.id}>
            <div className="budget-top">
              <strong>
                {b.category} <small>{b.currency}</small>
              </strong>
              <span>
                {money(b.spent, b.currency)} / {money(b.limit, b.currency)}{" "}
                <b
                  className={
                    b.percentage >= 90
                      ? "danger"
                      : b.percentage >= 75
                        ? "warning"
                        : "ok"
                  }
                >
                  {Math.round(b.percentage)}%
                </b>
              </span>
            </div>
            <div className="track">
              <div
                className={
                  b.percentage >= 90
                    ? "red"
                    : b.percentage >= 75
                      ? "amber"
                      : "green"
                }
                style={{ width: `${Math.min(100, b.percentage)}%` }}
              />
            </div>
          </div>
        ))
      ) : (
        <p className="empty">
          Aún no hay presupuestos para {monthLabel(month)}.
        </p>
      )}
    </div>
  );
  const table = (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Tipo</th>
            <th>Categoría</th>
            <th>Descripción</th>
            <th>Moneda</th>
            <th>Monto</th>
          </tr>
        </thead>
        <tbody>
          {movements
            .filter((m) => (page === "Dashboard" ? inMonth(m) : true))
            .slice(0, page === "Dashboard" ? 10 : 100)
            .map((m) => (
              <tr key={m.id}>
                <td>{m.date}</td>
                <td>
                  <span className={`type ${m.kind}`}>
                    {m.category === "Cambio de divisas"
                      ? "↔ Cambio"
                      : m.kind === "income"
                        ? "↓ Ingreso"
                        : m.kind === "expense"
                          ? "↑ Gasto"
                          : "↓ Reembolso"}
                  </span>
                </td>
                <td>{m.category}</td>
                <td>{m.description || "—"}</td>
                <td>{m.currency}</td>
                <td className={m.kind === "expense" ? "negative" : "positive"}>
                  {m.kind === "expense" ? "− " : "+ "}
                  {money(m.amount, m.currency)}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
      {!movements.length && (
        <p className="empty">Registra tu primer movimiento para comenzar.</p>
      )}
    </div>
  );
  return (
    <div className="app">
      <aside className={`sidebar ${mobile ? "shown" : ""}`}>
        <div className="brand">
          <Wallet size={27} />
          <strong>Expense AI</strong>
          <button
            className="mobile-close"
            onClick={() => setMobile(false)}
            aria-label="Cerrar menú"
          >
            <X />
          </button>
        </div>
        <nav>
          {menu.map(([label, Icon]) => (
            <button
              key={label}
              onClick={() => open(label)}
              className={page === label ? "active" : ""}
            >
              <Icon size={19} />
              {label}
              {label === "Notificaciones" && alerts.length > 0 && (
                <span className="count">{alerts.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="side-bottom">
          <button onClick={() => open("Configuración")}>
            <Settings size={19} /> Configuración
          </button>
          <small>Finanzas personales · Local</small>
        </div>
      </aside>
      <div className="content">
        <div className="topbar">
          <button
            className="menu-toggle"
            onClick={() => setMobile(true)}
            aria-label="Abrir menú"
          >
            <Menu />
          </button>
          <div className="top-spacer" />
          {page !== "Asistente IA" && <label className="month-select">
            Mes{" "}
            <input
              type="month"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
            />
          </label>}
          <div className="avatar">AI</div>
        </div>
        <main>
          <div className="heading">
            <div>
              <h1>{page === "Dashboard" ? "Resumen financiero" : page}</h1>
              <p>
                {page === "Dashboard"
                  ? "Tu dinero, claro y bajo control"
                  : page === "Asistente IA"
                    ? "Consulta tus saldos y gastos"
                    : monthLabel(month)}
              </p>
            </div>
            {page === "Dashboard" && (
              <button
                className="primary compact"
                onClick={() => open("Movimientos")}
              >
                <Plus size={17} /> Nuevo movimiento
              </button>
            )}
          </div>
          {error && (
            <div className="message error" role="alert">
              {error}
            </div>
          )}
          {notice && (
            <div className="message success" role="status">
              {notice}
            </div>
          )}
          {page === "Dashboard" && (
            <Dashboard
              summary={summary}
              incomePen={incomePen}
              incomeUsd={incomeUsd}
              expensePen={expensePen}
              expenseUsd={expenseUsd}
              categoryData={categoryData}
              monthly={monthly}
              colors={colors}
              month={month}
              money={money}
              monthLabel={monthLabel}
              budgetList={budgetList}
              alerts={alerts}
              table={table}
              open={open}
            />
          )}
          {page === "Movimientos" && (
            <Movements
              movementForm={movementForm}
              summary={summary}
              money={money}
              incomePen={incomePen}
              incomeUsd={incomeUsd}
              expensePen={expensePen}
              expenseUsd={expenseUsd}
              sum={sum}
              reimbursements={reimbursements}
              table={table}
            />
          )}
          {page === "Cambio de divisas" && (
            <Exchanges
              fx={fx}
              setFx={setFx}
              submitExchange={submitExchange}
              summary={summary}
              movements={movements}
              money={money}
            />
          )}
          {page === "Presupuestos" && (
            <Budgets
              budgetForm={budgetForm}
              budgetList={budgetList}
              month={month}
              monthLabel={monthLabel}
            />
          )}

          {page === "Metas de ahorro" && (
            <SavingsGoals
              savingsGoalForm={savingsGoalForm}
              savingsGoals={savingsGoals}
              money={money}
              addSavingsContribution={addSavingsContribution}
              useSavingsGoal={useSavingsGoal}
              cancelSavingsGoal={cancelSavingsGoal}
            />
          )}

          {page === "Reembolsos" && (
            <Reimbursements
              reimbursementForm={reimbursementForm}
              setReimbursementForm={setReimbursementForm}
              reimbursementsData={reimbursementsData}
              reimbursements={reimbursements}
              createReimbursement={createReimbursement}
              completeReimbursement={completeReimbursement}
              money={money}
              sum={sum}
            />
          )}

          {page === "Pagos recurrentes" && (
            <RecurringPayments
              recurringForm={recurringForm}
              setRecurringForm={setRecurringForm}
              categories={categories}
              recurringPayments={recurringPayments}
              createRecurringPayment={createRecurringPayment}
              payRecurringPayment={payRecurringPayment}
              money={money}
            />
          )}

          {page === "Reportes" && (
            <Reports monthly={monthly} categoryData={categoryData} colors={colors} money={money} />
          )}
          {page === "Notificaciones" && (
            <Notifications notifications={notifications} />
          )}
          <div hidden={page !== "Asistente IA"}>
            <FinancialChat api={API} />
          </div>
          {page === "Configuración" && (
            <SettingsPage onRefresh={load} />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
