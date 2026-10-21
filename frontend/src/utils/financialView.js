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
