export const money = (n, c = "PEN") =>
  new Intl.NumberFormat("es-PE", {
    style: "currency",
    currency: c,
    minimumFractionDigits: 2,
  }).format(Number(n || 0));
export const monthLabel = (m) =>
  new Date(`${m}-02T12:00:00`).toLocaleDateString("es-PE", {
    month: "long",
    year: "numeric",
  });
