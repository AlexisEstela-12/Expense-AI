import { API, apiFetch } from "./client.js";

export const requestFinancialChat = (message, signal, baseUrl = API) =>
  apiFetch(`${baseUrl}/api/chat/tools`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });
