import React from "react";

export default function Notifications({ notifications }) {
  return (
    <section className="panel">
      <h2>Centro de notificaciones</h2>

      <p className="muted">
        Aquí encontrarás alertas sobre tus pagos, presupuestos y
        reembolsos pendientes.
      </p>

      {notifications.length ? (
        notifications.map((notification, index) => (
          <div
            className="alert-item"
            key={`${notification.type}-${notification.date}-${index}`}
          >
            <span
              className={
                notification.level === "danger"
                  ? "alert-icon critical"
                  : notification.level === "warning"
                    ? "alert-icon caution"
                    : "alert-icon"
              }
            >
              !
            </span>

            <div>
              <strong>{notification.title}</strong>

              <p>{notification.message}</p>

              <span className="muted">
                {notification.type === "recurring_payment"
                  ? "Pago recurrente"
                  : notification.type === "budget"
                    ? "Presupuesto"
                    : notification.type === "reimbursement"
                      ? "Reembolso"
                      : "Notificación"}
              </span>
            </div>
          </div>
        ))
      ) : (
        <p className="empty">No tienes notificaciones activas.</p>
      )}

      <p className="muted">
        Por ahora las alertas se muestran dentro de la aplicación; las
        notificaciones externas llegarán en otra fase.
      </p>
    </section>
  );
}
