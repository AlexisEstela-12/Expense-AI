import React from "react";

export default function Exchanges({ fx, setFx, submitExchange, summary, movements, money }) {
  const exchangeForm = (
    <form onSubmit={submitExchange} className="form-grid">
      <label>
        Fecha
        <input
          required
          type="date"
          value={fx.date}
          onChange={(e) => setFx({ ...fx, date: e.target.value })}
        />
      </label>
      <label>
        Dirección
        <select
          value={fx.from_currency}
          onChange={(e) => setFx({ ...fx, from_currency: e.target.value })}
        >
          <option value="USD">USD → PEN</option>
          <option value="PEN">PEN → USD</option>
        </select>
      </label>
      <label>
        Monto entregado ({fx.from_currency})
        <input
          required
          type="number"
          min="0.01"
          step="0.01"
          value={fx.amount_out}
          onChange={(e) => setFx({ ...fx, amount_out: e.target.value })}
        />
      </label>
      <label>
        Monto recibido ({fx.from_currency === "USD" ? "PEN" : "USD"})
        <input
          required
          type="number"
          min="0.01"
          step="0.01"
          value={fx.amount_in}
          onChange={(e) => setFx({ ...fx, amount_in: e.target.value })}
        />
      </label>
      <div className="hint">
        Tipo de cambio efectivo:{" "}
        {Number(fx.amount_out) > 0 && Number(fx.amount_in) > 0
          ? (fx.from_currency === "USD"
              ? Number(fx.amount_in) / Number(fx.amount_out)
              : Number(fx.amount_out) / Number(fx.amount_in)
            ).toFixed(4)
          : "—"}{" "}
        PEN/USD
      </div>
      <button className="primary" type="submit">
        Registrar cambio
      </button>
    </form>
  );
  return (
    <div className="panels">
      <section className="panel">
        <h2>Registrar cambio</h2>
        <p className="muted">
          Sin cuentas de origen o destino ni comprobantes.
        </p>
        {exchangeForm}
      </section>
      <section className="panel">
        <h2>Tus saldos</h2>
        <div className="balance-box">
          <small>Soles disponibles</small>
          <strong>{money(summary?.spendable?.PEN ?? 0)}</strong>
        </div>
        <div className="balance-box">
          <small>Dólares disponibles</small>
          <strong>{money(summary?.spendable?.USD ?? 0, "USD")}</strong>
        </div>
        <p className="muted">
          Los saldos se actualizan automáticamente al registrar el
          cambio.
        </p>
      </section>
      <section className="panel full">
        <h2>Movimientos de cambio</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Moneda</th>
                <th>Movimiento</th>
              </tr>
            </thead>
            <tbody>
              {movements
                .filter((m) => m.category === "Cambio de divisas")
                .map((m) => (
                  <tr key={m.id}>
                    <td>{m.date}</td>
                    <td>{m.currency}</td>
                    <td
                      className={
                        m.kind === "expense" ? "negative" : "positive"
                      }
                    >
                      {m.kind === "expense" ? "− " : "+ "}
                      {money(m.amount, m.currency)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
