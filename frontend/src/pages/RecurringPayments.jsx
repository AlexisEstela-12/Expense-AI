import React from "react";

export default function RecurringPayments({
  recurringForm,
  setRecurringForm,
  categories,
  recurringPayments,
  createRecurringPayment,
  payRecurringPayment,
  money,
}) {
  return (
    <div className="panels">
      <section className="panel">
        <h2>Nuevo pago recurrente</h2>

        <p className="muted">
          Registra servicios, suscripciones y otros pagos que realizas
          periódicamente.
        </p>

        <form
          className="form-grid"
          onSubmit={(e) => {
            e.preventDefault();
            createRecurringPayment();
          }}
        >
          <label>
            Nombre
            <input
              type="text"
              required
              maxLength="100"
              placeholder="Ej. Internet hogar"
              value={recurringForm.name}
              onChange={(e) =>
                setRecurringForm({
                  ...recurringForm,
                  name: e.target.value,
                })
              }
            />
          </label>

          <label>
            Categoría
            <select
              value={recurringForm.category}
              onChange={(e) =>
                setRecurringForm({
                  ...recurringForm,
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
              value={recurringForm.currency}
              onChange={(e) =>
                setRecurringForm({
                  ...recurringForm,
                  currency: e.target.value,
                })
              }
            >
              <option value="PEN">PEN - Soles</option>
              <option value="USD">USD - Dólares</option>
            </select>
          </label>

          <label>
            Monto
            <input
              type="number"
              min="0.01"
              step="0.01"
              required
              placeholder="0.00"
              value={recurringForm.amount}
              onChange={(e) =>
                setRecurringForm({
                  ...recurringForm,
                  amount: e.target.value,
                })
              }
            />
          </label>

          <label>
            Frecuencia
            <select
              value={recurringForm.frequency}
              onChange={(e) =>
                setRecurringForm({
                  ...recurringForm,
                  frequency: e.target.value,
                })
              }
            >
              <option value="weekly">Semanal</option>
              <option value="monthly">Mensual</option>
              <option value="yearly">Anual</option>
            </select>
          </label>

          <label>
            Próximo pago
            <input
              type="date"
              required
              value={recurringForm.next_payment_date}
              onChange={(e) =>
                setRecurringForm({
                  ...recurringForm,
                  next_payment_date: e.target.value,
                })
              }
            />
          </label>

          <button type="submit" className="primary">
            Registrar pago recurrente
          </button>
        </form>
      </section>
      <section className="panel">
        <h2>Próximos pagos</h2>

        <p className="muted">
          Pagos recurrentes activos ordenados por su próximo
          vencimiento.
        </p>

        {recurringPayments.filter((p) => p.active).length === 0 ? (
          <p className="empty">No tienes pagos recurrentes activos.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Próximo pago</th>
                  <th>Nombre</th>
                  <th>Moneda</th>
                  <th>Monto</th>
                  <th>Frecuencia</th>
                  <th>Acción</th>
                </tr>
              </thead>

              <tbody>
                {recurringPayments
                  .filter((p) => p.active)
                  .map((p) => (
                    <tr key={p.id}>
                      <td>{p.next_payment_date}</td>
                      <td>{p.name}</td>
                      <td>{p.currency}</td>
                      <td>{money(Number(p.amount), p.currency)}</td>
                      <td>
                        {p.frequency === "weekly"
                          ? "Semanal"
                          : p.frequency === "monthly"
                            ? "Mensual"
                            : "Anual"}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="primary"
                          onClick={() => payRecurringPayment(p.id)}
                        >
                          Marcar como pagado
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
