import React from "react";

export default function MovementsTable({ visibleMovements, hasMovements, money }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Tipo</th>
            <th>Categoría</th>
            <th>Descripción</th>
            <th>Moneda</th>
            <th>Monto</th>
          </tr>
        </thead>
        <tbody>
          {visibleMovements.map((m) => (
              <tr key={m.id}>
                <td>{m.date}</td>
                <td>
                  <span className={`type ${m.kind}`}>
                    {m.category === "Cambio de divisas"
                      ? "↔ Cambio"
                      : m.kind === "income"
                        ? "↓ Ingreso"
                        : m.kind === "expense"
                          ? "↑ Gasto"
                          : "↓ Reembolso"}
                  </span>
                </td>
                <td>{m.category}</td>
                <td>{m.description || "—"}</td>
                <td>{m.currency}</td>
                <td className={m.kind === "expense" ? "negative" : "positive"}>
                  {m.kind === "expense" ? "− " : "+ "}
                  {money(m.amount, m.currency)}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
      {!hasMovements && (
        <p className="empty">Registra tu primer movimiento para comenzar.</p>
      )}
    </div>
  );
}
