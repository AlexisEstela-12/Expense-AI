import React from "react";

export default function BudgetList({ currentBudgets, money, month, monthLabel }) {
  return (
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
}
