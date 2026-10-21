import React from "react";

export default function Settings({ onRefresh }) {
  return (
    <section className="panel">
      <h2>Configuración</h2>
      <p className="muted">
        Versión local de desarrollo. No publiques esta aplicación en
        Internet sin autenticación y HTTPS.
      </p>
      <button className="secondary" onClick={onRefresh}>
        Actualizar datos
      </button>
    </section>
  );
}
