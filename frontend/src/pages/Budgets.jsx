import React from "react";

export default function Budgets({ budget, setBudget, categories, submitBudget, budgetList, month, monthLabel }) {
  return (
    <div className="panels">
      <section className="panel">
        <h2>Nuevo presupuesto</h2>
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
      </section>
      <section className="panel">
        <h2>Seguimiento · {monthLabel(month)}</h2>
        {budgetList}
      </section>
    </div>
  );
}
