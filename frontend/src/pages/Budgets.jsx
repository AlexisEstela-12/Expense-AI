import React from "react";

export default function Budgets({ budgetForm, budgetList, month, monthLabel }) {
  return (
    <div className="panels">
      <section className="panel">
        <h2>Nuevo presupuesto</h2>
        {budgetForm}
      </section>
      <section className="panel">
        <h2>Seguimiento · {monthLabel(month)}</h2>
        {budgetList}
      </section>
    </div>
  );
}
