import React from "react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import { Wallet, TrendingUp, TrendingDown, ChevronRight } from "lucide-react";

export default function Dashboard({
  summary, incomePen, incomeUsd, expensePen, expenseUsd,
  categoryData, monthly, colors, month, money, monthLabel,
  budgetList, alerts, table, open,
}) {
  return (
    <>
      <div className="stats">
        <div className="stat">
          <span className="stat-icon green-bg">
            <Wallet />
          </span>
          <span>Disponible en soles</span>
          <strong>
            {money(summary.spendable?.PEN ?? summary.balances.PEN)}
          </strong>
          <small>
            Total: {money(summary.balances.PEN)} · Reservado:{" "}
            {money(summary.reserved?.PEN ?? 0)}
          </small>
        </div>

        <div className="stat">
          <span className="stat-icon blue-bg">
            <Wallet />
          </span>
          <span>Disponible en dólares</span>
          <strong>
            {money(
              summary.spendable?.USD ?? summary.balances.USD,
              "USD",
            )}
          </strong>
          <small>
            Total: {money(summary.balances.USD, "USD")} · Reservado:{" "}
            {money(summary.reserved?.USD ?? 0, "USD")}
          </small>
        </div>
        <div className="stat">
          <span className="stat-icon green-bg">
            <TrendingUp />
          </span>
          <span>Ingresos del mes</span>
          <strong>{money(incomePen)}</strong>
          <small>USD: {money(incomeUsd, "USD")}</small>
        </div>
        <div className="stat">
          <span className="stat-icon red-bg">
            <TrendingDown />
          </span>
          <span>Gastos del mes</span>
          <strong>{money(expensePen)}</strong>
          <small>USD: {money(expenseUsd, "USD")}</small>
        </div>
      </div>
      <div className="panels">
        <section className="panel">
          <div className="panel-title">
            <h2>Gastos por categoría (PEN)</h2>
            <span>{monthLabel(month)}</span>
          </div>
          {categoryData.length ? (
            <div className="pie-layout">
              <div className="dashboard-pie">
              <ResponsiveContainer width="100%" height={265}>
                <PieChart>
                  <Pie
                    data={categoryData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={65}
                    outerRadius={100}
                    paddingAngle={2}
                  >
                    {categoryData.map((d, i) => (
                      <Cell
                        key={d.name}
                        fill={colors[i % colors.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => money(v)} />
                </PieChart>
              </ResponsiveContainer>
              </div>
              <div className="legend">
                {categoryData.map((d, i) => (
                  <div key={d.name}>
                    <span
                      className="dot"
                      style={{ background: colors[i % colors.length] }}
                    />
                    {d.name}
                    <strong>{money(d.value)}</strong>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="empty chart-empty">
              Registra gastos en soles para visualizar el gráfico.
            </p>
          )}
        </section>
        <section className="panel">
          <div className="panel-title">
            <h2>Ingresos vs. gastos</h2>
            <span>Últimos 6 meses · PEN</span>
          </div>
          <ResponsiveContainer width="100%" height={270}>
            <BarChart
              data={monthly}
              margin={{ top: 12, right: 6, left: 0, bottom: 0 }}
            >
              <CartesianGrid vertical={false} stroke="#e9edf4" />
              <XAxis dataKey="name" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} width={60} />
              <Tooltip formatter={(v) => money(v)} />
              <Legend />
              <Bar
                dataKey="Ingresos"
                fill="#278763"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="Gastos"
                fill="#2563ad"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </section>
        <section className="panel">
          <div className="panel-title">
            <h2>Presupuestos del mes</h2>
            <button
              className="link"
              onClick={() => open("Presupuestos")}
            >
              Ver todos <ChevronRight size={14} />
            </button>
          </div>
          {budgetList}
        </section>
        <section className="panel">
          <div className="panel-title">
            <h2>Alertas recientes</h2>
            <button
              className="link"
              onClick={() => open("Notificaciones")}
            >
              Ver todas <ChevronRight size={14} />
            </button>
          </div>
          {alerts.length ? (
            alerts.map((b) => (
              <div className="alert-item" key={b.id}>
                <span
                  className={
                    b.alert >= 90
                      ? "alert-icon critical"
                      : "alert-icon caution"
                  }
                >
                  !
                </span>
                <div>
                  <strong>
                    {b.alert >= 100
                      ? "Presupuesto agotado"
                      : `Has alcanzado el ${b.alert}% de tu presupuesto`}
                  </strong>
                  <p>
                    {b.category}: {money(b.spent, b.currency)} de{" "}
                    {money(b.limit, b.currency)}
                  </p>
                </div>
              </div>
            ))
          ) : (
            <p className="empty">
              Sin alertas de presupuesto para este mes.
            </p>
          )}
        </section>
      </div>
      <section className="panel recent">
        <div className="panel-title">
          <h2>Movimientos recientes</h2>
          <button className="link" onClick={() => open("Movimientos")}>
            Ver todos <ChevronRight size={14} />
          </button>
        </div>
        {table}
      </section>
    </>
  );
}
