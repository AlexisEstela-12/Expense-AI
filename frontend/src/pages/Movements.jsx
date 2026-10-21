import React from "react";

export default function Movements({
  movementForm, summary, money, incomePen, incomeUsd,
  expensePen, expenseUsd, sum, reimbursements, table,
}) {
  return (
    <div className="panels">
      <section className="panel">
        <h2>Nuevo movimiento</h2>
        {movementForm}
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
