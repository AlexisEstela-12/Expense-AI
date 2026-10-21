import { API } from "./client.js";

export const requestFinancialChat = (message, signal, baseUrl = API) =>
  fetch(`${baseUrl}/api/chat/tools`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });
