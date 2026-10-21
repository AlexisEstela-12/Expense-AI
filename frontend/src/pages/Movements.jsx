import React from "react";
import { Plus } from "lucide-react";

export default function Movements({
  form, setForm, categories, showNewCategory, setShowNewCategory,
  newCategory, setNewCategory, createNewCategory, submitMovement,
  summary, money, incomePen, incomeUsd,
  expensePen, expenseUsd, sum, reimbursements, table,
}) {
  return (
    <div className="panels">
      <section className="panel">
        <h2>Nuevo movimiento</h2>
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
      </section>
      <section className="panel">
        <h2>Resumen del mes</h2>
        <div className="summary-section-title">Saldos actuales</div>
        <div className="summary-row">
          <span>Saldo disponible PEN</span>
          <b>{money(summary.balances.PEN)}</b>
        </div>
        <div className="summary-row">
          <span>Saldo disponible USD</span>
          <b>{money(summary.balances.USD, "USD")}</b>
        </div>
        <div className="summary-section-title">Actividad del mes</div>
        <div className="summary-row">
          <span>Ingresos PEN</span>
          <b>{money(incomePen)}</b>
        </div>
        <div className="summary-row">
          <span>Ingresos USD</span>
          <b>{money(incomeUsd, "USD")}</b>
        </div>
        <div className="summary-row">
          <span>Gastos PEN</span>
          <b>{money(expensePen)}</b>
        </div>
        <div className="summary-row">
          <span>Gastos USD</span>
          <b>{money(expenseUsd, "USD")}</b>
        </div>
        <div className="summary-row">
          <span>Reembolsos recibidos PEN</span>
          <b>{money(sum(reimbursements, "PEN"))}</b>
        </div>
        <div className="summary-row">
          <span>Reembolsos recibidos USD</span>
          <b>{money(sum(reimbursements, "USD"), "USD")}</b>
        </div>
      </section>
      <section className="panel full">
        <h2>Historial de movimientos</h2>
        {table}
      </section>
    </div>
  );
}
