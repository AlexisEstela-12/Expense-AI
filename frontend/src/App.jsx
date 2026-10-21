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
import BudgetList from "./components/BudgetList.jsx";
import MovementsTable from "./components/MovementsTable.jsx";
import Reports from "./pages/Reports.jsx";
import SettingsPage from "./pages/Settings.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Movements from "./pages/Movements.jsx";
import Budgets from "./pages/Budgets.jsx";
import SavingsGoals from "./pages/SavingsGoals.jsx";
import RecurringPayments from "./pages/RecurringPayments.jsx";
import Reimbursements from "./pages/Reimbursements.jsx";
import Exchanges from "./pages/Exchanges.jsx";
import {
  ordinary,
  sum,
  filterMonthlyMovements,
  movementTotals,
  calculateCategoryData,
  calculateMonthly,
} from "./utils/financialView.js";
import { API } from "./api/client.js";
import { createMovement, createExchange, createBudget } from "./api/resources.js";
import {
  getSummary,
  getMovements,
  getBudgets,
  getCategories,
  getReimbursements,
  getRecurringPayments,
  getSavingsGoals,
  getNotifications,
} from "./api/resources.js";
import {
  createReimbursementRequest,
  completeReimbursementRequest,
  createRecurringPaymentRequest,
  payRecurringPaymentRequest,
} from "./api/resources.js";
import {
  createSavingsGoalRequest,
  addSavingsContributionRequest,
  cancelSavingsGoalRequest,
  useSavingsGoalRequest,
  createCategoryRequest,
} from "./api/resources.js";
import { money, monthLabel } from "./utils/formatters.js";
const today = new Date().toLocaleDateString("en-CA"),
  monthNow = today.slice(0, 7);
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
          getSummary(),
          getMovements(),
          getBudgets(),
          getCategories(),
          getReimbursements(),
          getRecurringPayments(),
          getSavingsGoals(),
          getNotifications(),
        ],
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
  const send = async (request, payload, reset) => {
    setError("");
    setNotice("");
    try {
      const r = await request(payload),
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
      const response = await createReimbursementRequest({
        ...reimbursementForm,
        amount: Number(reimbursementForm.amount),
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
      const response = await completeReimbursementRequest(id, {
        date: reimbursementDate,
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
      const response = await createRecurringPaymentRequest({
        ...recurringForm,
        amount: Number(recurringForm.amount),
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
      const response = await payRecurringPaymentRequest(id, {
        date: paymentDate,
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
      const response = await createSavingsGoalRequest({
        name: savingsGoalFormData.name,
        currency: savingsGoalFormData.currency,
        target_amount: Number(savingsGoalFormData.target_amount),
        target_date: savingsGoalFormData.target_date || null,
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
      const response = await addSavingsContributionRequest(goal.id, {
        date: contributionDate,
        amount: numericAmount,
      });

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
      const response = await cancelSavingsGoalRequest(goal.id);

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
      const response = await useSavingsGoalRequest(goal.id);

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

  const inMonth = (m) => m.date?.startsWith(month);
  const { expenses, income, reimbursements } = filterMonthlyMovements(
    movements,
    month,
  );
  const { expensePen, expenseUsd, incomePen, incomeUsd } = movementTotals(
    expenses,
    income,
  );
  const categoryData = calculateCategoryData(expenses);
  const monthly = useMemo(() => calculateMonthly(movements, month), [movements, month]);
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
      const response = await createCategoryRequest({
        name: name,
        kind: form.kind,
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
    send(createMovement, form, () =>
      setForm({ ...form, amount: "", description: "" }),
    );
  };
  const submitExchange = (e) => {
    e.preventDefault();
    send(createExchange, fx, () =>
      setFx({ ...fx, amount_out: "", amount_in: "" }),
    );
  };
  const submitBudget = (e) => {
    e.preventDefault();
    send(createBudget, budget, () => setBudget({ ...budget, limit_amount: "" }));
  };
  const budgetList = (
    <BudgetList
      currentBudgets={currentBudgets}
      money={money}
      month={month}
      monthLabel={monthLabel}
    />
  );
  const visibleMovements = movements
    .filter((m) => (page === "Dashboard" ? inMonth(m) : true))
    .slice(0, page === "Dashboard" ? 10 : 100);
  const table = (
    <MovementsTable
      visibleMovements={visibleMovements}
      hasMovements={movements.length > 0}
      money={money}
    />
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
              form={form}
              setForm={setForm}
              categories={categories}
              showNewCategory={showNewCategory}
              setShowNewCategory={setShowNewCategory}
              newCategory={newCategory}
              setNewCategory={setNewCategory}
              createNewCategory={createNewCategory}
              submitMovement={submitMovement}
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
              budget={budget}
              setBudget={setBudget}
              categories={categories}
              submitBudget={submitBudget}
              budgetList={budgetList}
              month={month}
              monthLabel={monthLabel}
            />
          )}

          {page === "Metas de ahorro" && (
            <SavingsGoals
              savingsGoalFormData={savingsGoalFormData}
              setSavingsGoalFormData={setSavingsGoalFormData}
              createSavingsGoal={createSavingsGoal}
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
