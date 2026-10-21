export const ordinary = (m) => m.category !== "Cambio de divisas";

export const sum = (items, c) =>
  items
    .filter((m) => m.currency === c)
    .reduce((a, m) => a + Number(m.amount), 0);
