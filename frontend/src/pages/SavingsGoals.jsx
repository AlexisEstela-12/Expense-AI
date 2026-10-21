import React from "react";

export default function SavingsGoals({
  savingsGoalFormData, setSavingsGoalFormData, createSavingsGoal,
  savingsGoals, money,
  addSavingsContribution, useSavingsGoal, cancelSavingsGoal,
}) {
  return (
    <div className="panels">
      <section className="panel">
        <h2>Nueva meta</h2>
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
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Metas de ahorro</h2>
        </div>

        <p className="muted">
          Separa parte de tu saldo para objetivos específicos sin
          registrarlo como un gasto.
        </p>

        {savingsGoals.length === 0 ? (
          <p className="empty">Todavía no tienes metas de ahorro.</p>
        ) : (
          savingsGoals.map((goal) => (
            <div className="budget-row" key={goal.id}>
              <div className="budget-head">
                <div>
                  <strong>{goal.name}</strong>

                  <p className="muted">
                    Objetivo:{" "}
                    {money(Number(goal.target_amount), goal.currency)}
                    {goal.target_date
                      ? ` · Fecha objetivo: ${goal.target_date}`
                      : ""}
                  </p>
                </div>

                <strong>{goal.percentage}%</strong>
              </div>

              <div className="progress">
                <span
                  style={{
                    width: `${Math.min(goal.percentage, 100)}%`,
                  }}
                />
              </div>

              <p className="muted">
                Ahorrado:{" "}
                {money(Number(goal.saved_amount), goal.currency)} de{" "}
                {money(Number(goal.target_amount), goal.currency)}
              </p>
              <div className="goal-actions">
                <button
                  className="primary"
                  type="button"
                  onClick={() => addSavingsContribution(goal)}
                >
                  Realizar aporte
                </button>

                <button
                  className="secondary"
                  type="button"
                  onClick={() => useSavingsGoal(goal)}
                  disabled={Number(goal.saved_amount) <= 0}
                >
                  Usar ahorro
                </button>

                <button
                  className="secondary"
                  type="button"
                  onClick={() => cancelSavingsGoal(goal)}
                >
                  Cancelar meta
                </button>
              </div>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
