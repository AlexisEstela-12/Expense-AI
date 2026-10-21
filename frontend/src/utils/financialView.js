export const ordinary = (m) => m.category !== "Cambio de divisas";

export const sum = (items, c) =>
  items
    .filter((m) => m.currency === c)
    .reduce((a, m) => a + Number(m.amount), 0);

export const filterMonthlyMovements = (movements, month) => {
  const inMonth = (m) => m.date?.startsWith(month);
  const expenses = movements.filter(
    (m) => inMonth(m) && m.kind === "expense" && ordinary(m),
  );
  const income = movements.filter(
    (m) => inMonth(m) && m.kind === "income" && ordinary(m),
  );
  const reimbursements = movements.filter(
    (m) => inMonth(m) && m.kind === "reimbursement",
  );
  return { expenses, income, reimbursements };
};

export const movementTotals = (expenses, income) => {
  const expensePen = sum(expenses, "PEN"),
    expenseUsd = sum(expenses, "USD"),
    incomePen = sum(income, "PEN"),
    incomeUsd = sum(income, "USD");
  return { expensePen, expenseUsd, incomePen, incomeUsd };
};

export const calculateCategoryData = (expenses) =>
  Object.values(
    expenses
      .filter((m) => m.currency === "PEN")
      .reduce((a, m) => {
        a[m.category] ??= { name: m.category, value: 0 };
        a[m.category].value += Number(m.amount);
        return a;
      }, {}),
  ).sort((a, b) => b.value - a.value);

export const calculateMonthly = (movements, month) => {
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
};
