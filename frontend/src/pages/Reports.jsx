import React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

export default function Reports({ monthly, categoryData, colors, money }) {
  return (
    <div className="panels">
      <section className="panel full">
        <h2>Ingresos y gastos de los últimos seis meses (PEN)</h2>
        <ResponsiveContainer width="100%" height={330}>
          <BarChart data={monthly}>
            <CartesianGrid vertical={false} stroke="#e9edf4" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip formatter={(v) => money(v)} />
            <Legend />
            <Bar dataKey="Ingresos" fill="#278763" />
            <Bar dataKey="Gastos" fill="#2563ad" />
          </BarChart>
        </ResponsiveContainer>
      </section>
      <section className="panel full">
        <h2>Gastos por categoría (PEN)</h2>
        {categoryData.length ? (
          categoryData.map((d, i) => (
            <div className="summary-row" key={d.name}>
              <span>
                <span
                  className="dot"
                  style={{ background: colors[i % colors.length] }}
                />
                {d.name}
              </span>
              <b>{money(d.value)}</b>
            </div>
          ))
        ) : (
          <p className="empty">No hay gastos en este período.</p>
        )}
      </section>
    </div>
  );
}
