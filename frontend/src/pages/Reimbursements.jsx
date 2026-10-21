import React from "react";

export default function Reimbursements({
  reimbursementForm,
  setReimbursementForm,
  reimbursementsData,
  reimbursements,
  createReimbursement,
  completeReimbursement,
  money,
  sum,
}) {
  return (
    <>
      <div className="panels">
        <section className="panel">
          <h2>Registrar gasto reembolsable</h2>

          <p className="muted">
            Registra un gasto laboral pagado con tu dinero y que
            posteriormente deberá ser reembolsado.
          </p>

          <form
            className="form-grid"
            onSubmit={(e) => {
              e.preventDefault();
              createReimbursement();
            }}
          >
            <label>
              Fecha
              <input
                type="date"
                required
                value={reimbursementForm.date}
                onChange={(e) =>
                  setReimbursementForm({
                    ...reimbursementForm,
                    date: e.target.value,
                  })
                }
              />
            </label>

            <label>
              Moneda
              <select
                value={reimbursementForm.currency}
                onChange={(e) =>
                  setReimbursementForm({
                    ...reimbursementForm,
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
                value={reimbursementForm.amount}
                onChange={(e) =>
                  setReimbursementForm({
                    ...reimbursementForm,
                    amount: e.target.value,
                  })
                }
              />
            </label>

            <label>
              Descripción
              <input
                type="text"
                maxLength="255"
                required
                placeholder="Ej. Taxi reunión cliente"
                value={reimbursementForm.description}
                onChange={(e) =>
                  setReimbursementForm({
                    ...reimbursementForm,
                    description: e.target.value,
                  })
                }
              />
            </label>

            <button type="submit" className="primary">
              Registrar gasto
            </button>
          </form>
        </section>

        <section className="panel">
          <h2>Resumen de reembolsos</h2>

          <div className="summary-section-title">
            Pendiente por recuperar
          </div>

          <div className="summary-row">
            <span>Soles</span>
            <b>
              {money(
                reimbursementsData
                  .filter(
                    (r) =>
                      r.status === "pending" && r.currency === "PEN",
                  )
                  .reduce((total, r) => total + Number(r.amount), 0),
              )}
            </b>
          </div>

          <div className="summary-row">
            <span>Dólares</span>
            <b>
              {money(
                reimbursementsData
                  .filter(
                    (r) =>
                      r.status === "pending" && r.currency === "USD",
                  )
                  .reduce((total, r) => total + Number(r.amount), 0),
                "USD",
              )}
            </b>
          </div>

          <div className="summary-section-title">
            Reembolsado este mes
          </div>

          <div className="summary-row">
            <span>Soles</span>
            <b>{money(sum(reimbursements, "PEN"))}</b>
          </div>

          <div className="summary-row">
            <span>Dólares</span>
            <b>{money(sum(reimbursements, "USD"), "USD")}</b>
          </div>
        </section>
      </div>

      <div className="panel" style={{ marginTop: "20px" }}>
        <h2>Gastos pendientes de reembolso</h2>

        {reimbursementsData.filter((r) => r.status === "pending")
          .length === 0 ? (
          <p className="muted">
            No tienes gastos pendientes de reembolso.
          </p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Descripción</th>
                  <th>Moneda</th>
                  <th>Monto</th>
                  <th>Estado</th>
                  <th>Acción</th>
                </tr>
              </thead>

              <tbody>
                {reimbursementsData
                  .filter((r) => r.status === "pending")
                  .map((r) => (
                    <tr key={r.id}>
                      <td>{r.date}</td>
                      <td>{r.description || "Gasto laboral"}</td>
                      <td>{r.currency}</td>
                      <td>{money(Number(r.amount), r.currency)}</td>
                      <td>Pendiente</td>
                      <td>
                        <button
                          type="button"
                          className="primary"
                          onClick={() => completeReimbursement(r.id)}
                        >
                          Marcar como reembolsado
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="summary-section-title">
          Historial de reembolsos
        </div>

        {reimbursementsData.filter((r) => r.status === "reimbursed")
          .length === 0 ? (
          <p className="muted">
            Todavía no tienes reembolsos completados.
          </p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Gasto</th>
                  <th>Descripción</th>
                  <th>Fecha reembolso</th>
                  <th>Moneda</th>
                  <th>Monto</th>
                  <th>Estado</th>
                </tr>
              </thead>

              <tbody>
                {reimbursementsData
                  .filter((r) => r.status === "reimbursed")
                  .map((r) => (
                    <tr key={r.id}>
                      <td>{r.date}</td>
                      <td>{r.description || "Gasto laboral"}</td>
                      <td>{r.reimbursed_date || "-"}</td>
                      <td>{r.currency}</td>
                      <td>{money(Number(r.amount), r.currency)}</td>
                      <td>Reembolsado</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
